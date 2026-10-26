import { useFinancialScope } from '../families/Scope'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

import { LoadState, PageHeader, Select, useResource } from '../finance/ui'
import type { AuditEvent } from './api'

const resourceNames: Record<string, string> = { 'families.family': 'Familia', 'families.familymembership': 'Membresía', 'families.familyinvitation': 'Invitación', 'accounts.account': 'Cuenta', 'categories.area': 'Área', 'categories.category': 'Categoría', 'categories.subcategory': 'Subcategoría', 'transactions.transaction': 'Movimiento', 'budgets.budget': 'Presupuesto', 'recurring.recurringrule': 'Regla recurrente', 'recurring.recurringexecution': 'Ocurrencia' }
const operationNames: Record<string, string> = { CREATE: 'Creación', UPDATE: 'Edición', VOID: 'Anulación', DEACTIVATE: 'Desactivación', PAUSE: 'Pausa', RESUME: 'Reanudación', CANCEL: 'Cancelación', EXECUTE: 'Ejecución', SKIP: 'Omisión' }
export default function AuditHistory({ resourceId, revision = 0 }: { resourceId?: string; revision?: number }) {
  const { finance, href, family } = useFinancialScope()
  const { user } = useAuth()
  const [resource, setResource] = useState(resourceId ? 'transactions.transaction' : '')
  const [operation, setOperation] = useState('')
  const [page, setPage] = useState(1)
  const query = new URLSearchParams({ page: String(page) })
  if (resource) query.set('resource_type', resource)
  if (operation) query.set('operation', operation)
  if (resourceId) query.set('resource_id', resourceId)
  const filters = query.toString()
  const state = useResource((signal) => finance.list<AuditEvent>('audit/events', filters, signal), [filters, revision])
  const renderValue = (value: string | boolean | number | null | undefined) => value === undefined ? 'Omitido o sin valor previo' : value === null ? '—' : typeof value === 'boolean' ? value ? 'Sí' : 'No' : String(value)
  return <section className={resourceId ? 'mt-8' : ''}>{resourceId ? <h2 className="mb-5 text-lg font-semibold">Historial de cambios del movimiento</h2> : <PageHeader eyebrow="TRAZABILIDAD PRIVADA" title="Auditoría financiera">El historial comienza desde su activación. No reconstruye versiones previas. Descripción, referencia e institución no se copian a los eventos.</PageHeader>}
    <div className="mb-5 flex flex-wrap gap-4">{!resourceId ? <Select label="Recurso" value={resource} onChange={(e) => { setResource(e.target.value); setPage(1) }}><option value="">Todos los recursos</option>{Object.entries(resourceNames).map(([value, name]) => <option key={value} value={value}>{name}</option>)}</Select> : null}<Select label="Operación" value={operation} onChange={(e) => { setOperation(e.target.value); setPage(1) }}><option value="">Todas las operaciones</option>{Object.entries(operationNames).map(([value, name]) => <option key={value} value={value}>{name}</option>)}</Select></div>
    <LoadState {...state} retry={state.reload} />{state.data && !state.loading && !state.error ? <><div className="space-y-4">{state.data.results.map((event) => <article key={event.id} className="card min-w-0"><div className="flex flex-wrap justify-between gap-3"><h3 className="font-semibold">{operationNames[event.operation]} · {resourceNames[event.resource_type]}</h3><time className="text-xs text-slate-500" dateTime={event.occurred_at}>{new Date(event.occurred_at).toLocaleString('es-PE', { timeZone: (family?.timezone || user?.timezone) })}</time></div><p className="mt-2 break-all text-xs text-slate-500">Recurso: {event.resource_id} · Actor: {event.actor}</p>{event.resource_type === 'transactions.transaction' && !resourceId ? <Link className="text-link mt-3 inline-block text-sm" to={href(`/movimientos/${event.resource_id}`)}>Ver movimiento</Link> : null}<details className="mt-4"><summary className="cursor-pointer text-sm font-medium">Ver valores anteriores y posteriores</summary><div className="mt-3 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th className="p-2">Campo</th><th className="p-2">Anterior</th><th className="p-2">Posterior</th></tr></thead><tbody>{event.changed_fields.map((field) => <tr key={field} className="border-t border-slate-100"><td className="p-2">{field}</td><td className="max-w-xs break-all p-2">{renderValue(event.before[field])}</td><td className="max-w-xs break-all p-2">{renderValue(event.after[field])}</td></tr>)}</tbody></table></div><p className="mt-3 break-all text-xs text-slate-400">Evento: {event.id} · Correlación: {event.correlation_id}</p></details></article>)}</div>{!state.data.count ? <p className="card text-slate-500">No hay eventos desde la activación para estos filtros.</p> : null}<div className="mt-5 flex items-center gap-4"><button className="button-secondary" disabled={!state.data.previous} onClick={() => setPage(page - 1)}>Anterior</button><span className="text-sm">Página {page}</span><button className="button-secondary" disabled={!state.data.next} onClick={() => setPage(page + 1)}>Siguiente</button></div></> : null}</section>
}
