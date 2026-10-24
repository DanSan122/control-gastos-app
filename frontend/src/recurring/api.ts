import { request } from '../lib/api'
import type { Kind, Page } from '../finance/api'

export interface Rule {
  id: string
  name: string
  kind: Kind
  amount: string
  source_account: string
  destination_account: string | null
  source_name: string
  destination_name: string | null
  area: string | null
  category: string | null
  subcategory: string | null
  payment_method: string
  frequency: 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'YEARLY'
  interval: number
  start_date: string
  end_date: string | null
  next_due_date: string | null
  timezone: string
  execution_mode: 'AUTOMATIC' | 'MANUAL'
  status: 'ACTIVE' | 'PAUSED' | 'COMPLETED' | 'CANCELLED'
  calendar_locked: boolean
}
export interface Execution {
  id: string
  rule: string
  rule_name: string
  scheduled_date: string
  status: 'PENDING' | 'EXECUTED' | 'FAILED' | 'SKIPPED'
  transaction: string | null
  error_code: string
  kind: Kind
  amount: string
  execution_mode: Rule['execution_mode']
  rule_status: Rule['status']
  timezone: string
}
export interface UpcomingPage extends Page<Execution> {
  scheduled_totals: { income: string; expense: string; transfer: string }
}
export const recurring = {
  upcoming: (signal?: AbortSignal, compact = false, page = 1) =>
    request<UpcomingPage>(
      `/recurring/upcoming/?days=30&page_size=${compact ? 5 : 25}&page=${page}`,
      { private: true, signal },
    ),
  action: <T>(resource: 'rules' | 'executions', id: string, action: string) =>
    request<T>(`/recurring/${resource}/${id}/${action}/`, {
      method: 'POST',
      data: {},
      private: true,
    }),
}
export const frequencyLabel = {
  DAILY: 'Diaria',
  WEEKLY: 'Semanal',
  MONTHLY: 'Mensual',
  YEARLY: 'Anual',
}
export const statusLabel: Record<string, string> = {
  ACTIVE: 'Activa',
  PAUSED: 'Pausada',
  COMPLETED: 'Finalizada',
  CANCELLED: 'Cancelada',
  PENDING: 'Pendiente',
  EXECUTED: 'Ejecutada',
  FAILED: 'Fallida',
  SKIPPED: 'Omitida',
}
