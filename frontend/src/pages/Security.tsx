import { useState, type FormEvent } from 'react'
import { Field, Feedback, SubmitButton, feedbackFrom, type FormFeedback } from '../components/Form'
import { api } from '../lib/api'

export default function Security() {
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState<FormFeedback>()
  const [success, setSuccess] = useState('')
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    setSuccess('')
    if (data.get('new_password') !== data.get('confirm')) {
      setFeedback({ message: 'Las contraseñas no coinciden.', fields: { confirm: ['Repite la misma contraseña.'] } }); return
    }
    setBusy(true); setFeedback(undefined)
    try {
      await api.changePassword({ current_password: String(data.get('current_password')), new_password: String(data.get('new_password')) })
      form.reset(); setSuccess('Contraseña actualizada. Tu sesión actual sigue abierta; las demás se cerrarán.')
    } catch (reason) { setFeedback(feedbackFrom(reason)) }
    finally { setBusy(false) }
  }
  return <>
    <p className="eyebrow">SEGURIDAD</p><h1 className="page-title mt-3">Actualiza tu contraseña</h1>
    <p className="mt-3 text-slate-500">Una contraseña única ayuda a proteger tu cuenta.</p>
    <section className="card mt-8 max-w-xl"><form onSubmit={submit} className="space-y-5" aria-busy={busy}>
      <Feedback feedback={feedback} success={success} /><fieldset disabled={busy} className="space-y-5">
        <Field label="Contraseña actual" name="current_password" type="password" autoComplete="current-password" maxLength={128} required error={feedback?.fields.current_password} />
        <Field label="Nueva contraseña" name="new_password" type="password" autoComplete="new-password" minLength={8} maxLength={128} required error={feedback?.fields.new_password} />
        <p className="text-xs leading-relaxed text-slate-500">Mínimo 8 caracteres; debe ser diferente a la actual y no ser común, solo numérica ni similar a tus datos.</p>
        <Field label="Confirmar nueva contraseña" name="confirm" type="password" autoComplete="new-password" minLength={8} maxLength={128} required error={feedback?.fields.confirm} />
        <SubmitButton busy={busy}>Cambiar contraseña</SubmitButton>
      </fieldset>
    </form></section>
  </>
}
