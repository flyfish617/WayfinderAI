import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User } from '@/types'
import { authApi } from '@/services/api'
import { getTokenExpiryMs, isTokenExpired } from '@/utils/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(null)
  const user = ref<User | null>(null)
  const expiresAt = ref<number | null>(null)
  let expiryTimer: number | null = null

  const isAuthenticated = computed(() => {
    return !!token.value && !!user.value && !!expiresAt.value && expiresAt.value > Date.now()
  })
  const userId = computed(() => user.value?.user_id || null)
  const username = computed(() => user.value?.username || '')

  const stopExpiryTimer = () => {
    if (expiryTimer !== null) {
      window.clearTimeout(expiryTimer)
      expiryTimer = null
    }
  }

  const clearPersistedAuth = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_info')
  }

  const clearAuth = () => {
    stopExpiryTimer()
    token.value = null
    user.value = null
    expiresAt.value = null
    clearPersistedAuth()
    localStorage.removeItem('guest_session_id')
  }

  const scheduleExpiryTimer = (accessToken: string | null) => {
    stopExpiryTimer()
    expiresAt.value = getTokenExpiryMs(accessToken)

    if (!accessToken || !expiresAt.value) {
      return
    }

    const remainingMs = expiresAt.value - Date.now()
    if (remainingMs <= 0) {
      clearAuth()
      return
    }

    expiryTimer = window.setTimeout(() => {
      clearAuth()
    }, remainingMs)
  }

  const setAuth = (accessToken: string, userInfo: User) => {
    if (isTokenExpired(accessToken)) {
      clearAuth()
      return
    }

    token.value = accessToken
    user.value = userInfo
    localStorage.setItem('access_token', accessToken)
    localStorage.setItem('user_info', JSON.stringify(userInfo))
    localStorage.removeItem('guest_session_id')
    scheduleExpiryTimer(accessToken)
  }

  const logout = async () => {
    try {
      try {
        await authApi.logout()
      } catch (apiError) {
        console.error('Backend logout API failed:', apiError)
      }
    } finally {
      clearAuth()
    }
  }

  const restoreAuth = () => {
    try {
      const savedToken = localStorage.getItem('access_token')
      const savedUserInfo = localStorage.getItem('user_info')

      if (!savedToken || !savedUserInfo || isTokenExpired(savedToken)) {
        clearAuth()
        return
      }

      token.value = savedToken
      user.value = JSON.parse(savedUserInfo)
      scheduleExpiryTimer(savedToken)
    } catch (error) {
      console.error('Failed to restore auth state:', error)
      clearAuth()
    }
  }

  const updateUser = (updatedUser: Partial<User>) => {
    if (user.value) {
      user.value = { ...user.value, ...updatedUser }
      localStorage.setItem('user_info', JSON.stringify(user.value))
    }
  }

  restoreAuth()

  return {
    token,
    user,
    expiresAt,
    isAuthenticated,
    userId,
    username,
    setAuth,
    logout,
    clearAuth,
    restoreAuth,
    updateUser,
  }
})
