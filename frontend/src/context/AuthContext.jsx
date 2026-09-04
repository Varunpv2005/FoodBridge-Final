import { createContext, useContext, useState, useEffect } from 'react'
import { api } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const handleUnauthorized = () => setUser(null)
    window.addEventListener('foodbridge:unauthorized', handleUnauthorized)
    const token = localStorage.getItem('fb_token')
    if (!token) {
      setLoading(false)
      return () => window.removeEventListener('foodbridge:unauthorized', handleUnauthorized)
    }
    api.me().then(setUser).catch(() => localStorage.removeItem('fb_token')).finally(() => setLoading(false))
    return () => window.removeEventListener('foodbridge:unauthorized', handleUnauthorized)
  }, [])

  const login = async (email, password) => {
    const res = await api.login({ email, password })
    localStorage.setItem('fb_token', res.access_token)
    setUser(res.user)
    return res.user
  }

  const register = async (payload) => {
    const res = await api.register(payload)
    localStorage.setItem('fb_token', res.access_token)
    setUser(res.user)
    return res.user
  }

  const logout = () => {
    localStorage.removeItem('fb_token')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, setUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
