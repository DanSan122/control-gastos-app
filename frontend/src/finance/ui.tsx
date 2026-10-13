import { useEffect, useState, type ReactNode, type SelectHTMLAttributes } from 'react'
import { feedbackFrom, type FormFeedback } from '../components/Form'

export function useResource<T>(loader: (signal: AbortSignal) => Promise<T>, dependencies: unknown[] = []) {
  const [data, setData] = useState<T>()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    let active = true
    setLoading(true); setError('')
    loader(controller.signal).then((value) => { if (active) setData(value) })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : 'No se pudo cargar la información.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false; controller.abort() }
    // Los consumidores proporcionan dependencias primitivas que definen su consulta.
  }, [...dependencies, revision])
  return { data, loading, error, reload: () => setRevision((value) => value + 1) }
}
export function LoadState({ loading, error, retry }: { loading: boolean; error: string; retry: () => void }) {
  if (loading) return <p role="status" className="py-6 text-slate-500">Cargando información…</p>
  if (error) return <div role="alert" className="card mb-6 border-red-200"><p>{error}</p><button className="button-secondary mt-3" onClick={retry}>Reintentar</button></div>
  return null
}
export function FinanceFeedback({ error, success }: { error?: FormFeedback; success?: string }) {
  const messages = error ? Object.entries(error.fields).filter(([name]) => name !== 'detail').flatMap(([name, values]) => values.map((value) => `${name}: ${value}`)) : []
  return <>
    {error ? <div role="alert" className="rounded-xl bg-red-50 p-4 text-sm text-red-800"><p>{error.message}</p>{messages.length ? <ul className="mt-2 list-disc pl-5">{messages.map((message, index) => <li key={index}>{message}</li>)}</ul> : null}</div> : null}
    {success ? <p role="status" className="rounded-xl bg-emerald-50 p-4 text-sm text-emerald-800">{success}</p> : null}
  </>
}
export function Select({ label, children, ...props }: SelectHTMLAttributes<HTMLSelectElement> & { label: string }) {
  const id = props.name || label
  return <div className="space-y-2"><label htmlFor={id} className="block text-sm font-medium text-slate-700">{label}</label><select {...props} id={id} className="input">{children}</select></div>
}
export interface Period { period: 'day' | 'yesterday' | 'week' | 'previous_week' | 'month' | 'previous_month' | 'year' | 'custom'; start: string; end: string }
export const initialPeriod: Period = { period: 'month', start: '', end: '' }
export function periodQuery(value: Period) {
  const params = new URLSearchParams({ period: value.period })
  if (value.period === 'custom') { params.set('start', value.start); params.set('end', value.end) }
  return params.toString()
}
export function PeriodPicker({ value, onChange }: { value: Period; onChange: (value: Period) => void }) {
  return <fieldset className="flex flex-wrap items-end gap-3"><legend className="mb-2 text-sm text-slate-500">Periodo en tu zona horaria</legend>
    <Select label="Periodo" name="period" value={value.period} onChange={(event) => onChange({ ...value, period: event.target.value as Period['period'] })}>
      <option value="day">Hoy</option><option value="yesterday">Ayer</option><option value="week">Esta semana</option><option value="previous_week">Semana anterior</option><option value="month">Este mes</option><option value="previous_month">Mes anterior</option><option value="year">Este año</option><option value="custom">Rango personalizado</option>
    </Select>
    {value.period === 'custom' ? <><label className="text-sm">Desde<input aria-label="Desde" className="input mt-2" type="date" value={value.start} onChange={(event) => onChange({ ...value, start: event.target.value })} /></label>
      <label className="text-sm">Hasta<input aria-label="Hasta" className="input mt-2" type="date" value={value.end} onChange={(event) => onChange({ ...value, end: event.target.value })} /></label></> : null}
  </fieldset>
}
export function PageHeader({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return <div className="mb-8"><p className="eyebrow">{eyebrow}</p><h1 className="page-title mt-3">{title}</h1>{children ? <p className="mt-3 text-slate-500">{children}</p> : null}</div>
}
export { feedbackFrom }
