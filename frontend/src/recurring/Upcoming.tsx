import { useState } from 'react'
import { Link } from 'react-router-dom'
import { kindLabel, localDateTime, pen } from '../finance/api'
import { useResource, LoadState } from '../finance/ui'
import { recurring, statusLabel, type Execution } from './api'

export function ExecutionActions({
  execution,
  refresh,
}: {
  execution: Execution
  refresh: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const due =
    execution.scheduled_date <=
    localDateTime(new Date().toISOString(), execution.timezone).slice(0, 10)
  async function act(action: 'confirm' | 'skip') {
    if (
      !window.confirm(
        action === 'confirm'
          ? `¿Registrar ${kindLabel(execution.kind).toLowerCase()} de ${pen(execution.amount)} para ${execution.scheduled_date}?`
          : '¿Omitir esta ocurrencia? Se conservará sin movimiento financiero.',
      )
    )
      return
    setBusy(true)
    setError('')
    try {
      await recurring.action<Execution>('executions', execution.id, action)
      refresh()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No se pudo completar la operación.')
      refresh()
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      {execution.transaction ? (
        <Link className="text-link text-sm" to={`/movimientos/${execution.transaction}`}>
          Ver movimiento generado
        </Link>
      ) : execution.execution_mode === 'MANUAL' &&
        execution.rule_status === 'ACTIVE' &&
        (execution.status === 'PENDING' || execution.status === 'FAILED') ? (
        <div className="mt-3 flex flex-wrap gap-3">
          <button
            disabled={busy || !due}
            className="button-primary"
            onClick={() => void act('confirm')}
          >
            {busy ? 'Procesando…' : 'Confirmar ocurrencia'}
          </button>
          <button
            disabled={busy || !due}
            className="button-secondary"
            onClick={() => void act('skip')}
          >
            Omitir ocurrencia
          </button>
          {!due ? (
            <p className="text-xs text-slate-500">Disponible al vencer en {execution.timezone}.</p>
          ) : null}
        </div>
      ) : null}
      {error ? (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {error}
        </p>
      ) : null}
    </>
  )
}
export default function Upcoming({ compact = false }: { compact?: boolean }) {
  const [page, setPage] = useState(1)
  const state = useResource((signal) => recurring.upcoming(signal, compact, page), [compact, page])
  const refresh = () => {
    setPage(1)
    state.reload()
  }
  return (
    <section className="card my-6 min-w-0">
      <div className="flex flex-wrap justify-between gap-3">
        <h2 className="text-lg font-semibold">Próximos movimientos programados</h2>
        <button className="text-link text-sm" onClick={refresh}>
          Actualizar próximos
        </button>
      </div>
      <p className="mt-2 text-sm text-slate-500">
        Próximo vencimiento de cada regla activa en 30 días, incluidos atrasados. Los pendientes no
        afectan saldos ni presupuestos.
      </p>
      <LoadState {...state} retry={refresh} />
      {state.data && !state.loading && !state.error ? (
        <>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            {[
              ['Ingresos programados', state.data.scheduled_totals.income],
              ['Gastos programados', state.data.scheduled_totals.expense],
              ['Transferencias programadas', state.data.scheduled_totals.transfer],
            ].map(([label, amount]) => (
              <div key={label}>
                <p className="text-xs text-slate-500">{label}</p>
                <p className="mt-2 break-words text-xl font-semibold">{pen(amount)}</p>
              </div>
            ))}
          </div>
          <ul className="mt-5 space-y-5">
            {state.data.results.map((execution) => (
              <li key={execution.id} className="border-t border-slate-100 pt-4">
                <div className="flex flex-wrap justify-between gap-3">
                  <Link className="text-link font-medium" to={`/recurrentes/${execution.rule}`}>
                    {execution.rule_name}
                  </Link>
                  <span className="text-sm font-semibold">{pen(execution.amount)}</span>
                </div>
                <p className="mt-2 text-sm text-slate-500">
                  {kindLabel(execution.kind)} · {execution.scheduled_date} · {execution.timezone} ·{' '}
                  {statusLabel[execution.status]} ·{' '}
                  {execution.execution_mode === 'MANUAL' ? 'Manual' : 'Automático'}
                </p>
                {execution.error_code ? (
                  <p className="mt-2 text-sm text-amber-700">
                    No se registró dinero: {execution.error_code}
                  </p>
                ) : null}
                {!compact ? <ExecutionActions execution={execution} refresh={refresh} /> : null}
              </li>
            ))}
          </ul>
          {!state.data.count ? (
            <p className="mt-5 text-sm text-slate-500">No hay vencimientos para esta ventana.</p>
          ) : null}
          {compact ? (
            <Link className="text-link mt-5 inline-block text-sm" to="/recurrentes">
              Ver reglas y vencimientos
            </Link>
          ) : (
            <div className="mt-5 flex items-center gap-4">
              <button
                className="button-secondary"
                disabled={!state.data.previous}
                onClick={() => setPage(page - 1)}
              >
                Anterior
              </button>
              <span className="text-sm">Página {page}</span>
              <button
                className="button-secondary"
                disabled={!state.data.next}
                onClick={() => setPage(page + 1)}
              >
                Siguiente
              </button>
            </div>
          )}
        </>
      ) : null}
    </section>
  )
}
