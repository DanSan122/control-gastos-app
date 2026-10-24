import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Field, type FormFeedback } from '../components/Form'
import {
  finance,
  kindLabel,
  pen,
  moneyInput,
  localDateTime,
  type Account,
  type Area,
  type Category,
  type Subcategory,
  type Kind,
} from '../finance/api'
import {
  PageHeader,
  Select,
  LoadState,
  useResource,
  FinanceFeedback,
  feedbackFrom,
} from '../finance/ui'
import Upcoming, { ExecutionActions } from './Upcoming'
import { recurring, frequencyLabel, statusLabel, type Rule, type Execution } from './api'

export function Rules() {
  const [kind, setKind] = useState(''),
    [status, setStatus] = useState('ACTIVE'),
    [frequency, setFrequency] = useState(''),
    [page, setPage] = useState(1)
  const query = new URLSearchParams({ kind, status, frequency, page: String(page) }).toString()
  const state = useResource(
    (signal) => finance.list<Rule>('recurring/rules', query, signal),
    [query],
  )
  return (
    <>
      <PageHeader eyebrow="PLANIFICACIÓN FINANCIERA" title="Movimientos recurrentes">
        Organiza vencimientos. El registro automático requiere un procesador periódico; no se envían
        pagos a bancos.
      </PageHeader>
      <Link className="button-primary inline-block" to="/recurrentes/nueva">
        Nueva regla recurrente
      </Link>
      <Upcoming />
      <div className="mb-5 flex flex-wrap gap-4">
        <Select
          label="Tipo de regla"
          value={kind}
          onChange={(e) => {
            setKind(e.target.value)
            setPage(1)
          }}
        >
          <option value="">Todos los tipos</option>
          <option value="EXPENSE">Gasto</option>
          <option value="INCOME">Ingreso</option>
          <option value="TRANSFER">Transferencia</option>
        </Select>
        <Select
          label="Estado de regla"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value)
            setPage(1)
          }}
        >
          <option value="">Todos los estados</option>
          {['ACTIVE', 'PAUSED', 'COMPLETED', 'CANCELLED'].map((s) => (
            <option key={s} value={s}>
              {statusLabel[s]}
            </option>
          ))}
        </Select>
        <Select
          label="Frecuencia de regla"
          value={frequency}
          onChange={(e) => {
            setFrequency(e.target.value)
            setPage(1)
          }}
        >
          <option value="">Todas las frecuencias</option>
          {Object.entries(frequencyLabel).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
      </div>
      <LoadState {...state} retry={state.reload} />
      {state.data && !state.loading && !state.error ? (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            {state.data.results.map((rule) => (
              <article key={rule.id} className="card">
                <h2 className="font-semibold">{rule.name}</h2>
                <p className="mt-3 break-words text-2xl font-semibold">{pen(rule.amount)}</p>
                <p className="mt-3 text-sm text-slate-500">
                  {kindLabel(rule.kind)} · {frequencyLabel[rule.frequency]} · Cada {rule.interval} ·{' '}
                  {statusLabel[rule.status]}
                </p>
                <p className="mt-2 text-sm text-slate-500">
                  Próximo: {rule.next_due_date || 'Sin próximos'} · {rule.execution_mode}
                </p>
                <Link className="text-link mt-5 inline-block" to={`/recurrentes/${rule.id}`}>
                  Ver regla e historial
                </Link>
              </article>
            ))}
          </div>
          {!state.data.count ? (
            <p className="card text-slate-500">No hay reglas con estos filtros.</p>
          ) : null}
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
        </>
      ) : null}
    </>
  )
}

function Editor({ rule }: { rule?: Rule }) {
  const { user } = useAuth(),
    navigate = useNavigate()
  const [kind, setKind] = useState<Kind>(rule?.kind || 'EXPENSE'),
    [source, setSource] = useState(rule?.source_account || ''),
    [area, setArea] = useState(rule?.area || ''),
    [category, setCategory] = useState(rule?.category || '')
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<FormFeedback>()
  const choices = useResource(async (signal) => {
    const [accounts, areas, categories, subcategories] = await Promise.all([
      finance.all<Account>('accounts', 'active=true', signal),
      finance.all<Area>('areas', 'active=true', signal),
      finance.all<Category>('categories', 'active=true', signal),
      finance.all<Subcategory>('subcategories', 'active=true', signal),
    ])
    return { accounts, areas, categories, subcategories }
  })
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(undefined)
    const data = new FormData(event.currentTarget),
      mode = String(data.get('execution_mode'))
    if (
      !window.confirm(
        mode === 'AUTOMATIC'
          ? '¿Guardar regla automática? El procesador registrará vencidos aunque cierres el navegador.'
          : '¿Guardar regla manual? Cada ocurrencia requiere confirmación.',
      )
    )
      return
    setBusy(true)
    try {
      const saved = await finance.save<Rule>(
        'recurring/rules',
        {
          name: String(data.get('name')).trim(),
          kind,
          amount: moneyInput(data.get('amount')),
          currency: 'PEN',
          source_account: source,
          destination_account: kind === 'TRANSFER' ? data.get('destination_account') : null,
          area: kind !== 'TRANSFER' ? area : null,
          category: kind !== 'TRANSFER' ? category : null,
          subcategory: kind !== 'TRANSFER' ? data.get('subcategory') || null : null,
          payment_method: data.get('payment_method') || '',
          frequency: data.get('frequency') || rule?.frequency,
          interval: Number(data.get('interval') || rule?.interval || 1),
          start_date: rule?.start_date || data.get('start_date'),
          end_date: data.get('end_date') || null,
          execution_mode: mode,
        },
        rule?.id,
      )
      navigate(`/recurrentes/${saved.id}`, { replace: true })
    } catch (reason) {
      setError(feedbackFrom(reason))
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <PageHeader
        eyebrow="REGLA RECURRENTE"
        title={rule ? 'Editar regla recurrente' : 'Nueva regla recurrente'}
      >
        PEN · Zona fijada: {rule?.timezone || user?.timezone}. Días 29–31 se ajustan sin
        desplazamiento acumulativo.
      </PageHeader>
      <LoadState {...choices} retry={choices.reload} />
      <form aria-label="Regla recurrente" className="card max-w-3xl" onSubmit={submit}>
        <FinanceFeedback error={error} />
        <fieldset disabled={busy || choices.loading} className="mt-5 grid gap-5 sm:grid-cols-2">
          <Field
            label="Nombre de la regla"
            name="name"
            required
            maxLength={100}
            defaultValue={rule?.name}
          />
          <Select
            label="Tipo de movimiento"
            value={kind}
            disabled={Boolean(rule)}
            onChange={(e) => {
              setKind(e.target.value as Kind)
              setArea('')
              setCategory('')
            }}
          >
            <option value="EXPENSE">Gasto</option>
            <option value="INCOME">Ingreso</option>
            <option value="TRANSFER">Transferencia</option>
          </Select>
          <Select
            label="Cuenta de origen"
            value={source}
            required
            onChange={(e) => setSource(e.target.value)}
          >
            <option value="">Selecciona una cuenta</option>
            {choices.data?.accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </Select>
          {kind === 'TRANSFER' ? (
            <Select
              label="Cuenta de destino"
              name="destination_account"
              defaultValue={rule?.destination_account || ''}
              required
            >
              <option value="">Selecciona otra cuenta</option>
              {choices.data?.accounts
                .filter((a) => a.id !== source)
                .map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
            </Select>
          ) : null}
          <Field
            label="Importe programado (PEN)"
            name="amount"
            required
            inputMode="decimal"
            pattern="[0-9]+([.,][0-9]{1,2})?"
            defaultValue={rule?.amount}
            placeholder="0.00"
          />
          {kind !== 'TRANSFER' ? (
            <>
              <Select
                label="Área"
                value={area}
                required
                onChange={(e) => {
                  setArea(e.target.value)
                  setCategory('')
                }}
              >
                <option value="">Selecciona un área</option>
                {choices.data?.areas.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </Select>
              <Select
                label="Categoría"
                value={category}
                required
                onChange={(e) => setCategory(e.target.value)}
              >
                <option value="">Selecciona una categoría</option>
                {choices.data?.categories
                  .filter((c) => c.area === area && c.kind === kind)
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
              </Select>
              <Select
                label="Subcategoría"
                name="subcategory"
                key={category}
                defaultValue={category === rule?.category ? rule?.subcategory || '' : ''}
              >
                <option value="">Sin subcategoría</option>
                {choices.data?.subcategories
                  .filter((s) => s.category === category)
                  .map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
              </Select>
            </>
          ) : null}
          <Select
            label="Método de pago"
            name="payment_method"
            defaultValue={rule?.payment_method || ''}
          >
            <option value="">Sin especificar</option>
            {[
              ['CASH', 'Efectivo'],
              ['CARD', 'Tarjeta'],
              ['YAPE', 'Yape'],
              ['PLIN', 'Plin'],
              ['BANK', 'Banco'],
              ['OTHER', 'Otro'],
            ].map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
          <Select
            label="Frecuencia"
            name="frequency"
            defaultValue={rule?.frequency || 'MONTHLY'}
            disabled={rule?.calendar_locked}
          >
            {Object.entries(frequencyLabel).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
          <Field
            label="Cada cuántos periodos"
            name="interval"
            type="number"
            required
            min={1}
            max={1000}
            defaultValue={rule?.interval || 1}
            disabled={rule?.calendar_locked}
          />
          <Field
            label="Fecha inicial"
            name="start_date"
            type="date"
            required
            defaultValue={
              rule?.start_date ||
              localDateTime(new Date().toISOString(), user?.timezone || 'America/Lima').slice(0, 10)
            }
            disabled={Boolean(rule)}
          />
          <Field
            label="Fecha final (opcional)"
            name="end_date"
            type="date"
            defaultValue={rule?.end_date || ''}
          />
          <Select
            label="Modo de ejecución"
            name="execution_mode"
            defaultValue={rule?.execution_mode || 'MANUAL'}
          >
            <option value="MANUAL">Confirmación manual</option>
            <option value="AUTOMATIC">Registro automático</option>
          </Select>
        </fieldset>
        <p className="mt-5 text-xs text-slate-500">
          No se envían pagos a bancos. Importe/cuentas aplican a pendientes y futuros; el historial
          conserva movimientos anteriores. Inicio y tipo no cambian; el calendario se bloquea al
          consumir una ocurrencia.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <button
            disabled={busy || choices.loading || Boolean(choices.error)}
            className="button-primary"
          >
            {busy ? 'Guardando…' : 'Guardar regla'}
          </button>
          <Link className="button-secondary" to={rule ? `/recurrentes/${rule.id}` : '/recurrentes'}>
            Volver
          </Link>
        </div>
      </form>
    </>
  )
}
export function RuleForm() {
  const { id } = useParams()
  const state = useResource(
    (signal) =>
      id ? finance.get<Rule>('recurring/rules', id, signal) : Promise.resolve(undefined),
    [id],
  )
  if (!id) return <Editor key="new" />
  return (
    <>
      <LoadState {...state} retry={state.reload} />
      {state.data && !state.loading && !state.error ? <Editor key={id} rule={state.data} /> : null}
    </>
  )
}

export function RuleDetail() {
  const { id = '' } = useParams(),
    [page, setPage] = useState(1),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('')
  const state = useResource((signal) => finance.get<Rule>('recurring/rules', id, signal), [id])
  const history = useResource(
    (signal) => finance.list<Execution>('recurring/executions', `rule=${id}&page=${page}`, signal),
    [id, page],
  )
  const refresh = () => {
    state.reload()
    history.reload()
  }
  async function act(action: 'pause' | 'resume' | 'cancel') {
    if (
      !window.confirm(
        `¿${action === 'pause' ? 'Pausar' : action === 'resume' ? 'Reanudar' : 'Cancelar definitivamente'} esta regla? Su historial se conserva.`,
      )
    )
      return
    setBusy(true)
    setError('')
    try {
      if (action === 'cancel') await finance.remove('recurring/rules', id)
      else await recurring.action<Rule>('rules', id, action)
      refresh()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No se pudo modificar la regla.')
    } finally {
      setBusy(false)
    }
  }
  const rule = state.data
  return (
    <>
      <PageHeader eyebrow="DETALLE DE RECURRENCIA" title={rule?.name || 'Detalle de regla'} />
      <LoadState {...state} retry={state.reload} />
      {error ? (
        <p role="alert" className="mb-5 text-red-700">
          {error}
        </p>
      ) : null}
      {rule ? (
        <section className="card">
          <p className="text-3xl font-semibold">{pen(rule.amount)}</p>
          <p className="mt-4 text-sm">
            {kindLabel(rule.kind)} · {frequencyLabel[rule.frequency]} · Cada {rule.interval} ·{' '}
            {statusLabel[rule.status]}
          </p>
          <p className="mt-3 text-sm text-slate-500">
            {rule.source_name}
            {rule.destination_name ? ` → ${rule.destination_name}` : ''} · {rule.timezone}
          </p>
          <p className="mt-3 text-sm">
            Inicio: {rule.start_date} · Fin: {rule.end_date || 'Sin límite'} · Próximo:{' '}
            {rule.next_due_date || 'Sin próximos'}
          </p>
          <p className="mt-3 text-sm text-slate-500">
            {rule.execution_mode === 'AUTOMATIC'
              ? 'Procesador automático: registra vencidos sin navegador; requiere servicio periódico activo.'
              : 'Confirmación manual: no hay movimiento hasta confirmar.'}
          </p>
          {rule.status === 'ACTIVE' || rule.status === 'PAUSED' ? (
            <div className="mt-5 flex flex-wrap gap-3">
              <Link className="button-primary" to={`/recurrentes/${id}/editar`}>
                Editar regla
              </Link>
              <button
                disabled={busy}
                className="button-secondary"
                onClick={() => void act(rule.status === 'ACTIVE' ? 'pause' : 'resume')}
              >
                {rule.status === 'ACTIVE' ? 'Pausar regla' : 'Reanudar regla'}
              </button>
              <button
                disabled={busy}
                className="button-secondary text-red-700"
                onClick={() => void act('cancel')}
              >
                Cancelar regla
              </button>
            </div>
          ) : null}
        </section>
      ) : null}
      <section className="mt-7">
        <h2 className="mb-4 text-lg font-semibold">Historial de ejecuciones</h2>
        <LoadState {...history} retry={history.reload} />
        {history.data && !history.loading && !history.error ? (
          <>
            <div className="space-y-4">
              {history.data.results.map((execution) => (
                <article key={execution.id} className="card">
                  <div className="flex flex-wrap justify-between gap-3">
                    <h3 className="font-semibold">
                      {execution.scheduled_date} · {statusLabel[execution.status]}
                    </h3>
                    <span>{pen(execution.amount)}</span>
                  </div>
                  {execution.error_code ? (
                    <p className="mt-3 text-sm text-amber-700">
                      Error seguro: {execution.error_code}
                    </p>
                  ) : null}
                  <ExecutionActions execution={execution} refresh={refresh} />
                </article>
              ))}
            </div>
            <div className="mt-5 flex items-center gap-4">
              <button
                className="button-secondary"
                disabled={!history.data.previous}
                onClick={() => setPage(page - 1)}
              >
                Anterior
              </button>
              <span className="text-sm">Página {page}</span>
              <button
                className="button-secondary"
                disabled={!history.data.next}
                onClick={() => setPage(page + 1)}
              >
                Siguiente
              </button>
              <button className="text-link text-sm" onClick={refresh}>
                Actualizar historial
              </button>
            </div>
          </>
        ) : null}
      </section>
      <Link to="/recurrentes" className="text-link mt-6 inline-block">
        Ver todas las reglas
      </Link>
    </>
  )
}
