import axios from 'axios'

/**
 * Pre-configured Axios instance.
 *
 * All API modules import this client — never call fetch/axios directly.
 * Base URL is read from the environment at build time.
 */
const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000',
  headers: { Accept: 'application/json' },
})

// Global response interceptor — logs errors in development.
apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (process.env.NODE_ENV === 'development') {
      console.error('[API Error]', error)
    }
    return Promise.reject(error)
  },
)

export default apiClient
