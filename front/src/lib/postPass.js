import * as THREE from 'three'

// Post pass over the sculpture render. Two jobs, both touching only what the canvas draws:
// 1. Glass slide: the homepage import box refracts the model like a thick lab slide
//    (slight magnification, bent bevel, edge dispersion, soft blur, edge glints).
// 2. Signal glitch: slight warp, torn bands, RGB split, displaced strips, interlace.
// The scene is rendered into a target only while one of them is active.
const vertexShader = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = vec4(position.xy, 0.0, 1.0);
  }
`

const fragmentShader = /* glsl */ `
  uniform sampler2D tScene;
  uniform vec2 uRes;
  uniform vec3 uBg;
  uniform vec3 uGlint;
  uniform vec3 uShade;
  // glitch
  uniform float uSeed;
  uniform float uWarp;
  uniform float uSlice;
  uniform float uTear;
  uniform float uRgb;
  uniform float uBlocks;
  uniform float uScan;
  // glass, in device pixels with a bottom-left origin (gl_FragCoord space)
  uniform vec4 uGlass;
  uniform float uGlassOn;
  uniform float uRadius;
  uniform float uBevel;
  uniform float uBlur;
  varying vec2 vUv;

  float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7)) + uSeed * 43.7) * 43758.5453);
  }

  vec3 toSRGB(vec3 c) {
    return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(0.0031308, c));
  }

  float sdRoundRect(vec2 p, vec2 b, float r) {
    vec2 q = abs(p) - b + r;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
  }

  // Premultiplied linear scene sample, optionally softened with a 5-tap cross.
  vec4 scene(vec2 uv, float blur) {
    vec4 s = texture2D(tScene, clamp(uv, 0.0, 1.0));
    if (blur > 0.0) {
      vec2 d = blur / uRes;
      s = s * 0.4
        + texture2D(tScene, clamp(uv + vec2(d.x, 0.0), 0.0, 1.0)) * 0.15
        + texture2D(tScene, clamp(uv - vec2(d.x, 0.0), 0.0, 1.0)) * 0.15
        + texture2D(tScene, clamp(uv + vec2(0.0, d.y), 0.0, 1.0)) * 0.15
        + texture2D(tScene, clamp(uv - vec2(0.0, d.y), 0.0, 1.0)) * 0.15;
    }
    return s;
  }

  void main() {
    vec2 uv = vUv;
    vec2 frag = gl_FragCoord.xy;

    // --- glass slide -------------------------------------------------------------
    vec2 gc = (uGlass.xy + uGlass.zw) * 0.5;
    vec2 gh = (uGlass.zw - uGlass.xy) * 0.5;
    float sd = sdRoundRect(frag - gc, gh, uRadius);
    float inside = uGlassOn * step(sd, 0.0);
    // 1 at the edge, 0 once deeper than the bevel
    float rim = clamp(1.0 + sd / uBevel, 0.0, 1.0);
    vec2 n = normalize(vec2(
      sdRoundRect(frag - gc + vec2(1.0, 0.0), gh, uRadius) - sd,
      sdRoundRect(frag - gc + vec2(0.0, 1.0), gh, uRadius) - sd
    ) + 1e-5);
    // Whole slab magnifies a touch; the bevel bends light hard toward the inside.
    vec2 lens = (-(frag - gc) * 0.05 - n * rim * rim * uBevel * 1.6) * inside / uRes;
    float blur = uBlur * inside;

    // --- glitch -------------------------------------------------------------------
    float bulgeY = hash(vec2(uSeed, 12.0));
    float bulge = exp(-pow((vUv.y - bulgeY) * 9.0, 2.0));
    uv.x += uWarp * (sin(vUv.y * 9.0 + uSeed * 6.0) + 2.5 * bulge);
    uv.y += uWarp * 0.6 * bulge * (hash(vec2(uSeed, 13.0)) - 0.5);

    float bands = mix(12.0, 46.0, hash(vec2(uSeed, 1.0)));
    float band = floor(vUv.y * bands);
    float shift = step(hash(vec2(band, 2.0)), uSlice * 0.45) * (hash(vec2(band, 3.0)) - 0.5) * uTear;
    float hair = floor(gl_FragCoord.y / 2.0);
    shift += step(hash(vec2(hair, 4.0)), uSlice * 0.025) * (hash(vec2(hair, 5.0)) - 0.5) * uTear * 2.0;

    float row = floor(vUv.y * 36.0);
    float rowOn = step(hash(vec2(row, 10.0)), 0.3);
    vec2 cell = vec2(floor(vUv.x * mix(6.0, 18.0, hash(vec2(row, 11.0)))), row);
    float block = step(hash(cell + 7.0), uBlocks * 0.5) * rowOn;
    uv += block * (vec2(hash(cell + 8.0), hash(cell + 9.0)) - 0.5) * vec2(0.08, 0.02);
    uv.x += shift;

    // --- sample: glitch split along x, glass dispersion along the refraction ------------
    vec2 split = vec2(uRgb * (1.0 + abs(shift) * 18.0) / uRes.x, 0.0);
    vec4 sr = scene(uv + split + lens * 0.92, blur);
    vec4 sg = scene(uv + lens, blur);
    vec4 sb = scene(uv - split + lens * 1.1, blur);

    // Match the direct render: each sample is encoded to sRGB unpremultiplied, then the channel
    // gap up to the widest alpha is filled with the page colour so fringes stay soft.
    float a = max(sg.a, max(sr.a, sb.a));
    vec3 bg = toSRGB(uBg);
    vec3 c = vec3(
      toSRGB(sr.rgb / max(sr.a, 1e-4)).r * sr.a + bg.r * (a - sr.a),
      toSRGB(sg.rgb / max(sg.a, 1e-4)).g * sg.a + bg.g * (a - sg.a),
      toSRGB(sb.rgb / max(sb.a, 1e-4)).b * sb.a + bg.b * (a - sb.a)
    );
    c *= 1.0 - uScan * 0.08 * step(1.0, mod(gl_FragCoord.y, 3.0));

    // Glass edge: a glint on the bevel facing the key light, a soft shade on the far side.
    float facing = dot(n, normalize(vec2(-0.45, 0.9)));
    float glint = inside * pow(rim, 5.0) * max(facing, 0.0) * 0.85;
    float shade = inside * pow(rim, 3.0) * max(-facing, 0.0) * 0.35;
    vec3 shadeC = toSRGB(uShade);
    c = c * (1.0 - shade) + shadeC * shade;
    a = a * (1.0 - shade) + shade;
    c = c * (1.0 - glint) + toSRGB(uGlint) * glint;
    a = a * (1.0 - glint) + glint;

    gl_FragColor = vec4(c, a);
  }
`

const CLEAN = { seed: 0, warp: 0, slice: 0, tear: 0, rgb: 0, blocks: 0, scan: 0 }

export function createPostPass(renderer, colors) {
  const target = new THREE.WebGLRenderTarget(1, 1, {
    samples: renderer.capabilities.isWebGL2 ? 4 : 0,
    type: THREE.HalfFloatType,
  })
  const material = new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader,
    depthTest: false,
    depthWrite: false,
    blending: THREE.NoBlending, // output is already premultiplied
    uniforms: {
      tScene: { value: target.texture },
      uRes: { value: new THREE.Vector2(1, 1) },
      uBg: { value: colors.background },
      uGlint: { value: colors.glint },
      uShade: { value: colors.shade },
      uSeed: { value: 0 },
      uWarp: { value: 0 },
      uSlice: { value: 0 },
      uTear: { value: 0 },
      uRgb: { value: 0 },
      uBlocks: { value: 0 },
      uScan: { value: 0 },
      uGlass: { value: new THREE.Vector4() },
      uGlassOn: { value: 0 },
      uRadius: { value: 8 },
      uBevel: { value: 16 },
      uBlur: { value: 3 },
    },
  })
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material)
  quad.frustumCulled = false
  const quadScene = new THREE.Scene()
  quadScene.add(quad)
  const quadCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1)
  const size = new THREE.Vector2()

  return {
    // glitch: { seed, warp, slice, tear, rgb, blocks, scan } | null
    // glass: { rect: [x0, y0, x1, y1] device px, bottom-left origin, strength 0..1 } | null
    render(scene, camera, glitch, glass) {
      renderer.getDrawingBufferSize(size)
      if (target.width !== size.x || target.height !== size.y) target.setSize(size.x, size.y)
      const dpr = renderer.getPixelRatio()
      const g = glitch || CLEAN
      const u = material.uniforms
      u.uRes.value.copy(size)
      u.uSeed.value = g.seed
      u.uWarp.value = g.warp
      u.uSlice.value = g.slice
      u.uTear.value = g.tear
      u.uRgb.value = g.rgb * dpr
      u.uBlocks.value = g.blocks
      u.uScan.value = g.scan
      u.uGlassOn.value = glass ? glass.strength : 0
      if (glass) u.uGlass.value.fromArray(glass.rect)
      u.uRadius.value = 8 * dpr
      u.uBevel.value = 16 * dpr
      u.uBlur.value = 3 * dpr
      renderer.setRenderTarget(target)
      renderer.clear()
      renderer.render(scene, camera)
      renderer.setRenderTarget(null)
      renderer.render(quadScene, quadCamera)
    },
    dispose() {
      target.dispose()
      material.dispose()
      quad.geometry.dispose()
    },
  }
}
