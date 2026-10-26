import { PersonalScope } from '../families/Scope'
import { SpaceSelector } from '../families/pages'
import { useState } from 'react'
import { Link, Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { api } from '../lib/api'
import Sidebar from './Sidebar'

export function Brand() {
  return <Link to="/" className="flex items-center gap-3 font-bold tracking-tight text-slate-900">
    <span aria-hidden="true" className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-700 text-lg text-white">C</span>
    <span className="text-xl">Control<span className="text-emerald-700">Gastos</span></span>
  </Link>
}
export function AuthLayout() {
  return <main className="grid min-h-screen lg:grid-cols-2">
    <section className="relative hidden flex-col justify-between overflow-hidden bg-slate-950 p-14 text-white lg:flex">
      <div aria-hidden="true" className="absolute -right-20 top-32 h-96 w-96 rounded-full border border-emerald-700/30" />
      <p className="relative text-sm font-semibold uppercase tracking-[0.25em] text-emerald-300">Tu espacio personal</p>
      <div className="relative max-w-lg">
        <p className="mb-6 text-sm text-emerald-300">CLARIDAD · TRANQUILIDAD · CONTROL</p>
        <h1 className="text-5xl font-semibold leading-tight tracking-tight">El primer paso hacia unas finanzas más claras.</h1>
        <p className="mt-7 max-w-md text-lg leading-relaxed text-slate-300">Un lugar propio para organizarte y construir mejores hábitos, a tu ritmo.</p>
      </div>
      <p className="relative text-sm text-slate-400">Hecho para tu día a día. Pensado para ti.</p>
    </section>
    <section className="flex flex-col px-6 py-8 sm:px-12"><Brand />
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-12"><Outlet /></div>
      <p className="text-center text-xs text-slate-500">ControlGastos · Tu información en tu espacio personal</p>
    </section>
  </main>
}
export function AppLayout() {
  const location = useLocation()
  const { user, setUser } = useAuth()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const signOut = async () => {
    setBusy(true); setError('')
    try { await api.logout(); setUser(null); navigate('/login', { replace: true }) }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo cerrar la sesión.') }
    finally { setBusy(false) }
  }
  return <div className="min-h-screen bg-slate-50">
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-5 px-6 py-5"><Brand />
        <div className="flex items-center gap-4"><span className="hidden text-sm text-slate-500 sm:block">Hola, {user?.first_name}</span>
          <button className="button-secondary" onClick={signOut} disabled={busy}>{busy ? 'Cerrando…' : 'Cerrar sesión'}</button></div>
      </div>
    </header>
    <SpaceSelector />
    <div className="mx-auto flex max-w-[1600px] flex-col lg:flex-row"><Sidebar /><main className="min-w-0 flex-1 px-5 py-8 sm:px-8">{error ? <p role="alert" className="mb-6 rounded-lg bg-red-50 p-4 text-red-800">{error}</p> : null}<PersonalScope key={location.pathname}><Outlet /></PersonalScope></main></div>
  </div>
}
