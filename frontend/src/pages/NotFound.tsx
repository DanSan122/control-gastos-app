import { Link } from 'react-router-dom'
export default function NotFound() {
  return <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6 text-center"><div>
    <p className="eyebrow">404 · PÁGINA NO ENCONTRADA</p><h1 className="page-title mt-5">Este camino no existe</h1>
    <p className="mt-4 text-slate-500">Comprueba la dirección o vuelve a tu espacio.</p><Link to="/" className="button-primary mt-8 inline-block">Volver al inicio</Link>
  </div></main>
}
