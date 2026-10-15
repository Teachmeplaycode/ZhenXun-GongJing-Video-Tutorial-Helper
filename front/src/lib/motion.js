// Motion constants (design_2.md §12). Every tween must pick a duration + easing from here.
export const DUR = { micro: 0.2, short: 0.4, medium: 0.8, long: 1.2, scene: 1.6 }
export const EASE = { enter: 'power2.out', exit: 'power2.in', move: 'power2.inOut', bounce: 'back.out(1.4)', expand: 'power4.inOut' }

export const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

// Coarse low-end heuristic used to cut sculpture sheets / contour density.
export const isLowEndDevice = () => {
  const cores = navigator.hardwareConcurrency || 4
  const memory = navigator.deviceMemory || 8
  return cores <= 4 || memory <= 4
}
