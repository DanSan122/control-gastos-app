import { request } from '../lib/api'
import type { Account, Movement } from '../finance/api'

export interface Tick { value: number; label: string }
export interface Point { date: string; income: string; expense: string; net_flow: string; accumulated: string; income_plot: number; expense_plot: number; net_flow_plot: number; accumulated_plot: number }
export interface Slice { id: string; name: string; amount: string; weight: number }
export interface ComparisonPoint { name: string; current: string; previous: string; current_plot: number; previous_plot: number; change: { percent: string | null; status: string } }
export interface Progress { consumed: string; available: string; used_percent: string; bar_percent: number; alert: 'NORMAL' | 'WARNING' | 'EXCEEDED' | 'INACTIVE'; scope_name: string }
export interface Budget { id: string; area: string | null; category: string | null; limit_amount: string; currency: string; year: number; month: number; is_active: boolean; progress: Progress }
export interface Analytics {
  recent_movements?: Movement[]
  start: string; end_exclusive: string; timezone: string; income: string; expense: string; net_flow: string
  asset_balances: string; credit_debt: string; net_worth: string; average_daily_expense: string; days: number
  top_category: Slice | null; accounts: Account[]; areas: Slice[]; categories: Slice[]
  evolution: { points: Point[]; ticks: Tick[] }
  comparison: { start: string; end_exclusive: string; criterion: string; points: ComparisonPoint[]; ticks: Tick[] }
  budget_alerts: (Progress & { id: string })[]
}
export const getAnalytics = (section: string, query: string, signal?: AbortSignal, send = request) => send<Analytics>(`/analytics/${section}/?${query}`, { private: true, signal })
