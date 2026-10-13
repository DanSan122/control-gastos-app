import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { privateDestination } from '../auth/routes'
import { Field, Feedback, SubmitButton, feedbackFrom, type FormFeedback } from '../components/Form'
import { api } from '../lib/api'

export default function Login() {
  const { setUser } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState<FormFeedback>()
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    setBusy(true); setFeedback(undefined)
    try {
      const response = await api.login({ email: String(data.get('email')).trim(), password: String(data.get('password')) })
      setUser(response.user)
      const from = (location.state as { from?: string } | null)?.from
      navigate(privateDestination(from), { replace: true })
    } catch (reason) { setFeedback(feedbackFrom(reason)) }
    finally { setBusy(false) }
  }
  return <>
    <p className="eyebrow">BIENVENIDO DE NUEVO</p><h2 className="page-title mt-3">Entra a tu espacio</h2>
    <p className="mt-3 text-slate-500">Continúa donde lo dejaste.</p>
    <form onSubmit={submit} className="mt-8 space-y-5" aria-busy={busy}>
      <Feedback feedback={feedback} success={(location.state as { registered?: boolean } | null)?.registered ? 'Tu cuenta está lista. Inicia sesión para continuar.' : undefined} />
      <fieldset disabled={busy} className="space-y-5">
        <Field label="Correo electrónico" name="email" type="email" autoComplete="username" maxLength={254} required error={feedback?.fields.email} placeholder="tu@correo.com" />
        <Field label="Contraseña" name="password" type="password" autoComplete="current-password" maxLength={128} required error={feedback?.fields.password} />
        <SubmitButton busy={busy}>Iniciar sesión</SubmitButton>
      </fieldset>
    </form>
    <p className="mt-7 text-center text-sm text-slate-500">¿Es tu primera vez? <Link className="text-link" to="/registro">Crea una cuenta</Link></p>
  </>
}
