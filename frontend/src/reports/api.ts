import { request } from '../lib/api'
import type { Movement, Page } from '../finance/api'
import type { Slice, Point } from '../analytics/api'

export interface FinancialReport {
  income: string; expense: string; net_flow: string; start: string; end_exclusive: string; generated_at: string; timezone: string; note: string
  areas: Slice[]; categories: Slice[]; evolution: { points: Point[] }; movements: Page<Movement>
}
export interface AuditEvent {
  id: string; actor: string; operation: string; resource_type: string; resource_id: string; occurred_at: string; correlation_id: string
  before: Record<string, string | boolean | number | null>; after: Record<string, string | boolean | number | null>; changed_fields: string[]
}
export const preview = (query: string, signal?: AbortSignal, send = request) => send<FinancialReport>(`/reports/preview/?${query}`, { private: true, signal })
export async function exportReport(format: 'xlsx' | 'csv' | 'pdf', query: string, send = request) {
  const blob = await send<Blob>(`/reports/export/${format}/?${query}`, { private: true, responseType: 'blob' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url; link.download = `controlgastos-reporte.${format}`
  document.body.appendChild(link); link.click(); link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
