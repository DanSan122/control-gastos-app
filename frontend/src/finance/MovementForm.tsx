import { useFinancialScope } from '../families/Scope'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Field, SubmitButton, type FormFeedback } from '../components/Form'
import { ApiError } from '../lib/api'
import { kindLabel, localDateTime, localToIso, moneyInput, pen, type Account, type Area, type Category, type Kind, type Movement, type Subcategory } from './api'
import { FinanceFeedback, LoadState, PageHeader, Select, feedbackFrom, useResource } from './ui'

export default function MovementForm({ kind, movement }: { kind: Kind; movement?: Movement }) {
  const { finance, href, family } = useFinancialScope()
  const { user } = useAuth()
  const navigate = useNavigate()
  const zone = (family?.timezone || user?.timezone) || 'America/Lima'
  const [area, setArea] = useState(movement?.area || '')
  const [category, setCategory] = useState(movement?.category || '')
  const [account, setAccount] = useState(movement?.account || '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<FormFeedback>()
  // Mantener la clave y payload congelado tras el primer intento, incluso si la red falla.
  const [retry, setRetry] = useState<{ key: string; payload: Record<string, unknown> }>()
  const state = useResource(async (signal) => {
    const [accounts, areas, categories, subcategories] = await Promise.all([
      finance.all<Account>('accounts', '', signal), finance.all<Area>('areas', '', signal), finance.all<Category>('categories', '', signal), finance.all<Subcategory>('subcategories', '', signal),
    ])
    return { accounts, areas, categories, subcategories }
  })
  const activeOrOriginal = (item: Area, id: string | null | undefined) => item.is_active || item.id === id
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (retry) {
      setBusy(true); setError(undefined)
      try {
        const saved = await finance.transfer(retry.payload, retry.key)
        navigate(href(`/movimientos/${saved.id}`), { replace: true, state: { saved: true } })
      } catch (reason) {
        if (reason instanceof ApiError && reason.status === 400) setRetry(undefined)
        setError(feedbackFrom(reason))
      } finally { setBusy(false) }
      return
    }
    const data = new FormData(event.currentTarget)
    setError(undefined)
    try {
      const payload: Record<string, unknown> = { account: data.get('account'), kind, currency: 'PEN', amount: moneyInput(data.get('amount')),
        occurred_at: localToIso(String(data.get('occurred_at')), zone), description: String(data.get('description')).trim(),
        reference: String(data.get('reference')).trim(), payment_method: String(data.get('payment_method') || '') }
      if (kind === 'TRANSFER') payload.destination_account = data.get('destination_account')
      else { payload.area = data.get('area'); payload.category = data.get('category'); payload.subcategory = data.get('subcategory') || null }
      if (movement && !window.confirm('¿Guardar la corrección? Se recalcularán los saldos y resúmenes.')) return
      if (kind === 'TRANSFER' && !movement && !retry && !window.confirm(`¿Transferir ${pen(String(payload.amount))}? No se contará como ingreso ni gasto.`)) return
      setBusy(true)
      let saved: Movement
      if (kind === 'TRANSFER' && !movement) {
        const attempt = retry || { key: crypto.randomUUID(), payload }
        setRetry(attempt)
        saved = await finance.transfer(attempt.payload, attempt.key)
      } else saved = await finance.save<Movement>('transactions', payload, movement?.id)
      navigate(href(`/movimientos/${saved.id}`), { replace: true, state: { saved: true } })
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 400) setRetry(undefined)
      setError(feedbackFrom(reason))
    }
    finally { setBusy(false) }
  }
  return <>
    <PageHeader eyebrow={family ? 'MOVIMIENTO FAMILIAR' : movement ? 'EDITAR MOVIMIENTO' : 'MOVIMIENTO PERSONAL'} title={movement ? `Editar ${kindLabel(kind).toLowerCase()}` : kind === 'TRANSFER' ? 'Transferir dinero' : `Registrar ${kindLabel(kind).toLowerCase()}`}>
      {kind === 'TRANSFER' ? 'Entre cuentas propias. El pago de una tarjeta es una transferencia hacia esa tarjeta.' : 'Registra cada movimiento una sola vez, con su fecha efectiva.'}
    </PageHeader><LoadState {...state} retry={state.reload} />
    {state.data && !state.data.accounts.some((item) => item.is_active || item.id === movement?.account) ? <div className="card"><p>Crea una cuenta antes de registrar movimientos.</p><Link to={href("/cuentas")} className="text-link mt-3 inline-block">Ir a mis cuentas</Link></div> : null}
    {state.data?.accounts.length ? <section className="card max-w-3xl"><FinanceFeedback error={error} />
      {retry ? <p className="my-4 rounded-lg bg-amber-50 p-4 text-sm text-amber-900">El reintento conserva exactamente los datos del primer envío para evitar duplicados. No cierres esta página hasta confirmar el resultado en el historial.</p> : null}
      <form onSubmit={submit} aria-label="Movimiento financiero" className="mt-5"><fieldset disabled={busy || Boolean(retry)} className="grid gap-5 sm:grid-cols-2">
        <Select label={kind === 'TRANSFER' ? 'Cuenta de origen' : 'Cuenta'} name="account" required value={account} onChange={(event) => setAccount(event.target.value)}><option value="">Selecciona una cuenta</option>
          {state.data.accounts.filter((item) => activeOrOriginal(item, movement?.account)).map((item) => <option key={item.id} value={item.id}>{item.name} · {pen(item.balance)}{item.kind === 'CREDIT' ? ' · Crédito' : ''}</option>)}</Select>
        {kind === 'TRANSFER' ? <Select label="Cuenta de destino" name="destination_account" required defaultValue={movement?.destination_account || ''}><option value="">Selecciona otra cuenta</option>{state.data.accounts.filter((item) => item.id !== account && activeOrOriginal(item, movement?.destination_account)).map((item) => <option key={item.id} value={item.id}>{item.name}{item.kind === 'CREDIT' ? ' · Pago de deuda' : ''}</option>)}</Select> :
          <Select label="Método de pago" name="payment_method" defaultValue={movement?.payment_method || ''}><option value="">Sin especificar</option><option value="CASH">Efectivo</option><option value="YAPE">Yape</option><option value="PLIN">Plin</option><option value="CARD">Tarjeta</option><option value="BANK">Transferencia bancaria</option><option value="OTHER">Otro</option></Select>}
        <Field label="Importe (PEN)" name="amount" inputMode="decimal" pattern="[0-9]+([.,][0-9]{1,2})?" required defaultValue={movement?.amount} placeholder="0.00" />
        <Field label={`Fecha y hora (${zone})`} name="occurred_at" type="datetime-local" required defaultValue={localDateTime(movement?.occurred_at || new Date().toISOString(), zone)} />
        {kind !== 'TRANSFER' ? <>
          <Select label="Área" name="area" required value={area} onChange={(event) => { setArea(event.target.value); setCategory('') }}><option value="">Selecciona un área</option>{state.data.areas.filter((item) => activeOrOriginal(item, movement?.area)).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select>
          <Select label="Categoría" name="category" required value={category} onChange={(event) => setCategory(event.target.value)}><option value="">Selecciona una categoría</option>{state.data.categories.filter((item) => item.area === area && item.kind === kind && activeOrOriginal(item, movement?.category)).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select>
          <Select key={category} label="Subcategoría" name="subcategory" defaultValue={category === movement?.category ? movement?.subcategory || '' : ''}><option value="">Sin subcategoría</option>{state.data.subcategories.filter((item) => item.category === category && activeOrOriginal(item, movement?.subcategory)).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select>
        </> : null}
        <Field label="Referencia" name="reference" maxLength={100} defaultValue={movement?.reference} /><div className="sm:col-span-2"><Field label="Descripción" name="description" maxLength={500} defaultValue={movement?.description} /></div>
      </fieldset>
      <div className="mt-6"><SubmitButton busy={busy}>{retry ? 'Reintentar la misma transferencia' : movement ? 'Guardar corrección' : kind === 'TRANSFER' ? 'Confirmar transferencia' : `Guardar ${kindLabel(kind).toLowerCase()}`}</SubmitButton></div>
      {retry ? <Link className="text-link mt-4 inline-block text-sm" to={href("/movimientos")}>Consultar historial antes de otro envío</Link> : null}
      </form><p className="mt-5 text-xs leading-relaxed text-slate-500">Importes exactos con dos decimales. Zona horaria: {zone}. En una tarjeta, registra la compra como gasto y el pago posterior como transferencia.</p>
    </section> : null}
  </>
}
