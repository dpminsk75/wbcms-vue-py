import { api, TOKEN_KEY } from './client'

export interface AuthUser { id: number; username: string; email?: string }

export interface Company { id: number; name: string; abbreviation?: string | null; inn?: string | null }
export interface CompanyMember { id: number; username: string; email?: string; role: 'owner' | 'admin' | 'member' | 'viewer'; status: 'active' | 'blocked' | 'invited'; invited_by?: number | null }

export interface InviteCreateCompany { company_name: string; abbreviation?: string; inn?: string; expires_in_days?: number }
export interface InviteCreateUser { company_id: number; email: string; role?: 'admin' | 'member'; expires_in_days?: number }
export type InviteCreate = InviteCreateCompany | InviteCreateUser

export interface WbTokenCategory { key: string; bit: number; letter: string; name: string; in_token: boolean }
export interface WbTokenPing { http: number | null; ok: boolean; ms: number | null; skipped?: boolean; no_jam?: boolean; error?: string }
export interface WbTokenState {
  has_token: boolean; source?: 'saved' | 'draft'; valid?: boolean; error?: string;
  token_id?: string | null; sid?: string | null; exp_at?: string | null;
  days_left?: number | null; expired?: boolean; s_mask?: number;
  is_test?: boolean; is_readonly?: boolean;
  token_type?: 'basic' | 'test' | 'personal' | 'service' | 'unknown'; token_type_ru?: string;
  acc?: number | null; for?: string | null;
  categories?: WbTokenCategory[]; ping?: Record<string, WbTokenPing> | null; checked_at?: string;
  profile?: Record<string, any> | null; profile_saved?: boolean;
}
export interface WbProfile {
  has_profile: boolean; company_id?: number; sid?: string | null; seller_name?: string | null;
  tin?: string | null; trademark?: string | null;
  seller_info?: Record<string, any> | null; rating?: number | null; reviews_count?: number | null;
  has_jam?: boolean | null; jam?: Record<string, any> | null; tariffs?: {
    activeOptionCount?: number; activePackageCount?: number; totalCommissionRate?: number;
    packages?: Array<{ slug?: string; name?: string; status?: string; periodDuration?: number; commissionRate?: number; activatedAt?: string; expiresAt?: string; options?: Array<{ slug?: string; name?: string }> }>;
    options?: Array<{ slug?: string; name?: string; status?: string; periodDuration?: number; commissionRate?: number; activatedAt?: string; expiresAt?: string }>;
  } | null;
  fetched_at?: string | null; last_error?: string | null;
}

export const WB_TOKEN_CATS: Array<{ key: string; letter: string; name: string }> = [
  { key: 'content', letter: 'К', name: 'Контент' },
  { key: 'analytics', letter: 'А', name: 'Аналитика' },
  { key: 'prices', letter: 'Ц', name: 'Цены и скидки' },
  { key: 'marketplace', letter: 'М', name: 'Маркетплейс' },
  { key: 'statistics', letter: 'С', name: 'Статистика' },
  { key: 'promotion', letter: 'П', name: 'Продвижение' },
  { key: 'feedbacks', letter: 'В', name: 'Вопросы и отзывы' },
  { key: 'recommendations', letter: 'Р', name: 'Рекомендации' },
  { key: 'chat', letter: 'Ч', name: 'Чат с покупателями' },
  { key: 'supplies', letter: 'Пс', name: 'Поставки' },
  { key: 'returns', letter: 'Вз', name: 'Возвраты покупателями' },
  { key: 'documents', letter: 'Д', name: 'Документы' },
  { key: 'finance', letter: 'Ф', name: 'Финансы' },
  { key: 'users', letter: 'Пл', name: 'Пользователи' },
]

export const authApi = {
  login: (username: string, password: string) =>
    api.post('/api/auth/login', { username, password }).then((r) => r.data as { token: string; user: AuthUser; roles: string[]; perms: string[] }),
  me: () => api.get('/api/auth/me').then((r) => r.data as { user: AuthUser; roles: string[]; perms: string[] }),
  companies: () => api.get('/api/companies').then((r) => r.data as Company[]),

  register: (payload: { username: string; email: string; password: string; company_name?: string; abbreviation?: string; inn?: string; invite_token: string }) =>
    api.post('/api/auth/register', payload).then((r) => r.data as { token: string; user: AuthUser; company?: Company }),

  createInvite: (payload: InviteCreate) =>
    api.post('/api/auth/invites', payload).then((r) => r.data as { invite_token: string; expires_at: string; company?: Company }),

  inviteInfo: (token: string) =>
    api.get(`/api/auth/invites/${encodeURIComponent(token)}/info`).then((r) => r.data as { type: 'company' | 'user'; company_name?: string; company_id?: number; company?: Company; email_masked?: string; role?: string; expires_at?: string }),

  listInvites: () =>
    api.get('/api/auth/invites').then((r) => r.data as Array<{ id: number; token_type: 'company' | 'user'; company_id: number | null; company_label: string | null; target_email: string | null; role: string | null; company_name: string | null; expires_at: string; created_at: string; used_at: string | null; created_by: number | null; created_by_name: string | null; status: 'active' | 'used' | 'expired' }>),

  inviteLink: (id: number) =>
    api.get(`/api/auth/invites/by-id/${id}/link`).then((r) => r.data as { invite_token: string; register_path: string }),

  updateCompany: (companyId: number, payload: { name?: string; abbreviation?: string; inn?: string; api_key?: string }) =>
    api.patch(`/api/companies/${companyId}`, payload).then((r) => r.data as Company),

  createCompany: (payload: { name: string; abbreviation?: string; inn?: string; seo_model?: string; seo_daily_limit?: number; seo_desc_min?: number; seo_desc_max?: number; seo_anti_spam_days?: number }) =>
    api.post('/api/companies', payload).then((r) => r.data as Company),

  getCompanyMembers: (companyId: number) =>
    api.get(`/api/companies/${companyId}/members`).then((r) => r.data as { company: Company; members: CompanyMember[] }),

  getCompany: (companyId: number) =>
    api.get(`/api/companies/${companyId}`).then((r) => r.data as Record<string, any>),

  inviteMember: (companyId: number, payload: { email: string; role?: 'admin' | 'member' | 'viewer'; perms?: string[] }) =>
    api.post(`/api/companies/${companyId}/members`, payload).then((r) => r.data as { invite_token: string; expires_at: string; company: Company; member: CompanyMember & { user: AuthUser } }),
  memberPerms: (companyId: number, userId: number, payload: { add?: string[]; remove?: string[] }) =>
    api.patch(`/api/companies/${companyId}/members/${userId}/perms`, payload).then((r) => r.data as { company_id: number; id: number; perms: string[] }),
  grantablePerms: () =>
    api.get('/api/auth/grantable-perms').then((r) => r.data as Array<{ name: string; description: string | null }>),
  rbacItems: () =>
    api.get('/api/admin/rbac-items').then((r) => r.data as Array<{ name: string; type: number; description: string | null }>),
  setUserRoles: (userId: number, payload: { add?: string[]; remove?: string[] }) =>
    api.post(`/api/admin/users/${userId}/roles`, payload).then((r) => r.data as { id: number; items: Array<{ name: string; type: number | null; description: string | null }> }),
  adminCreateUser: (payload: { username: string; email: string; password: string; company_id?: number; role?: 'member' | 'viewer' | 'admin'; perms?: string[] }) =>
    api.post('/api/admin/users', payload).then((r) => r.data as { user: AuthUser; company: Company | null; role: string | null; perms: string[] }),

  updateMember: (companyId: number, userId: number, payload: { role: 'owner' | 'admin' | 'member' | 'viewer'; status?: 'active' | 'blocked' | 'invited' }) =>
    api.patch(`/api/companies/${companyId}/members/${userId}`, payload).then((r) => r.data),

  deleteMember: (companyId: number, userId: number) =>
    api.delete(`/api/companies/${companyId}/members/${userId}`).then((r) => r.data),

  adminUsers: () => api.get('/api/admin/users').then((r) => r.data as Array<{ id: number; username: string; email: string; blocked: boolean; companies: Array<{ company_id: number; company_name: string; role: string; status: string }> }>),
  setUserBlocked: (userId: number, blocked: boolean) =>
    api.patch(`/api/admin/users/${userId}/blocked`, blocked).then((r) => r.data),
  setUserPasswordAdmin: (userId: number, password: string) =>
    api.patch(`/api/admin/users/${userId}/password`, { password }).then((r) => r.data),
  setMemberPassword: (companyId: number, userId: number, password: string) =>
    api.patch(`/api/companies/${companyId}/members/${userId}/password`, { password }).then((r) => r.data),
  memberships: () =>
    api.get('/api/auth/memberships').then((r) => r.data as Array<{ company_id: number; company_name: string; role: string; status: string }>),
  wbTokenStatus: (companyId: number) =>
    api.get(`/api/companies/${companyId}/wb-token/status`).then((r) => r.data as WbTokenState),
  wbTokenCheck: (companyId: number, apiKey?: string) =>
    api.post(`/api/companies/${companyId}/wb-token/check`, apiKey ? { api_key: apiKey } : {}).then((r) => r.data as WbTokenState),
  wbTokensExpiring: (days = 14) =>
    api.get('/api/wb-tokens/expiring', { params: { days } }).then((r) => r.data as Array<{ company_id: number; company_name: string; exp_at: string; days_left: number; is_readonly: boolean; last_check_at: string | null }>),
  wbTokenProfile: (companyId: number) =>
    api.get(`/api/companies/${companyId}/wb-token/profile`).then((r) => r.data as WbProfile),
  wbTokenProfileRefresh: (companyId: number, apiKey?: string) =>
    api.post(`/api/companies/${companyId}/wb-token/profile/refresh`, apiKey ? { api_key: apiKey } : {}).then((r) => r.data as { profile: Record<string, any>; profile_saved: boolean; source: string }),
  adminCompanies: () => api.get('/api/admin/companies').then((r) => r.data as Array<Company & { is_active: boolean; members_count: number }>),
  setCompanyActive: (companyId: number, isActive: boolean) =>
    api.patch(`/api/admin/companies/${companyId}/active`, { is_active: isActive }).then((r) => r.data),
}