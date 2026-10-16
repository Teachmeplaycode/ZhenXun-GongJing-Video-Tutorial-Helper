import React, { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import gsap from 'gsap'
import { SHEET, SCULPTURE_VIEW, sampleSheets, composeSheetMatrix } from '../lib/sculptureMath'
import { token } from '../lib/tokens'
import { DUR, EASE, isLowEndDevice, prefersReducedMotion } from '../lib/motion'
import SculptureFallback from './SculptureFallback'
import { SCULPTURE_SETTINGS } from '../config/workspace'
import { morphStateAt, SHAPE_LABELS } from '../lib/sculptureShapes'
import { useModelGlitch } from '../lib/useModelGlitch'
import { createPostPass } from '../lib/postPass'
import { buildWordLayouts, fitWordDistance } from '../lib/sculptureWords'

const INSTANCE_COUNT = SCULPTURE_SETTINGS.count
const INSTANCE_COUNT_LOW = SCULPTURE_SETTINGS.lowCount
const ROCK_SPEED = { x: 0.07, y: 0.09, z: 0.04 }
const ROCK_AMOUNT = { x: 0.12, y: 0.18, z: 0.045 }
const PARALLAX = { max: 0.02, lerp: 0.08 }
const CAMERA_FOV = 22 // long-lens look
// Keep both loops inside the frame, including the placement beside the import panel.
const FRAME_HALF = SCULPTURE_SETTINGS.frame

const ANALYSIS_WORD_TIPS = {
  'Loading...': { kicker: 'LOADING / 加载中', title: '正在加载', detail: '系统正在逐帧提取画面。' },
  'Hello!': { kicker: 'HELLO / 你好', title: 'Hello! · 你好', detail: '系统正在逐帧提取画面。' },
  'Waiting...': { kicker: 'WAITING / 请稍候', title: 'Waiting... · 请稍候', detail: '系统正在逐帧提取画面。' },
  率厚: { kicker: 'PINGTAN DIALECT / 平潭话', title: '率厚 · 你好', detail: '「率厚」在平潭话中是「你好」的意思。' },
  '定xiu哇': { kicker: 'PINGTAN DIALECT / 平潭话', title: '定xiu哇 · 等一下', detail: '「定xiu哇」在平潭话中是「等一下」的意思。' },
  '加载中...': { kicker: 'LOADING / 加载中', title: '加载中…', detail: '系统正在逐帧提取画面。' },
}

/**
 * Parametric thin-sheet sculpture (design_2.md §7).
 * mode: 'idle' (infinity loop) | 'analyzing' (light, looping scatter/reassembly)
 * align: 'side' shifts the sculpture right to leave room for the import panel.
 * glassRef: optional element the model refracts through like a glass slide (homepage import box).
 */
export default function SculptureCanvas({ mode = 'idle', align = 'center', glassRef = null, complete = false, className = '' }) {
  const hostRef = useRef(null)
  const canvasRef = useRef(null)
  const stateRef = useRef(null)
  const [failed, setFailed] = useState(false)
  const [morph, setMorph] = useState({ shape: 'infinity', phase: 'hold' })
  const glitch = useModelGlitch(mode === 'idle' && align === 'side' && !failed)
  const glitchRef = useRef(null)
  glitchRef.current = glitch
  const glassElRef = useRef(null)
  glassElRef.current = glassRef

  useEffect(() => {
    const host = hostRef.current
    const canvas = canvasRef.current
    let renderer
    try {
      renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' })
    } catch {
      setFailed(true)
      return undefined
    }
    const low = isLowEndDevice()
    const reduced = prefersReducedMotion()
    const count = low ? INSTANCE_COUNT_LOW : INSTANCE_COUNT

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    renderer.setClearColor(0x000000, 0)
    renderer.shadowMap.enabled = !low
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    renderer.outputColorSpace = THREE.SRGBColorSpace

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(CAMERA_FOV, 1, 1, 400)
    const pivot = new THREE.Group() // horizontal placement
    const group = new THREE.Group() // bounded multi-axis rocking
    pivot.add(group)
    group.rotation.set(SCULPTURE_VIEW.x, SCULPTURE_VIEW.y, SCULPTURE_VIEW.z)
    scene.add(pivot)

    // Large soft light field: hemisphere fill + broad key + low rim for edge separation.
    const hemi = new THREE.HemisphereLight(0xffffff, new THREE.Color(token('--sculpture-shadow')), 1.6)
    scene.add(hemi)
    const key = new THREE.DirectionalLight(0xffffff, 1.5)
    key.position.set(-14, 22, 18)
    key.castShadow = !low
    key.shadow.mapSize.set(1024, 1024)
    key.shadow.radius = 6
    key.shadow.bias = -0.0008
    key.shadow.normalBias = 0.04
    Object.assign(key.shadow.camera, { left: -24, right: 24, top: 24, bottom: -24, near: 1, far: 100 })
    scene.add(key)
    const rim = new THREE.DirectionalLight(0xffffff, 0.55)
    rim.position.set(16, -6, -12)
    scene.add(rim)
    const geometry = new THREE.BoxGeometry(SHEET.width, SHEET.height, SHEET.thickness, 1, 1, 1)
    const lightColor = new THREE.Color(token('--sculpture-light'))
    const wordColor = new THREE.Color(token('--text-primary'))
    const material = new THREE.MeshStandardMaterial({
      color: lightColor.clone(),
      roughness: 0.85,
      metalness: 0,
      side: THREE.DoubleSide,
      flatShading: false,
    })
    const mesh = new THREE.InstancedMesh(geometry, material, count)
    mesh.frustumCulled = false
    mesh.castShadow = !low
    mesh.receiveShadow = !low
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage)
    group.add(mesh)

    const catcher = new THREE.Mesh(
      new THREE.PlaneGeometry(80, 80),
      new THREE.ShadowMaterial({ color: new THREE.Color(token('--sculpture-shadow')), opacity: 0.2 }),
    )
    catcher.rotation.x = -Math.PI / 2
    catcher.position.y = -16
    catcher.receiveShadow = !low
    scene.add(catcher)

    const postPass = low ? null : createPostPass(renderer, {
      background: new THREE.Color(token('--bg-canvas')),
      glint: new THREE.Color(token('--bg-surface')),
      shade: new THREE.Color(token('--sculpture-shadow')),
    })
    const glass = { rect: [0, 0, 0, 0], strength: 0 }
    // Track the glass element in device pixels; its inline opacity (GSAP) fades the refraction.
    const readGlass = () => {
      const el = glassElRef.current?.current
      if (!el || !el.isConnected || el.offsetParent === null) return null
      const r = el.getBoundingClientRect()
      const c = canvas.getBoundingClientRect()
      if (!r.width || r.right < c.left || r.left > c.right || r.bottom < c.top || r.top > c.bottom) return null
      // Buffer pixels per CSS pixel; also correct while the layer is scaled by a transition.
      const sx = canvas.width / c.width
      const sy = canvas.height / c.height
      glass.rect[0] = (r.left - c.left) * sx
      glass.rect[1] = (c.bottom - r.bottom) * sy
      glass.rect[2] = (r.right - c.left) * sx
      glass.rect[3] = (c.bottom - r.top) * sy
      const opacity = el.style.opacity === '' ? 1 : Number(el.style.opacity)
      glass.strength = Number.isFinite(opacity) ? opacity : 1
      return glass.strength > 0.01 ? glass : null
    }

    const wordLayouts = buildWordLayouts(count, SHEET, SCULPTURE_VIEW)
    const sheets = sampleSheets(count, wordLayouts.map((layout) => layout.poses))
    const matrix = new THREE.Matrix4()

    // Animated parameters, tweened by GSAP on mode changes.
    const params = { speed: 1, analyzing: false, cycleTime: 0, offsetX: 0 }
    let lastMorphKey = ''
    const parallax = { x: 0, y: 0, tx: 0, ty: 0 }
    let elapsed = 0
    let cameraDistance = 60
    let wordDistances = []
    let wordOffsets = []
    let viewportHeight = 1
    let wordCenterOffset = 0
    let sideScale = 1

    const resize = () => {
      const rect = host.getBoundingClientRect()
      const { width, height } = rect
      if (!width || !height) return
      renderer.setSize(width, height, false)
      camera.aspect = width / height
      sideScale = width <= 860 ? 0 : 1
      const vFov = THREE.MathUtils.degToRad(CAMERA_FOV)
      const fitV = FRAME_HALF.h / Math.tan(vFov / 2)
      const fitH = FRAME_HALF.w / (Math.tan(vFov / 2) * camera.aspect)
      cameraDistance = Math.max(fitV, fitH)
      viewportHeight = height
      const padding = width <= 860 ? SCULPTURE_SETTINGS.scatterText.mobilePadding : SCULPTURE_SETTINGS.scatterText.padding
      const footerSpace = Math.min(Math.max(padding, SCULPTURE_SETTINGS.scatterText.footerSpace), height * 0.4)
      wordDistances = wordLayouts.map((layout) => fitWordDistance(layout, width, height, CAMERA_FOV, padding, footerSpace))
      const page = host.closest('.wireframe')?.getBoundingClientRect()
      wordCenterOffset = page ? rect.top + height / 2 - (page.top + page.height / 2) : 0
      wordOffsets = wordLayouts.map((layout, i) => {
        const projectedHeight = layout.height * height / (2 * wordDistances[i] * Math.tan(vFov / 2))
        const desiredCenter = height / 2 - wordCenterOffset - (footerSpace - padding) / 2
        const center = THREE.MathUtils.clamp(desiredCenter, padding + projectedHeight / 2, height - footerSpace - projectedHeight / 2)
        return height / 2 - center
      })
      camera.updateProjectionMatrix()
    }
    const ro = new ResizeObserver(resize)
    ro.observe(host)
    resize()

    const onPointer = (e) => {
      const rect = host.getBoundingClientRect()
      parallax.tx = ((e.clientX - rect.left) / rect.width - 0.5) * 2
      parallax.ty = ((e.clientY - rect.top) / rect.height - 0.5) * 2
    }
    window.addEventListener('pointermove', onPointer)

    let raf = 0
    let last = performance.now()
    const tick = (now) => {
      raf = requestAnimationFrame(tick)
      // A first RAF timestamp can precede setup within the same browser frame.
      const dt = Math.max(0, Math.min((now - last) / 1000, 0.1))
      last = now
      // Bounded rocking preserves the infinity silhouette throughout the animation.
      // Reduced motion freezes the pose, twist and breathing.
      if (!reduced) elapsed += dt * params.speed
      if (params.analyzing && !reduced) params.cycleTime += dt
      const morphState = params.analyzing && !reduced
        ? morphStateAt(params.cycleTime)
        : { shape: 'infinity', spread: 0, phase: 'hold' }
      const morphKey = `${morphState.shape}:${morphState.phase}:${morphState.wordIndex}`
      if (morphKey !== lastMorphKey) {
        lastMorphKey = morphKey
        setMorph({ shape: morphState.shape, phase: morphState.phase, word: morphState.word })
      }
      for (let i = 0; i < count; i += 1) {
        composeSheetMatrix(sheets[i], elapsed, !reduced, matrix, morphState.spread * SCULPTURE_SETTINGS.scatter.amount, morphState.shape, morphState.wordIndex)
        mesh.setMatrixAt(i, matrix)
      }
      mesh.instanceMatrix.needsUpdate = true
      material.color.lerpColors(lightColor, wordColor, morphState.spread * SCULPTURE_SETTINGS.scatterText.inkMix)

      const rock = 1 - morphState.spread
      group.rotation.x = SCULPTURE_VIEW.x + Math.sin(elapsed * ROCK_SPEED.x) * ROCK_AMOUNT.x * rock
      group.rotation.y = SCULPTURE_VIEW.y + Math.sin(elapsed * ROCK_SPEED.y) * ROCK_AMOUNT.y * rock
      group.rotation.z = SCULPTURE_VIEW.z + Math.sin(elapsed * ROCK_SPEED.z) * ROCK_AMOUNT.z * rock
      pivot.position.x = params.offsetX * sideScale
      // Very slight parallax: offset is PARALLAX.max of the camera distance (spec value is
      // normalised to distance so the effect stays equally subtle at any container size).
      parallax.x += (parallax.tx - parallax.x) * PARALLAX.lerp
      parallax.y += (parallax.ty - parallax.y) * PARALLAX.lerp
      const wordDistance = wordDistances[morphState.wordIndex] || cameraDistance
      const distance = THREE.MathUtils.lerp(cameraDistance, wordDistance, morphState.spread ** 2)
      const off = reduced ? 0 : PARALLAX.max * distance * rock
      const wordOffset = wordOffsets[morphState.wordIndex] || 0
      const wordY = -wordOffset * (2 * distance * Math.tan(THREE.MathUtils.degToRad(CAMERA_FOV) / 2) / viewportHeight) * morphState.spread
      camera.position.set(parallax.x * off, 6 * rock - parallax.y * off + wordY, distance)
      camera.lookAt(0, wordY, 0)
      const glassNow = postPass ? readGlass() : null
      if (postPass && (glitchRef.current || glassNow)) postPass.render(scene, camera, glitchRef.current, glassNow)
      else renderer.render(scene, camera)
    }

    const start = () => {
      if (raf) return
      last = performance.now()
      raf = requestAnimationFrame(tick)
    }
    const stop = () => {
      cancelAnimationFrame(raf)
      raf = 0
    }
    const onVisibility = () => (document.hidden ? stop() : start())
    document.addEventListener('visibilitychange', onVisibility)
    start()

    stateRef.current = { params }

    return () => {
      stop()
      ro.disconnect()
      window.removeEventListener('pointermove', onPointer)
      document.removeEventListener('visibilitychange', onVisibility)
      gsap.killTweensOf(params)
      geometry.dispose()
      material.dispose()
      catcher.geometry.dispose()
      catcher.material.dispose()
      postPass?.dispose()
      renderer.dispose()
      stateRef.current = null
    }
  }, [])

  // Start the repeating gallery only when entering the analysis scene.
  useEffect(() => {
    const params = stateRef.current?.params
    if (!params) return
    const analyzing = mode === 'analyzing'
    params.analyzing = analyzing
    params.cycleTime = 0
    gsap.to(params, { speed: analyzing ? 1.3 : 1, duration: DUR.long, ease: EASE.move })
  }, [mode])

  useEffect(() => {
    const params = stateRef.current?.params
    if (!params) return
    gsap.to(params, { offsetX: align === 'side' ? SCULPTURE_SETTINGS.sideOffset : 0, duration: DUR.scene, ease: EASE.move })
  }, [align])

  if (failed) return <SculptureFallback className={className} align={align} />
  const wordTip = ANALYSIS_WORD_TIPS[morph.word] || ANALYSIS_WORD_TIPS['加载中...']
  return (
    <div
      ref={hostRef}
      className={`sculpture ${className}`}
      data-shape={morph.shape}
      data-phase={morph.phase}
      data-word={morph.phase === 'word' ? morph.word : undefined}
      data-glitch={glitch ? glitch.look : 'off'}
      role="img"
      aria-label={morph.phase === 'word' ? `薄片排列的文字：${morph.word}` : `动态薄片模型：${SHAPE_LABELS[morph.shape].name}`}
    >
      <canvas ref={canvasRef} aria-hidden="true" />
      {mode === 'analyzing' ? (
        <div className="sculpture__caption" aria-hidden="true">
          <span className="mono-sm">{wordTip.kicker}</span>
          <strong>{wordTip.title}</strong>
          <span>{wordTip.detail}</span>
          <span className="sculpture__caption-status">
            <i />{complete ? '切分已完成，可以进入对话分析。' : '当前正在切分视频帧，请耐心等待。'}
          </span>
        </div>
      ) : null}
    </div>
  )
}
