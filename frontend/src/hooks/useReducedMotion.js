import { useSyncExternalStore } from 'react'

const query = '(prefers-reduced-motion: reduce)'
const subscribe = (listener) => {
  const media = window.matchMedia?.(query)
  media?.addEventListener('change', listener)
  return () => media?.removeEventListener('change', listener)
}
const getSnapshot = () => window.matchMedia?.(query).matches ?? false

export function useReducedMotion() {
  return useSyncExternalStore(subscribe, getSnapshot, () => false)
}
