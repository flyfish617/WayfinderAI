import axios from 'axios'
import type {
  AuthResponse,
  ChangePasswordRequest,
  LoginRequest,
  RegisterRequest,
  TripPlanRequest,
  TripPlanResponse,
  UpdateProfileRequest,
  User,
} from '@/types'
import { isTokenExpired } from '@/utils/auth'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 300000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

function clearStoredAuth() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('user_info')
}

apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')

    if (token && !isTokenExpired(token)) {
      config.headers.Authorization = `Bearer ${token}`
    } else {
      if (token) {
        clearStoredAuth()
      }

      const guestSessionId = localStorage.getItem('guest_session_id')
      if (guestSessionId) {
        config.headers['X-Guest-Session'] = guestSessionId
      }
    }

    return config
  },
  (error) => Promise.reject(error),
)

let isLoggingOut = false

apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (isLoggingOut) {
      return Promise.reject(error)
    }

    const responseData = error.response?.data
    const errorMessage =
      responseData?.error_message || responseData?.detail || error.message || '请求失败'

    if (error.response?.status === 401) {
      console.error('认证失败 (401):', {
        url: error.config?.url,
        method: error.config?.method,
        message: errorMessage,
        timestamp: new Date().toISOString(),
      })

      const isAuthAPI = error.config?.url?.includes('/auth/')
      if (!isAuthAPI) {
        isLoggingOut = true
        clearStoredAuth()
        console.warn('认证已失效，本地登录状态已清除')

        setTimeout(() => {
          window.location.href = '/login'
          isLoggingOut = false
        }, 100)
      }
    }

    console.error('API请求失败:', {
      url: error.config?.url,
      status: error.response?.status,
      message: errorMessage,
      timestamp: new Date().toISOString(),
    })

    return Promise.reject(new Error(errorMessage))
  },
)

export const authApi = {
  async login(data: LoginRequest): Promise<AuthResponse> {
    return apiClient.post('/api/v1/auth/login', data)
  },

  async register(data: RegisterRequest): Promise<AuthResponse> {
    return apiClient.post('/api/v1/auth/register', data)
  },

  async getCurrentUser(): Promise<User> {
    return apiClient.get('/api/v1/auth/me')
  },

  async updateProfile(data: UpdateProfileRequest): Promise<User> {
    return apiClient.put('/api/v1/auth/me', data)
  },

  async changePassword(data: ChangePasswordRequest): Promise<{ message: string }> {
    return apiClient.post('/api/v1/auth/change-password', data)
  },

  async uploadAvatar(file: File): Promise<{ url: string }> {
    const formData = new FormData()
    formData.append('file', file)

    return apiClient.post('/api/v1/auth/upload-avatar', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total) {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          console.log(`上传进度: ${percentCompleted}%`)
        }
      },
    })
  },

  async logout(): Promise<{ message: string }> {
    return apiClient.post('/api/v1/auth/logout')
  },

  async createGuestSession(): Promise<{
    user_id: string
    guest_session_id?: string
    user_type: 'guest' | 'registered'
    message: string
  }> {
    const resp = await apiClient.post<
      { user_id: string; guest_session_id?: string; user_type: 'guest' | 'registered'; message: string },
      { user_id: string; guest_session_id?: string; user_type: 'guest' | 'registered'; message: string }
    >('/api/v1/auth/guest')

    if (resp?.user_type === 'guest' && resp?.guest_session_id) {
      localStorage.setItem('guest_session_id', resp.guest_session_id)
    }

    return resp
  },
}

export const tripApi = {
  async createTripPlan(request: TripPlanRequest, cancelToken?: any): Promise<TripPlanResponse> {
    return apiClient.post('/api/v1/trips/plan', request, { cancelToken })
  },

  async createTripPlanTask(
    request: TripPlanRequest,
  ): Promise<{ task_id: string; status: string; message: string }> {
    return apiClient.post('/api/v1/trips/plan-async', request)
  },

  async getTripTask(taskId: string): Promise<{
    task_id: string
    status: 'pending' | 'running' | 'succeeded' | 'failed'
    progress: number
    message: string
    result_trip_id?: string | null
    error?: string | null
    city_support_level?: string | null
    city_support_message?: string | null
    updated_at?: string
  }> {
    return apiClient.get(`/api/v1/trips/tasks/${taskId}`)
  },

  async getTripsList(): Promise<TripPlanResponse[]> {
    return apiClient.get('/api/v1/trips/list')
  },

  async getTripDetail(tripId: string): Promise<TripPlanResponse> {
    return apiClient.get(`/api/v1/trips/${tripId}`)
  },

  async deleteTrip(tripId: string): Promise<{ message: string }> {
    return apiClient.delete(`/api/v1/trips/${tripId}`)
  },

  async updateTrip(tripId: string, tripData: TripPlanResponse): Promise<TripPlanResponse> {
    return apiClient.put(`/api/v1/trips/${tripId}`, tripData)
  },

  async updateTripWithVersion(
    tripId: string,
    tripData: TripPlanResponse,
    expectedVersion?: number,
  ): Promise<TripPlanResponse> {
    return apiClient.put(`/api/v1/trips/${tripId}`, tripData, {
      headers: expectedVersion != null ? { 'If-Match-Version': String(expectedVersion) } : {},
    })
  },

  async getTripVersions(tripId: string): Promise<{
    trip_id: string
    versions: Array<{ version: number; snapshot_at: string; trip_title: string }>
  }> {
    return apiClient.get(`/api/v1/trips/${tripId}/versions`)
  },

  async rollbackTrip(tripId: string, targetVersion: number): Promise<TripPlanResponse> {
    return apiClient.post(`/api/v1/trips/${tripId}/rollback`, null, {
      params: { target_version: targetVersion },
    })
  },

  async listCitySupport(): Promise<{ count: number; cities: string[] }> {
    return apiClient.get('/api/v1/trips/city-support')
  },

  async healthCheck(): Promise<{ status: string }> {
    return apiClient.get('/health')
  },
}

export default apiClient
