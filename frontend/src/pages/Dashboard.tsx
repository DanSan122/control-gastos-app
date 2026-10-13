import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function Dashboard() {
  const { user } = useAuth()
  return <>
    <p className="eyebrow">TU ESPACIO PERSONAL</p><h1 className="page-title mt-3">Bienvenido, {user?.first_name}</h1>
    <p className="mt-3 text-slate-500">Tu cuenta está lista. Este es el comienzo.</p>
    <section className="mt-9 overflow-hidden rounded-2xl bg-slate-900 p-8 text-white sm:p-12">
      <span className="inline-block rounded-full bg-emerald-400/10 px-3 py-1 text-xs font-medium text-emerald-300">Un paso a la vez</span>
      <h2 className="mt-6 max-w-xl text-3xl font-semibold tracking-tight">Todo empieza con un espacio propio.</h2>
      <p className="mt-4 max-w-xl leading-relaxed text-slate-300">Pronto podrás organizar tus ingresos y gastos aquí. Mientras tanto, configura tus preferencias y mantén tu cuenta segura.</p>
      <Link to="/perfil" className="mt-7 inline-flex rounded-lg bg-white px-5 py-3 text-sm font-semibold text-slate-900 hover:bg-emerald-50">Completar mi perfil →</Link>
    </section>
    <div className="mt-6 grid gap-6 md:grid-cols-2">
      <section className="card"><p className="eyebrow">TUS PREFERENCIAS</p><h2 className="mt-4 text-xl font-semibold">A tu manera</h2>
        <dl className="mt-5 space-y-3 text-sm"><div className="flex justify-between gap-4"><dt className="text-slate-500">Moneda</dt><dd className="font-medium">{user?.currency}</dd></div>
          <div className="flex justify-between gap-4"><dt className="text-slate-500">Zona horaria</dt><dd className="font-medium">{user?.timezone}</dd></div></dl>
      </section>
      <section className="card"><p className="eyebrow">SEGURIDAD</p><h2 className="mt-4 text-xl font-semibold">Cuida tu cuenta</h2>
        <p className="mt-4 text-sm leading-relaxed text-slate-500">Puedes actualizar tu contraseña cuando lo necesites. Las otras sesiones se cerrarán al hacerlo.</p>
        <Link to="/seguridad" className="text-link mt-5 inline-block text-sm">Gestionar contraseña →</Link>
      </section>
    </div>
  </>
}
