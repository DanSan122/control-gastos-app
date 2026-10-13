import { useState, type FormEvent } from 'react'
import { useAuth } from '../auth/AuthContext'
import { Field, Feedback, SubmitButton, feedbackFrom, type FormFeedback } from '../components/Form'
import { api, type User } from '../lib/api'

export default function Profile() {
  const { user, setUser } = useAuth()
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState<FormFeedback>()
  const [success, setSuccess] = useState('')
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    setBusy(true); setFeedback(undefined); setSuccess('')
    try {
      const updated = await api.profile({ first_name: String(data.get('first_name')).trim(), last_name: String(data.get('last_name')).trim(),
        timezone: String(data.get('timezone')).trim(), currency: String(data.get('currency')) as User['currency'] })
      setUser(updated); setSuccess('Tu perfil se actualizó correctamente.')
    } catch (reason) { setFeedback(feedbackFrom(reason)) }
    finally { setBusy(false) }
  }
  return <>
    <p className="eyebrow">MI PERFIL</p><h1 className="page-title mt-3">Tus datos y preferencias</h1>
    <p className="mt-3 text-slate-500">Haz que tu espacio se adapte a ti.</p>
    <section className="card mt-8 max-w-2xl">
      <div className="mb-7 border-b border-slate-100 pb-6"><p className="text-sm text-slate-500">Correo de tu cuenta</p><p className="mt-1 break-all font-medium">{user?.email}</p>
        <p className="mt-3 text-xs text-slate-500">Miembro desde {user ? new Intl.DateTimeFormat('es-PE', { dateStyle: 'long', timeZone: user.timezone }).format(new Date(user.date_joined)) : ''}</p></div>
      <form onSubmit={submit} className="space-y-5" aria-busy={busy}>
        <Feedback feedback={feedback} success={success} /><fieldset disabled={busy} className="space-y-5">
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Nombre" name="first_name" defaultValue={user?.first_name} autoComplete="given-name" maxLength={150} required error={feedback?.fields.first_name} />
            <Field label="Apellidos" name="last_name" defaultValue={user?.last_name} autoComplete="family-name" maxLength={150} required error={feedback?.fields.last_name} />
          </div>
          <Field label="Zona horaria" name="timezone" defaultValue={user?.timezone} maxLength={64} required list="timezones" error={feedback?.fields.timezone} />
          <datalist id="timezones"><option value="America/Lima" /><option value="UTC" /><option value="America/Bogota" /><option value="Europe/Madrid" /></datalist>
          <div className="space-y-2"><label htmlFor="currency" className="block text-sm font-medium text-slate-700">Moneda preferida</label>
            <select id="currency" name="currency" className="input" defaultValue={user?.currency} aria-invalid={Boolean(feedback?.fields.currency)} aria-describedby={feedback?.fields.currency ? 'currency-error' : undefined}>
              <option value="PEN">PEN · Sol peruano</option><option value="USD">USD · Dólar estadounidense</option><option value="EUR">EUR · Euro</option>
            </select>{feedback?.fields.currency ? <p id="currency-error" className="text-sm text-red-700">{feedback.fields.currency.join(' ')}</p> : null}
          </div><SubmitButton busy={busy}>Guardar cambios</SubmitButton>
        </fieldset>
      </form>
    </section>
  </>
}
