import axios from 'axios'

export const TOKEN_KEY = 'wbcms_token'
export const COMPANY_KEY = 'wbcms_company'

export const api = axios.create({ baseURL: '' })

api.interceptors.request.use((cfg) => {
  let token = ''
  let company = ''
  try {
    token = localStorage.getItem(TOKEN_KEY) || ''
    if (token) cfg.headers.Authorization = `Bearer ${token}`
  } catch { /* noop */ }
  try {
    company = localStorage.getItem(COMPANY_KEY) || ''
    if (company && company !== 'all') cfg.headers['X-Company-Id'] = company
    else if (company === 'all') cfg.headers['X-Company-Id'] = 'all'
  } catch { /* noop */ }
  const short = token ? token.slice(-12) : '(empty)'
  console.debug('[api]', cfg.method?.toUpperCase(), cfg.url, 'token=' + short, 'company=' + (company || '(empty)'))
  return cfg
})

api.interceptors.response.use(
  (r) => {
    console.debug('[api]', r.config?.method?.toUpperCase(), r.config?.url, '->', r.status)
    return r
  },
  (err) => {
    const url = err?.config?.url || ''
    console.warn('[api]', err?.config?.method?.toUpperCase?.(), url, '->', err?.response?.status, err?.response?.data?.detail || '')
    if (err?.response?.status === 401 && !String(url).includes('/api/auth/')) {
      try { localStorage.removeItem(TOKEN_KEY) } catch { /* noop */ }
      if (!location.pathname.startsWith('/login')) location.href = '/login'
    }
    return Promise.reject(err)
  },
)
