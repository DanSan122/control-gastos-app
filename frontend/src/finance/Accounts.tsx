import { useFinancialScope } from '../families/Scope'
import { useState, type FormEvent } from 'react'
import { Field, SubmitButton, type FormFeedback } from '../components/Form'
import { pen, moneyInput, type Account } from './api'
import { FinanceFeedback, LoadState, PageHeader, Select, feedbackFrom, useResource } from './ui'

const accountKinds = { CASH: 'Efectivo', BANK: 'Banco', WALLET: 'Billetera digital', CREDIT: 'Tarjeta de crédito', OTHER: 'Otra cuenta de activos' }
export default function Accounts() {
  const { finance, family } = useFinancialScope()
  const state = useResource((signal) => finance.all<Account>('accounts', '', signal))
  const [editing, setEditing] = useState<Account>()
  const [kind, setKind] = useState<Account['kind']>('BANK')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<FormFeedback>()
  const [success, setSuccess] = useState('')
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    setBusy(true); setError(undefined); setSuccess('')
    try {
      const payload = { name: String(data.get('name')).trim(), institution: String(data.get('institution')).trim(),
        kind, currency: 'PEN', initial_balance: moneyInput(data.get('initial_balance')),
        ...(editing ? { is_active: data.get('is_active') === 'on' } : {}) }
      if (editing && (kind !== editing.kind || payload.initial_balance !== editing.initial_balance)
          && !window.confirm('¿Corregir los datos financieros iniciales? El saldo se recalculará.')) return
      await finance.save<Account>('accounts', payload, editing?.id)
      setEditing(undefined); setKind('BANK'); form.reset(); state.reload(); setSuccess('Cuenta guardada correctamente.')
    } catch (reason) { setError(feedbackFrom(reason)) }
    finally { setBusy(false) }
  }
  async function deactivate(account: Account) {
    if (!window.confirm(`¿Desactivar ${account.name}? Se conservarán su saldo e historial.`)) return
    setBusy(true); setError(undefined)
    try { await finance.remove('accounts', account.id); state.reload(); setSuccess('Cuenta desactivada; historial conservado.') }
    catch (reason) { setError(feedbackFrom(reason)) } finally { setBusy(false) }
  }
  return <>
    <PageHeader eyebrow="MIS CUENTAS" title="Tu dinero, en su lugar">Separa activos y deudas. Yape y Plin pueden usarse como métodos de una cuenta bancaria.</PageHeader>
    <FinanceFeedback error={error} success={success} />
    <div className="mt-6 grid items-start gap-6 xl:grid-cols-[1fr_360px]">
      <section><LoadState {...state} retry={state.reload} />
        {!state.loading && !state.error && !state.data?.length ? <div className="card text-slate-500">Aún no tienes cuentas. Crea la primera para registrar movimientos.</div> : null}
        <div className="grid gap-4 sm:grid-cols-2">{state.data?.map((account) => <article key={account.id} className="card min-w-0">
          <p className="eyebrow">{accountKinds[account.kind]} · {account.is_active ? 'Activa' : 'Inactiva'}</p><h2 className="mt-3 break-words text-xl font-semibold">{account.name}</h2>
          <p className="mt-1 text-sm text-slate-500">{account.institution || 'Sin institución'}</p><p className="mt-5 break-words text-2xl font-semibold">{pen(account.balance)}</p>
          <p className="mt-2 text-xs text-slate-500">{account.kind === 'CREDIT' ? `Deuda pendiente: ${pen(account.debt)}. No es límite de crédito.` : 'Saldo calculado desde tus movimientos.'}</p>
          <div className="mt-5 flex flex-wrap gap-3"><button className="button-secondary" disabled={busy || Boolean(family && family.role !== 'ADMIN')} onClick={() => { setEditing(account); setKind(account.kind); setError(undefined) }}>Editar</button>
            {account.is_active ? <button className="text-sm text-red-700" disabled={busy || Boolean(family && family.role !== 'ADMIN')} onClick={() => deactivate(account)}>Desactivar</button> : null}</div>
        </article>)}</div>
      </section>
      <section className="card"><h2 className="mb-5 text-xl font-semibold">{editing ? 'Editar cuenta' : 'Nueva cuenta'}</h2>
        <form aria-label={editing ? 'Editar cuenta' : 'Nueva cuenta'} onSubmit={submit} key={editing?.id || 'new'}><fieldset disabled={busy || Boolean(family && family.role !== 'ADMIN')} className="space-y-5">
          <Field label="Nombre de la cuenta" name="name" required maxLength={100} defaultValue={editing?.name} placeholder="Ej.: BCP soles, efectivo, Yape propio" />
          <Field label="Institución" name="institution" maxLength={100} defaultValue={editing?.institution} list="institutions" /><datalist id="institutions"><option value="BCP" /><option value="Interbank" /><option value="BBVA" /><option value="Scotiabank" /><option value="Banco de la Nación" /><option value="Yape" /><option value="Plin" /></datalist>
          <Select label="Tipo de cuenta" name="kind" value={kind} onChange={(event) => setKind(event.target.value as Account['kind'])}>{Object.entries(accountKinds).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select>
          <Field label="Saldo inicial (PEN)" name="initial_balance" inputMode="decimal" pattern="-?[0-9]+([.,][0-9]{1,2})?" required defaultValue={editing?.initial_balance || '0.00'} />
          <p className="text-xs text-slate-500">{kind === 'CREDIT' ? 'Deuda inicial con signo negativo. No registres el límite disponible.' : 'Saldo anterior a tus primeros movimientos registrados. Se permite saldo negativo para reflejar sobregiros.'}</p>
          {editing ? <><p className="text-xs text-slate-500">El tipo y saldo inicial solo se pueden corregir si la cuenta nunca tuvo movimientos.</p><label className="flex items-center gap-3 text-sm"><input name="is_active" type="checkbox" defaultChecked={editing.is_active} />Cuenta activa</label></> : null}
          <SubmitButton busy={busy}>Guardar cuenta</SubmitButton>
          {editing ? <button type="button" className="button-secondary w-full" onClick={() => { setEditing(undefined); setKind('BANK') }}>Cancelar edición</button> : null}
        </fieldset></form>
      </section>
    </div>
  </>
}
