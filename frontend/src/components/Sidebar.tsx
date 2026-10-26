import { NavLink, useLocation } from 'react-router-dom'

const links = [
  ['/dashboard', 'Inicio'], ['/cuentas', 'Mis cuentas'], ['/clasificaciones', 'Áreas y categorías'],
  ['/analisis', 'Análisis de gastos'], ['/comparacion', 'Comparar periodos'], ['/presupuestos', 'Presupuestos'],
  ['/reportes', 'Reportes'], ['/auditoria', 'Auditoría'],
  ['/recurrentes', 'Movimientos recurrentes'],
  ['/gastos/nuevo', 'Registrar gasto'], ['/ingresos/nuevo', 'Registrar ingreso'], ['/transferir', 'Transferir dinero'],
  ['/movimientos', 'Historial'], ['/resumen', 'Resumen financiero'], ['/perfil', 'Mi perfil'], ['/seguridad', 'Seguridad'],
]
export default function Sidebar() {
  const location = useLocation()
  const familyPrefix = location.pathname.match(/^\/familias\/[0-9a-f-]{36}(?=\/)/i)?.[0]
  const visibleLinks = familyPrefix ? [...links.filter(([to]) => !['/recurrentes', '/perfil', '/seguridad'].includes(to)).map(([to, label]) => [familyPrefix + to, label]), [familyPrefix + '/integrantes', 'Integrantes'], [familyPrefix + '/configuracion', 'Configuración familiar']] : links

  return <aside className="min-w-0 border-b border-slate-200 bg-white lg:w-60 lg:shrink-0 lg:border-b-0 lg:border-r">
    <nav aria-label="Navegación principal" className="flex gap-2 overflow-x-auto p-4 lg:sticky lg:top-0 lg:flex-col lg:gap-1 lg:overflow-visible lg:p-5">
      {visibleLinks.map(([to, label]) => <NavLink key={to} to={to} end className={({ isActive }) => `whitespace-nowrap rounded-xl px-4 py-3 text-sm font-medium ${isActive ? 'bg-emerald-50 text-emerald-800' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'}`}>{label}</NavLink>)}
    </nav>
  </aside>
}
