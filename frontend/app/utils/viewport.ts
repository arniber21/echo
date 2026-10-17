/** Reveal an offscreen source after an explicit selection, without moving a visible player. */
export function revealIfOffscreen(element: HTMLElement): void {
  const bounds = element.getBoundingClientRect()
  if (bounds.bottom > 0 && bounds.top < window.innerHeight) return
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  element.scrollIntoView({ behavior: reducedMotion ? 'instant' : 'smooth', block: 'nearest' })
}
