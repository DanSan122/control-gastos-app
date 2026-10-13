import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Field, Feedback, SubmitButton, feedbackFrom, type FormFeedback } from '../components/Form'
import { api } from '../lib/api'

export default function Register() {
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState<FormFeedback>()
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const password = String(data.get('password'))
    if (password !== data.get('confirm')) {
      setFeedback({ message: 'Las contraseñas no coinciden.', fields: { confirm: ['Repite la misma contraseña.'] } }); return
    }
    setBusy(true); setFeedback(undefined)
    try {
      await api.register({ email: String(data.get('email')).trim(), password,
        first_name: String(data.get('first_name')).trim(), last_name: String(data.get('last_name')).trim() })
      navigate('/login', { replace: true, state: { registered: true } })
    } catch (reason) { setFeedback(feedbackFrom(reason)) }
    finally { setBusy(false) }
  }
  return <>
    <p className="eyebrow">EMPIEZA AQUÍ</p><h2 className="page-title mt-3">Crea tu cuenta</h2>
    <p className="mt-3 text-slate-500">Tu espacio personal comienza con este paso.</p>
    <form onSubmit={submit} className="mt-8 space-y-5" aria-busy={busy}>
      <Feedback feedback={feedback} /><fieldset disabled={busy} className="space-y-5">
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Nombre" name="first_name" autoComplete="given-name" maxLength={150} required error={feedback?.fields.first_name} />
          <Field label="Apellidos" name="last_name" autoComplete="family-name" maxLength={150} required error={feedback?.fields.last_name} />
        </div>
        <Field label="Correo electrónico" name="email" type="email" autoComplete="email" maxLength={254} required error={feedback?.fields.email} />
        <Field label="Contraseña" name="password" type="password" autoComplete="new-password" minLength={8} maxLength={128} required error={feedback?.fields.password} />
        <p className="text-xs leading-relaxed text-slate-500">Usa al menos 8 caracteres. Evita contraseñas comunes, solo números o similares a tu nombre y correo.</p>
        <Field label="Confirmar contraseña" name="confirm" type="password" autoComplete="new-password" minLength={8} maxLength={128} required error={feedback?.fields.confirm} />
        <SubmitButton busy={busy}>Crear cuenta</SubmitButton>
      </fieldset>
    </form>
    <p className="mt-7 text-center text-sm text-slate-500">¿Ya tienes una cuenta? <Link className="text-link" to="/login">Inicia sesión</Link></p>
  </>
}
