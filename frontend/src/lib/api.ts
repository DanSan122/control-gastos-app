export interface User {
  id: string
  email: string
  first_name: string
  last_name: string
  date_joined: string
  is_active: boolean
  timezone: string
  currency: 'PEN' | 'USD' | 'EUR'
}

export interface HealthResponse { status: 'ok'; service: 'controlgastos-api'; version: 'v1' }

export class ApiError extends Error {
  constructor(public status: number, public fields: Record<string, string[]>, message: string) { super(message) }
}

const baseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace(/\/$/, '')

export async function request<T>(path: string, options: {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'; data?: unknown; signal?: AbortSignal; private?: boolean; headers?: Record<string, string>; responseType?: 'blob'
} = {}): Promise<T> {
  const method = options.method || 'GET'
  const headers: Record<string, string> = { Accept: 'application/json', ...options.headers }
  if (method !== 'GET') {
    // Token en memoria de esta petición; la cookie CSRF también es HttpOnly.
    const bootstrap = await request<{ csrfToken: string }>('/auth/csrf/')
    headers['X-CSRFToken'] = bootstrap.csrfToken
    headers['Content-Type'] = 'application/json'
  }
  const controller = new AbortController()
  const abort = () => controller.abort()
  options.signal?.addEventListener('abort', abort, { once: true })
  if (options.signal?.aborted) controller.abort()
  const timeout = window.setTimeout(abort, 15000)
  try {
    const response = await fetch(`${baseUrl}${path}`, {
      method, headers, credentials: 'include', cache: 'no-store', signal: controller.signal,
      ...(options.data !== undefined ? { body: JSON.stringify(options.data) } : {}),
    })
    if (response.status === 204) return undefined as T
    if (response.ok && options.responseType === 'blob') return await response.blob() as T
    const data: unknown = await response.json()
    if (!response.ok) {
      const fields: Record<string, string[]> = {}
      if (typeof data === 'object' && data !== null) {
        for (const [key, value] of Object.entries(data)) {
          fields[key] = Array.isArray(value) ? value.map(String) : [String(value)]
        }
      }
      const detail = fields.detail?.join(' ') || ''
      if (options.private && (response.status === 401 || (response.status === 403 && !detail.startsWith('CSRF')))) {
        window.dispatchEvent(new Event('session-expired'))
      }
      const message = response.status === 429
        ? `Demasiados intentos. Vuelve a intentarlo en ${Math.max(1, Math.ceil(Number(response.headers.get('Retry-After') || 60) / 60))} minutos.`
        : detail.startsWith('CSRF') ? 'La verificación de seguridad falló. Recarga la página y vuelve a intentarlo.'
          : detail || 'Revisa los campos indicados.'
      throw new ApiError(response.status, fields, message)
    }
    return data as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new Error('No se pudo conectar con el servidor. Comprueba tu conexión y vuelve a intentarlo.')
  } finally {
    window.clearTimeout(timeout)
    options.signal?.removeEventListener('abort', abort)
  }
}

export const api = {
  me: (signal?: AbortSignal) => request<User>('/auth/me/', { signal, private: true }),
  register: (data: { email: string; password: string; first_name: string; last_name: string }) =>
    request<User>('/auth/register/', { method: 'POST', data }),
  login: (data: { email: string; password: string }) =>
    request<{ user: User; csrfToken: string }>('/auth/login/', { method: 'POST', data }),
  logout: () => request<void>('/auth/logout/', { method: 'POST', private: true }),
  profile: (data: Pick<User, 'first_name' | 'last_name' | 'timezone' | 'currency'>) =>
    request<User>('/users/me/', { method: 'PATCH', data, private: true }),
  changePassword: (data: { current_password: string; new_password: string }) =>
    request<{ detail: string; csrfToken: string }>('/auth/change-password/', { method: 'POST', data, private: true }),
}

export const getHealth = (signal: AbortSignal) => request<HealthResponse>('/health/', { signal })
