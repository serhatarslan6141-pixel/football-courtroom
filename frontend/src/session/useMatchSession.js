import { useContext } from 'react'
import { MatchSessionContext } from './MatchSessionContext.js'

export function useMatchSession() {
  const session = useContext(MatchSessionContext)
  if (!session) throw new Error('useMatchSession requires a MatchSessionProvider')
  return session
}
