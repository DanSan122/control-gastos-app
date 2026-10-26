import { useFinancialScope } from '../families/Scope'
import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { type FormFeedback } from '../components/Form'
import { kindLabel, pen, type Movement } from './api'
import MovementForm from './MovementForm'
import AuditHistory from '../reports/AuditHistory'
import { FinanceFeedback, LoadState, PageHeader, feedbackFrom, useResource } from './ui'

export default function MovementDetail() {
  const { finance, href, family } = useFinancialScope()
  const { id = '' } = useParams()
  const { user } = useAuth()
  const location = useLocation()
  const [editing, setEditing] = useState(false)
  const [error, setError] = useState<FormFeedback>()
  const [busy, setBusy] = useState(false)
  useEffect(() => { setEditing(false) }, [location.key])
  const state = useResource((signal) => finance.get<Movement>('transactions', id, signal), [id, location.key])
  async function annul() {
    if (!window.confirm('¿Anular este movimiento? Se revertirán sus efectos de saldo y se conservará el registro.')) return
    setBusy(true); setError(undefined)
    try { await finance.remove('transactions', id); state.reload() } catch (reason) { setError(feedbackFrom(reason)) } finally { setBusy(false) }
  }
  if (editing && state.data) return <><button className="text-link mb-6" onClick={() => { setEditing(false); state.reload() }}>← Volver al detalle</button><MovementForm key={state.data.id} kind={state.data.kind} movement={state.data} /></>
  return <><PageHeader eyebrow="DETALLE" title="Detalle del movimiento" /><LoadState {...state} retry={state.reload} /><FinanceFeedback error={error} success={(location.state as { saved?: boolean } | null)?.saved ? 'Movimiento guardado correctamente.' : undefined} />
    {state.data ? <article className="card mt-5 max-w-3xl"><p className="eyebrow">{kindLabel(state.data.kind)} · {state.data.status === 'VOID' ? 'Anulado' : 'Vigente'}</p><p className="mt-5 break-words text-4xl font-semibold">{pen(state.data.amount)}</p>
      <dl className="mt-6 grid gap-4 text-sm sm:grid-cols-2">{[
        ['Registrado por', state.data.registered_by_name], ['Cuenta', state.data.account_name], ['Destino', state.data.destination_name], ['Área', state.data.area_name], ['Categoría', state.data.category_name], ['Subcategoría', state.data.subcategory_name],
        ['Descripción', state.data.description], ['Método', state.data.payment_method], ['Referencia', state.data.reference],
        ['Fecha efectiva', new Intl.DateTimeFormat('es-PE', { dateStyle: 'long', timeStyle: 'short', timeZone: (family?.timezone || user?.timezone) || 'America/Lima' }).format(new Date(state.data.occurred_at))],
      ].map(([label, value]) => <div key={label}><dt className="text-slate-500">{label}</dt><dd className="mt-1 break-words font-medium">{value || '—'}</dd></div>)}</dl>
      <div className="mt-7 flex flex-wrap gap-4">{state.data.status === 'POSTED' && (!family || family.role === 'ADMIN' || state.data.registered_by === user?.id) ? <><button className="button-primary" disabled={busy} onClick={() => setEditing(true)}>Editar movimiento</button><button className="button-secondary text-red-700" disabled={busy} onClick={annul}>{busy ? 'Anulando…' : 'Anular movimiento'}</button></> : <p className="text-sm text-slate-500">{state.data.status === 'VOID' ? 'Este registro anulado es inmutable y no participa en saldos ni reportes.' : 'Solo el autor o un administrador puede modificar este movimiento.'}</p>}<Link to={href("/movimientos")} className="button-secondary">Ver historial</Link></div>
    </article> : null}{state.data ? <AuditHistory key={id} resourceId={id} revision={state.data.status === 'VOID' ? 1 : 0} /> : null}</>
}
