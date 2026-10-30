import { createContext, ReactNode, useContext, useMemo, useState } from 'react'
import { api } from '../services/api'
import { User } from '../types'

type AuthValue = { user: User | null; loading: boolean; login: (username: string, password: string) => Promise<void>; register: (data: Record<string,string>) => Promise<User>; logout: () => Promise<void>; setUser: (user: User) => void }
const AuthContext = createContext<AuthValue | null>(null)
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<User | null>(() => { try { return JSON.parse(localStorage.getItem('user') || 'null') } catch { return null } })
  const setUser = (value: User) => { setUserState(value); localStorage.setItem('user', JSON.stringify(value)) }
  const login = async (username: string, password: string) => {
    const { data } = await api.post('/auth/login/', { username, password })
    localStorage.setItem('access', data.access); localStorage.setItem('refresh', data.refresh); setUser(data.user)
  }
  const register = async (payload: Record<string,string>) => (await api.post('/auth/register/', payload)).data.user as User
  const logout = async () => {
    const refresh = localStorage.getItem('refresh')
    try { if (refresh) await api.post('/auth/logout/', { refresh }) } finally {
      localStorage.removeItem('access'); localStorage.removeItem('refresh'); localStorage.removeItem('user'); setUserState(null)
    }
  }
  const value = useMemo(() => ({ user, loading: false, login, register, logout, setUser }), [user])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
export function useAuth() { const value = useContext(AuthContext); if (!value) throw new Error('useAuth must be inside AuthProvider'); return value }
