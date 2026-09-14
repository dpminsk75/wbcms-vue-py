import { api, TOKEN_KEY } from './client'

export interface AuthUser { id: number; username: string; email?: string }

export const authApi = {
  login: (username: string, password: string) =>
    api.post('/api/auth/login', { username, password }).then((r) => r.data as { token: string; user: AuthUser; roles: string[]; perms: string[] }),
  me: () => api.get('/api/auth/me').then((r) => r.data as { user: AuthUser; roles: string[]; perms: string[] }),
  companies: () => api.get('/api/companies').then((r) => r.data as { id: number; name: string }[]),
}
