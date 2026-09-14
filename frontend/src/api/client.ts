import axios from 'axios'

export const TOKEN_KEY = 'wbcms_token'

export const api = axios.create({ baseURL: '' })

api.interceptors.request.use((cfg) => {
  try {
    const t = localStorage.getItem(TOKEN_KEY)
    if (t) cfg.headers.Authorization = `Bearer ${t}`
  } catch { /* noop */ }
  return cfg
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401 && !String(err?.config?.url || '').includes('/api/auth/')) {
      try { localStorage.removeItem(TOKEN_KEY) } catch { /* noop */ }
      if (!location.pathname.startsWith('/login')) location.href = '/login'
    }
    return Promise.reject(err)
  },
)
