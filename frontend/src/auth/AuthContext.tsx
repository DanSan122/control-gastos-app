import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, ApiError, type User } from '../lib/api'

interface AuthState {
  user: User | null
  loading: boolean
  error: string
  setUser: (user: User | null) => void
  retry: () => void
}
const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    let active = true
    setLoading(true)
    setError('')
    api.me(controller.signal)
      .then((profile) => { if (active) setUser(profile) })
      .catch((reason: unknown) => {
        if (!active) return
        setUser(null)
        if (!(reason instanceof ApiError && [401, 403].includes(reason.status))) {
          setError(reason instanceof Error ? reason.message : 'No se pudo comprobar tu sesión.')
        }
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false; controller.abort() }
  }, [attempt])
  useEffect(() => {
    const expire = () => setUser(null)
    window.addEventListener('session-expired', expire)
    return () => window.removeEventListener('session-expired', expire)
  }, [])
  return <AuthContext.Provider value={{ user, loading, error, setUser, retry: () => setAttempt((value) => value + 1) }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('Se requiere AuthProvider.')
  return value
}
