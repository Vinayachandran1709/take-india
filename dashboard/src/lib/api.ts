import axios from 'axios'

import { clearAccessToken, getAccessToken } from './auth'

export type ApiError = { error?: { code?: string; message?: string; details?: unknown } }

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1',
})

api.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) clearAccessToken()
    if (error.response?.data?.error?.code === 'subscription_required') {
      window.dispatchEvent(new Event('typein:subscription-required'))
      if (!window.location.pathname.startsWith('/dashboard/billing')) {
        window.location.assign('/dashboard')
      }
    }
    return Promise.reject(error)
  },
)

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiError>(error)) {
    return error.response?.data?.error?.message ?? 'Something went wrong.'
  }
  return 'Something went wrong.'
}
