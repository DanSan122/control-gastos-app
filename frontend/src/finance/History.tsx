import { useFinancialScope } from '../families/Scope'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { kindLabel, pen, type Account, type Movement, type Category } from './api'
import { LoadState, PageHeader, PeriodPicker, Select, initialPeriod, periodQuery, useResource } from './ui'

export default function History() {
  const { finance, href, family } = useFinancialScope()
  const { user } = useAuth()
  const [period, setPeriod] = useState(initialPeriod)
  const [registeredBy, setRegisteredBy] = useState('')
  const [classification, setClassification] = useState('')
  const members = useResource((signal) => family ? finance.all<{user: string; name: string}>('members', '', signal) : Promise.resolve([]))
  const categories = useResource((signal) => finance.all<Category>('categories', '', signal))
  const [kind, setKind] = useState('')
  const [account, setAccount] = useState('')
  const [status, setStatus] = useState('POSTED')
  const [page, setPage] = useState(1)
  const [ordering, setOrdering] = useState('-occurred_at')
  const query = `registered_by=${registeredBy}&category=${classification}&${periodQuery(period)}&kind=${kind}&account=${account}&status=${status}&ordering=${ordering}&page=${page}`
  const state = useResource((signal) => finance.list<Movement>('transactions', query, signal), [query])
  const accounts = useResource((signal) => finance.all<Account>('accounts', '', signal))
  return <><PageHeader eyebrow="HISTORIAL" title="Tus movimientos">Los movimientos anulados permanecen disponibles; las transferencias no son ingresos ni gastos.</PageHeader>
    <div className="card mb-6"><PeriodPicker value={period} onChange={(value) => { setPeriod(value); setPage(1) }} /><div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Select label="Tipo" name="filter-kind" value={kind} onChange={(event) => { setKind(event.target.value); setPage(1) }}><option value="">Todos</option><option value="INCOME">Ingresos</option><option value="EXPENSE">Gastos</option><option value="TRANSFER">Transferencias</option></Select>
      <Select label="Cuenta" name="filter-account" value={account} onChange={(event) => { setAccount(event.target.value); setPage(1) }}><option value="">Todas</option>{accounts.data?.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select>
      <Select label="Estado" name="filter-status" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1) }}><option value="">Todos</option><option value="POSTED">Vigentes</option><option value="VOID">Anulados</option></Select>
      <Select label="Orden" name="ordering" value={ordering} onChange={(event) => { setOrdering(event.target.value); setPage(1) }}><option value="-occurred_at">Más recientes</option><option value="occurred_at">Más antiguos</option><option value="-amount">Mayor importe</option><option value="amount">Menor importe</option></Select>
      {family ? <Select label="Registrado por" value={registeredBy} onChange={e => { setRegisteredBy(e.target.value); setPage(1) }}><option value="">Todos los integrantes</option>{members.data?.map(m => <option key={m.user} value={m.user}>{m.name}</option>)}</Select> : null}
      <Select label="Categoría del movimiento" value={classification} onChange={e => { setClassification(e.target.value); setPage(1) }}><option value="">Todas las categorías</option>{categories.data?.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>
    </div></div><LoadState {...state} retry={state.reload} />
    {state.data && !state.error && !state.loading ? <>
      <p className="mb-3 text-sm text-slate-500">{state.data.count} movimientos · página {page}</p>
      {!state.data.results.length ? <div className="card text-slate-500">No hay movimientos para estos filtros.</div> : <div className="space-y-3">{state.data.results.map((item) => <Link to={href(`/movimientos/${item.id}`)} key={item.id} className="card flex min-w-0 flex-wrap items-center justify-between gap-4 transition hover:border-emerald-300">
        <div className="min-w-0"><p className="text-xs font-medium text-emerald-700">{kindLabel(item.kind)} · {item.status === 'VOID' ? 'Anulado' : 'Vigente'}</p><h2 className="mt-1 break-words font-semibold">{item.description || item.category_name || 'Transferencia entre cuentas'}</h2>
          {family ? <p className="mt-2 text-xs text-emerald-700">Registrado por {item.registered_by_name}</p> : null}<p className="mt-1 break-words text-sm text-slate-500">{item.account_name}{item.destination_name ? ` → ${item.destination_name}` : ''}</p><p className="mt-1 text-xs text-slate-400">{new Intl.DateTimeFormat('es-PE', { dateStyle: 'medium', timeStyle: 'short', timeZone: (family?.timezone || user?.timezone) || 'America/Lima' }).format(new Date(item.occurred_at))}</p></div>
        <span className="shrink-0 font-semibold">{pen(item.amount)} →</span>
      </Link>)}</div>}
      <div className="mt-5 flex justify-between"><button className="button-secondary" disabled={!state.data.previous} onClick={() => setPage((value) => value - 1)}>Anterior</button><button className="button-secondary" disabled={!state.data.next} onClick={() => setPage((value) => value + 1)}>Siguiente</button></div>
    </> : null}</>
}
