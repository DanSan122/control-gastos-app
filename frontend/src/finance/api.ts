import { request } from '../lib/api'

export type Kind = 'INCOME' | 'EXPENSE' | 'TRANSFER'
export interface Account { id: string; name: string; kind: 'CASH' | 'BANK' | 'WALLET' | 'CREDIT' | 'OTHER'; institution: string; currency: string; initial_balance: string; balance: string; debt: string; is_active: boolean }
export interface Area { id: string; name: string; is_active: boolean }
export interface Category extends Area { area: string; kind: 'INCOME' | 'EXPENSE' }
export interface Subcategory extends Area { category: string }
export interface Movement {
  id: string; kind: Kind; account: string; account_name: string; destination_account: string | null; destination_name: string | null
  amount: string; currency: string; area: string | null; area_name: string | null; category: string | null; category_name: string | null
  subcategory: string | null; subcategory_name: string | null; description: string; occurred_at: string; created_at: string; updated_at: string
  payment_method: string; reference: string; status: 'POSTED' | 'VOID'
}
export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }
export interface Summary {
  income: string; expense: string; net_flow: string; asset_balances: string; credit_debt: string; net_worth: string; net_worth_at_period_end: string
  start: string; end_exclusive: string; timezone: string; currency: string; accounts: Account[]
  expenses_by_area: { id: string; name: string; amount: string }[]; expenses_by_category: { id: string; name: string; amount: string }[]
  evolution: Record<'daily' | 'weekly' | 'monthly', { date: string; income: string; expense: string; net: string }[]>
}
export const finance = {
  list: <T,>(resource: string, query = '', signal?: AbortSignal) => request<Page<T>>(`/${resource}/?${query}`, { private: true, signal }),
  all: async <T,>(resource: string, query = '', signal?: AbortSignal): Promise<T[]> => {
    const result: T[] = []
    let page = 1
    while (true) {
      const data = await finance.list<T>(resource, `${query}&page_size=100&page=${page}`, signal)
      result.push(...data.results)
      if (!data.next) return result
      page += 1
    }
  },
  get: <T,>(resource: string, id: string, signal?: AbortSignal) => request<T>(`/${resource}/${id}/`, { private: true, signal }),
  save: <T,>(resource: string, data: unknown, id?: string) => request<T>(`/${resource}/${id ? `${id}/` : ''}`, { method: id ? 'PATCH' : 'POST', data, private: true }),
  remove: (resource: string, id: string) => request<void>(`/${resource}/${id}/`, { method: 'DELETE', private: true }),
  transfer: (data: unknown, key: string) => request<Movement>('/transfers/', { method: 'POST', data, private: true, headers: { 'Idempotency-Key': key } }),
  summary: (query: string, signal?: AbortSignal) => request<Summary>(`/reports/summary/?${query}`, { private: true, signal }),
}

export function pen(value: string): string {
  const negative = value.startsWith('-')
  const [whole, fraction = '00'] = value.replace(/^-/, '').split('.')
  return `S/ ${negative ? '−' : ''}${new Intl.NumberFormat('es-PE', { maximumFractionDigits: 0 }).format(BigInt(whole || '0'))}.${fraction.padEnd(2, '0')}`
}
export const moneyInput = (value: FormDataEntryValue | null) => String(value || '0').trim().replace(',', '.')
export const kindLabel = (value: Kind) => ({ INCOME: 'Ingreso', EXPENSE: 'Gasto', TRANSFER: 'Transferencia' })[value]

export function localDateTime(iso: string, zone: string): string {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(new Date(iso))
  const part = (type: string) => parts.find((item) => item.type === type)?.value || ''
  return `${part('year')}-${part('month')}-${part('day')}T${part('hour')}:${part('minute')}`
}
export function localToIso(local: string, zone: string): string {
  const values = local.split(/[-T:]/).map(Number)
  const target = Date.UTC(values[0], values[1] - 1, values[2], values[3], values[4])
  let candidate = target
  for (let index = 0; index < 4; index++) {
    const shown = localDateTime(new Date(candidate).toISOString(), zone).split(/[-T:]/).map(Number)
    const represented = Date.UTC(shown[0], shown[1] - 1, shown[2], shown[3], shown[4])
    candidate += target - represented
  }
  if (localDateTime(new Date(candidate).toISOString(), zone) !== local) throw new Error('Esa hora no existe en tu zona horaria. Elige otra hora.')
  return new Date(candidate).toISOString()
}
