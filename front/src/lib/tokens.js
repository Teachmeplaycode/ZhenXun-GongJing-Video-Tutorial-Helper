// Read design tokens from CSS custom properties so JS-driven rendering (Three.js, canvas)
// never hardcodes colors.
export function token(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}
