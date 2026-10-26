import { useFinancialScope } from '../families/Scope'
import { useState, type FormEvent } from 'react'
import { useAuth } from '../auth/AuthContext'
import { moneyInput, pen, type Area, type Category } from '../finance/api'
import { PageHeader, Select, LoadState, useResource, FinanceFeedback, feedbackFrom } from '../finance/ui'
import type { FormFeedback } from '../components/Form'
import type { Budget } from './api'

export default function Budgets() {
  const { finance, family } = useFinancialScope()
  const { user } = useAuth()
  const localMonth = new Intl.DateTimeFormat('en-CA', { timeZone: (family?.timezone || user?.timezone), year: 'numeric', month: '2-digit' }).formatToParts(new Date())
  const part = (key: string) => localMonth.find((p) => p.type === key)?.value || ''
  const [period, setPeriod] = useState(`${part('year')}-${part('month')}`)
  const [page, setPage] = useState(1)
  const [edit, setEdit] = useState<Budget>()
  const [scope, setScope] = useState('area')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<FormFeedback>()
  const [success, setSuccess] = useState('')
  const [year, month] = period.split('-')
  const state = useResource((signal) => finance.list<Budget>('budgets', `year=${year}&month=${month}&page=${page}`, signal), [year, month, page])
  const choices = useResource(async (signal) => {
    const [areas, categories] = await Promise.all([finance.all<Area>('areas', 'active=true', signal), finance.all<Category>('categories', 'active=true&kind=EXPENSE', signal)])
    return { areas, categories }
  })
  const options = scope === 'area' ? choices.data?.areas : choices.data?.categories
  const editScope = edit ? (edit.area ? 'area' : 'category') : null
  const selectedId = edit?.area || edit?.category || ''
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(undefined); setSuccess(''); setSaving(true)
    const values = new FormData(event.currentTarget)
    const [budgetYear, budgetMonth] = String(values.get('period')).split('-')
    try {
      await finance.save<Budget>('budgets', { area: scope === 'area' ? values.get('scope') : null, category: scope === 'category' ? values.get('scope') : null, limit_amount: moneyInput(values.get('amount')), currency: 'PEN', year: Number(budgetYear), month: Number(budgetMonth), is_active: values.get('active') === 'on' }, edit?.id)
      setSuccess('Presupuesto guardado.'); setEdit(undefined); state.reload()
    } catch (reason) { setError(feedbackFrom(reason)) } finally { setSaving(false) }
  }
  async function deactivate(budget: Budget) {
    if (!window.confirm(`¿Desactivar el presupuesto de ${budget.progress.scope_name}? Se conservará su historial.`)) return
    setSaving(true); setError(undefined); setSuccess('')
    try { await finance.remove('budgets', budget.id); setSuccess('Presupuesto desactivado.'); state.reload() } catch (reason) { setError(feedbackFrom(reason)) } finally { setSaving(false) }
  }
  return <><PageHeader eyebrow="PLANIFICA TU MES" title="Presupuestos">Controla gastos por área o categoría. Las alertas se calculan al consultar, desde 80 % y 100 % del límite.</PageHeader><FinanceFeedback error={error} success={success} /><div className="mt-6 grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]"><section className="min-w-0"><label className="block text-sm font-medium">Mes consultado<input className="input mt-2 max-w-xs" type="month" min="1900-01" max="9998-12" value={period} onChange={(e) => { setPeriod(e.target.value); setPage(1) }} /></label><LoadState {...state} retry={state.reload} />{state.data && !state.loading && !state.error ? <><div className="mt-5 space-y-4">{state.data.results.map((budget) => <article key={budget.id} className="card"><div className="flex flex-wrap justify-between gap-2"><h2 className="font-semibold">{budget.progress.scope_name}</h2><span className="text-xs text-slate-500">{budget.area ? 'Área' : 'Categoría'} · {budget.is_active ? 'Activo' : 'Inactivo'}</span></div><p className="mt-4 text-sm">{pen(budget.progress.consumed)} de {pen(budget.limit_amount)} · {budget.progress.used_percent} %</p><div className="mt-3 h-3 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-label={`Uso de ${budget.progress.scope_name}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={budget.progress.bar_percent} aria-valuetext={`${budget.progress.used_percent} por ciento`}><div className={`h-full ${budget.progress.alert === 'EXCEEDED' ? 'bg-red-500' : budget.progress.alert === 'WARNING' ? 'bg-amber-500' : 'bg-emerald-500'}`} style={{ width: `${budget.progress.bar_percent}%` }} /></div><p className="mt-3 text-sm text-slate-500">Disponible: {pen(budget.progress.available)}</p>{budget.progress.alert === 'WARNING' || budget.progress.alert === 'EXCEEDED' ? <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm">{budget.progress.alert === 'WARNING' ? 'Alerta: has alcanzado el 80 %.' : 'Límite alcanzado o superado.'}</p> : null}<div className="mt-4 flex gap-3"><button disabled={saving || Boolean(family && family.role !== 'ADMIN')} className="button-secondary" onClick={() => { setEdit(budget); setScope(budget.area ? 'area' : 'category'); setError(undefined) }}>Editar</button>{budget.is_active ? <button disabled={saving || Boolean(family && family.role !== 'ADMIN')} className="text-sm text-red-700" onClick={() => void deactivate(budget)}>Desactivar</button> : null}</div></article>)}</div>{!state.data.results.length ? <p className="card mt-5 text-slate-500">No hay presupuestos para este mes.</p> : null}<div className="mt-5 flex items-center gap-4"><button className="button-secondary" disabled={!state.data.previous} onClick={() => setPage(page - 1)}>Anterior</button><span className="text-sm">Página {page}</span><button className="button-secondary" disabled={!state.data.next} onClick={() => setPage(page + 1)}>Siguiente</button></div></> : null}</section><form key={`${edit?.id || 'new'}-${scope}`} aria-label={edit ? 'Editar presupuesto' : 'Nuevo presupuesto'} className="card space-y-4" onSubmit={submit}><h2 className="text-lg font-semibold">{edit ? 'Editar presupuesto' : 'Nuevo presupuesto'}</h2><LoadState {...choices} retry={choices.reload} /><Select label="Alcance" value={scope} onChange={(e) => setScope(e.target.value)}><option value="area">Área</option><option value="category">Categoría</option></Select><Select label="Clasificación" name="scope" required defaultValue={scope === editScope ? selectedId : ''}><option value="">Selecciona una clasificación</option>{scope === editScope && selectedId && !options?.some((o) => o.id === selectedId) ? <option value={selectedId}>{edit?.progress.scope_name} · Inactiva</option> : null}{options?.map((item) => <option key={item.id} value={item.id}>{item.name}{'area' in item ? ` · ${choices.data?.areas.find((a) => a.id === item.area)?.name || ''}` : ''}</option>)}</Select><label className="block text-sm font-medium">Mes del presupuesto<input name="period" type="month" required min="1900-01" max="9998-12" className="input mt-2" defaultValue={edit ? `${edit.year}-${String(edit.month).padStart(2, '0')}` : period} /></label><label className="block text-sm font-medium">Límite (PEN)<input name="amount" type="text" inputMode="decimal" required pattern="[0-9]+([.,][0-9]{1,2})?" className="input mt-2" defaultValue={edit?.limit_amount} placeholder="500.00" /></label><label className="flex items-center gap-2 text-sm"><input name="active" type="checkbox" defaultChecked={edit?.is_active ?? true} />Presupuesto activo</label><button className="button-primary w-full" disabled={saving || choices.loading || Boolean(choices.error) || Boolean(family && family.role !== 'ADMIN')}>{saving ? 'Guardando…' : 'Guardar presupuesto'}</button>{edit ? <button type="button" className="button-secondary w-full" onClick={() => setEdit(undefined)}>Cancelar edición</button> : null}<p className="text-xs leading-relaxed text-slate-500">Cada área o categoría admite un presupuesto por mes, también si está desactivado. Los presupuestos de área y categoría se evalúan por separado; sus límites no se suman.</p></form></div></>
}
