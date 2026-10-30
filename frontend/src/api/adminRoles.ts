import { api } from './client'

export interface PermMeta {
  name: string
  label?: string
  kind?: 'view' | 'manage' | string
  requires?: string | null
  protected?: boolean
  derivedOnly?: boolean
}

export interface RoleUser { id: number; username: string }

export interface Role {
  id: number
  name: string
  description: string | null
  is_system: number
  created_at?: string
  perms: string[]
  users?: RoleUser[]
}

export const adminRolesApi = {
  perms: () => api.get('/api/admin/perms').then((r) => r.data as PermMeta[]),
  list: () => api.get('/api/admin/roles').then((r) => r.data as Role[]),
  create: (payload: { name: string; description?: string | null; perms?: string[] }) =>
    api.post('/api/admin/roles', payload).then((r) => r.data as Role),
  update: (id: number, payload: { name?: string; description?: string | null }) =>
    api.patch(`/api/admin/roles/${id}`, payload).then((r) => r.data as Role),
  setPerms: (id: number, perms: string[]) =>
    api.put(`/api/admin/roles/${id}/perms`, { perms }).then((r) => r.data as { id: number; perms: string[] }),
  remove: (id: number) => api.delete(`/api/admin/roles/${id}`).then((r) => r.data),
  setUserRoles: (userId: number, payload: { add?: string[]; remove?: string[] }) =>
    api.post(`/api/admin/users/${userId}/v3-roles`, payload).then((r) => r.data as { id: number; roles: string[] }),
}
