import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { privateDestination } from './auth/routes'
import { AppLayout, AuthLayout } from './components/Layout'
import Summary from './finance/Summary'
const AnalyticsPage = lazy(() => import('./analytics/AnalyticsPage'))
const Budgets = lazy(() => import('./analytics/Budgets'))
const Reports = lazy(() => import('./reports/Reports'))
import AuditHistory from './reports/AuditHistory'
import Accounts from './finance/Accounts'
import Classifications from './finance/Classifications'
import MovementForm from './finance/MovementForm'
import History from './finance/History'
import MovementDetail from './finance/MovementDetail'
import Login from './pages/Login'
import Register from './pages/Register'
import Profile from './pages/Profile'
import Security from './pages/Security'
import NotFound from './pages/NotFound'

function SessionGate({ privateRoute }: { privateRoute: boolean }) {
  const { user, loading, error, retry } = useAuth()
  const location = useLocation()
  if (loading) return <main className="flex min-h-screen items-center justify-center" role="status">Comprobando tu sesión…</main>
  if (error) return <main className="flex min-h-screen items-center justify-center px-6"><div className="card max-w-md text-center">
    <p role="alert" className="text-slate-600">{error}</p><button onClick={retry} className="button-primary mt-6">Volver a intentar</button></div></main>
  if (privateRoute && !user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (!privateRoute && user) {
    const from = (location.state as { from?: string } | null)?.from
    return <Navigate to={privateDestination(from)} replace />
  }
  return <Outlet />
}
function Home() {
  const { user, loading } = useAuth()
  return loading ? <p role="status" className="p-10">Comprobando tu sesión…</p> : <Navigate to={user ? '/dashboard' : '/login'} replace />
}
export default function App() {
  return <BrowserRouter><AuthProvider><Suspense fallback={<p role="status" className="p-8">Cargando vista…</p>}><Routes>
    <Route path="/" element={<Home />} />
    <Route element={<SessionGate privateRoute={false} />}><Route element={<AuthLayout />}>
      <Route path="/login" element={<Login />} /><Route path="/registro" element={<Register />} />
    </Route></Route>
    <Route element={<SessionGate privateRoute />}><Route element={<AppLayout />}>
      <Route path="/dashboard" element={<AnalyticsPage key="dashboard" />} /><Route path="/analisis" element={<AnalyticsPage key="analysis" mode="analysis" />} /><Route path="/comparacion" element={<AnalyticsPage key="comparison" mode="comparison" />} /><Route path="/presupuestos" element={<Budgets />} /><Route path="/perfil" element={<Profile />} /><Route path="/seguridad" element={<Security />} />
      <Route path="/cuentas" element={<Accounts />} /><Route path="/clasificaciones" element={<Classifications />} />
      <Route path="/reportes" element={<Reports />} /><Route path="/auditoria" element={<AuditHistory />} />
      <Route path="/gastos/nuevo" element={<MovementForm key="expense" kind="EXPENSE" />} /><Route path="/ingresos/nuevo" element={<MovementForm key="income" kind="INCOME" />} />
      <Route path="/transferir" element={<MovementForm key="transfer" kind="TRANSFER" />} /><Route path="/movimientos" element={<History />} />
      <Route path="/movimientos/:id" element={<MovementDetail />} /><Route path="/resumen" element={<Summary />} />
    </Route></Route>
    <Route path="*" element={<NotFound />} />
  </Routes></Suspense></AuthProvider></BrowserRouter>
}
