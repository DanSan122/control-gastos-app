import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { request } from '../lib/api'
import type { Page } from '../finance/api'
import { Field, SubmitButton } from '../components/Form'
import { LoadState, PageHeader, Select, useResource } from '../finance/ui'
import { FamilyScope, useFinancialScope, type Family } from './Scope'

export interface Member {
  id: string
  user: string
  name: string
  role: 'ADMIN' | 'MEMBER'
  status: 'ACTIVE' | 'REMOVED'
}
interface Invitation {
  id: string
  family: string
  family_name: string
  invited_email: string
  status: string
  expires_at: string
}
export function Families() {
  const state = useResource((signal) =>
    request<Page<Family>>('/families/?page_size=100', { signal }),
  )
  return (
    <>
      <PageHeader eyebrow="ESPACIOS" title="Mis familias">
        Cada espacio conserva sus cuentas y movimientos separados de tu información personal.
      </PageHeader>
      <div className="mb-6 flex flex-wrap gap-3">
        <Link className="button-primary" to="/familias/nueva">
          Crear familia
        </Link>
        <Link className="button-secondary" to="/familias/invitaciones">
          Mis invitaciones
        </Link>
        <Link className="button-secondary" to="/dashboard">
          Mi espacio personal
        </Link>
      </div>
      <LoadState {...state} retry={state.reload} />
      {state.data && !state.loading && !state.error ? (
        <div className="grid gap-5 sm:grid-cols-2">
          {state.data.results.map((family) => (
            <Link key={family.id} className="card" to={`/familias/${family.id}/dashboard`}>
              <h2 className="font-semibold">{family.name}</h2>
              <p className="mt-3 text-sm text-slate-500">
                {family.role === 'ADMIN' ? 'Administrador' : 'Integrante'} ·{' '}
                {family.status === 'ACTIVE' ? 'Activa' : 'Archivada'}
              </p>
            </Link>
          ))}
          {!state.data.count ? (
            <p className="card text-slate-500">
              Todavía no perteneces a ninguna familia. Puedes crear una o aceptar una invitación.
            </p>
          ) : null}
        </div>
      ) : null}
    </>
  )
}

export function FamilyForm({ edit = false }: { edit?: boolean }) {
  const { family } = useFinancialScope()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (
      edit &&
      !window.confirm(
        '¿Guardar la configuración familiar? La zona horaria afecta los periodos de reportes y presupuestos.',
      )
    )
      return
    const values = new FormData(event.currentTarget)
    setBusy(true)
    setError('')
    setSuccess('')
    try {
      const saved = await request<Family>(`/families/${edit ? family?.id + '/' : ''}`, {
        method: edit ? 'PATCH' : 'POST',
        data: {
          name: values.get('name'),
          description: values.get('description'),
          timezone: values.get('timezone'),
          currency: 'PEN',
          ...(edit ? { status: values.get('status') } : {}),
        },
      })
      if (!edit) navigate(`/familias/${saved.id}/dashboard`)
      else {
        setSuccess('Configuración guardada.')
        navigate('/familias')
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No se pudo guardar.')
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <PageHeader eyebrow="FAMILIAS" title={edit ? 'Configuración familiar' : 'Crear familia'}>
        Crear un espacio no modifica tus cuentas ni tus movimientos personales.
      </PageHeader>
      {error ? (
        <p role="alert" className="mb-4 text-red-700">
          {error}
        </p>
      ) : null}
      {success ? <p role="status">{success}</p> : null}
      <form onSubmit={submit} className="card max-w-2xl">
        <fieldset disabled={busy || (edit && family?.role !== 'ADMIN')} className="space-y-5">
          <Field
            label="Nombre de familia"
            name="name"
            required
            maxLength={100}
            defaultValue={family?.name}
          />
          <Field
            label="Descripción familiar"
            name="description"
            maxLength={500}
            defaultValue={family?.description}
          />
          <Field
            label="Zona horaria IANA"
            name="timezone"
            required
            defaultValue={family?.timezone || 'America/Lima'}
          />
          {edit ? (
            <Select label="Estado familiar" name="status" defaultValue={family?.status}>
              <option value="ACTIVE">Activa</option>
              <option value="ARCHIVED">Archivada (solo lectura)</option>
            </Select>
          ) : null}
          <SubmitButton busy={busy}>
            {edit ? 'Guardar configuración' : 'Crear espacio familiar'}
          </SubmitButton>
        </fieldset>
      </form>
    </>
  )
}

export function Invitations() {
  const [page, setPage] = useState(1)
  const state = useResource(
    (signal) => request<Page<Invitation>>(`/families/invitations/mine/?page=${page}`, { signal }),
    [page],
  )
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  async function act(id: string, action: 'accept' | 'reject') {
    if (
      !window.confirm(
        action === 'accept'
          ? '¿Aceptar el acceso al espacio familiar? Tu información personal seguirá privada.'
          : '¿Rechazar esta invitación?',
      )
    )
      return
    setBusy(id)
    setError('')
    try {
      await request(`/families/invitations/${id}/${action}/`, { method: 'POST', data: {} })
      state.reload()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No se pudo responder.')
      state.reload()
    } finally {
      setBusy('')
    }
  }
  return (
    <>
      <PageHeader eyebrow="INVITACIONES PRIVADAS" title="Mis invitaciones">
        Caducan a los siete días. No otorgan acceso hasta que las aceptas.
      </PageHeader>
      {error ? (
        <p role="alert" className="mb-5 text-red-700">
          {error}
        </p>
      ) : null}
      <LoadState {...state} retry={state.reload} />
      {state.data && !state.loading && !state.error ? (
        <>
          <div className="space-y-4">
            {state.data.results.map((invite) => (
              <article key={invite.id} className="card">
                <h2 className="font-semibold">{invite.family_name}</h2>
                <p className="mt-2 text-sm text-slate-500">
                  {invite.status} · Vence {new Date(invite.expires_at).toLocaleDateString('es-PE')}
                </p>
                {invite.status === 'PENDING' ? (
                  <div className="mt-4 flex gap-3">
                    <button
                      className="button-primary"
                      disabled={Boolean(busy)}
                      onClick={() => void act(invite.id, 'accept')}
                    >
                      Aceptar invitación
                    </button>
                    <button
                      className="button-secondary"
                      disabled={Boolean(busy)}
                      onClick={() => void act(invite.id, 'reject')}
                    >
                      Rechazar
                    </button>
                  </div>
                ) : null}
              </article>
            ))}
            {!state.data.count ? <p className="card">No tienes invitaciones.</p> : null}
          </div>
          <Pager page={page} data={state.data} setPage={setPage} />
        </>
      ) : null}
      <Link className="text-link mt-6 inline-block" to="/familias">
        Ver mis familias
      </Link>
    </>
  )
}

export function Pager({
  page,
  data,
  setPage,
}: {
  page: number
  data: { next: string | null; previous: string | null }
  setPage: (value: number) => void
}) {
  return (
    <div className="my-5 flex items-center gap-4">
      <button
        className="button-secondary"
        disabled={!data.previous}
        onClick={() => setPage(page - 1)}
      >
        Anterior
      </button>
      <span className="text-sm">Página {page}</span>
      <button className="button-secondary" disabled={!data.next} onClick={() => setPage(page + 1)}>
        Siguiente
      </button>
    </div>
  )
}

export function Members() {
  const { family } = useFinancialScope()
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const prefix = `/families/${family?.id}`
  const members = useResource(
    (signal) => request<Page<Member>>(`${prefix}/members/?page=${page}`, { signal }),
    [page],
  )
  const invitations = useResource((signal) =>
    family?.role === 'ADMIN'
      ? request<Page<Invitation>>(`${prefix}/invitations/?page_size=100`, { signal })
      : Promise.resolve(undefined),
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  async function perform(path: string, method: 'POST' | 'PATCH' | 'DELETE', data?: unknown) {
    if (!window.confirm('¿Confirmar esta operación familiar?')) return
    setBusy(true)
    setError('')
    setSuccess('')
    try {
      const response = await request<{ detail?: string } | undefined>(path, { method, data })
      setSuccess(response?.detail || 'Operación completada.')
      members.reload()
      invitations.reload()
      if (path.endsWith('/leave/')) navigate('/familias')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No se pudo completar.')
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <PageHeader eyebrow="COLABORACIÓN" title="Integrantes familiares">
        Administrador: gestión compartida. Integrante: consulta y gestión de sus propios
        movimientos.
      </PageHeader>
      {error ? (
        <p role="alert" className="mb-5 text-red-700">
          {error}
        </p>
      ) : null}
      {success ? (
        <p role="status" className="mb-5 text-emerald-700">
          {success}
        </p>
      ) : null}
      {family?.role === 'ADMIN' ? (
        <form
          className="card mb-6 flex flex-wrap items-end gap-4"
          aria-label="Invitar familiar"
          onSubmit={(event) => {
            event.preventDefault()
            void perform(`${prefix}/invitations/`, 'POST', {
              email: new FormData(event.currentTarget).get('email'),
            })
          }}
        >
          <Field label="Correo del familiar registrado" name="email" type="email" required />
          <button disabled={busy} className="button-primary">
            Enviar invitación interna
          </button>
          <p className="w-full text-xs text-slate-500">
            No se envían correos ni se confirma si una cuenta existe.
          </p>
        </form>
      ) : null}
      <LoadState {...members} retry={members.reload} />
      {members.data && !members.loading && !members.error ? (
        <>
          <div className="space-y-3">
            {members.data.results.map((member) => (
              <article className="card" key={member.id}>
                <h2 className="font-semibold">{member.name}</h2>
                <p className="mt-2 text-sm">
                  {member.role === 'ADMIN' ? 'Administrador' : 'Integrante'} ·{' '}
                  {member.status === 'ACTIVE' ? 'Activo' : 'Retirado'}
                </p>
                {family?.role === 'ADMIN' && member.status === 'ACTIVE' ? (
                  <div className="mt-4 flex flex-wrap gap-3">
                    <button
                      disabled={busy}
                      className="button-secondary"
                      onClick={() =>
                        void perform(`${prefix}/members/${member.id}/`, 'PATCH', {
                          role: member.role === 'ADMIN' ? 'MEMBER' : 'ADMIN',
                        })
                      }
                    >
                      {member.role === 'ADMIN' ? 'Cambiar a integrante' : 'Hacer administrador'}
                    </button>
                    <button
                      disabled={busy}
                      className="button-secondary text-red-700"
                      onClick={() => void perform(`${prefix}/members/${member.id}/`, 'DELETE')}
                    >
                      Retirar integrante
                    </button>
                  </div>
                ) : null}
              </article>
            ))}
          </div>
          <Pager page={page} setPage={setPage} data={members.data} />
        </>
      ) : null}
      {family?.role === 'ADMIN' ? (
        <section className="card mt-6">
          <h2 className="font-semibold">Invitaciones de la familia</h2>
          <LoadState {...invitations} retry={invitations.reload} />
          {invitations.data?.results.map((invite) => (
            <div
              key={invite.id}
              className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t pt-4"
            >
              <span className="text-sm">
                {invite.invited_email} · {invite.status}
              </span>
              {invite.status === 'PENDING' ? (
                <button
                  className="button-secondary"
                  disabled={busy}
                  onClick={() =>
                    void perform(`${prefix}/invitations/${invite.id}/revoke/`, 'POST', {})
                  }
                >
                  Revocar invitación
                </button>
              ) : null}
            </div>
          ))}
        </section>
      ) : null}
      <button
        className="button-secondary mt-6 text-red-700"
        disabled={busy}
        onClick={() => void perform(`${prefix}/leave/`, 'POST', {})}
      >
        Salir de la familia
      </button>
    </>
  )
}

export function FamilyScreen({ children }: { children: ReactNode }) {
  const { familyId } = useParams()
  const location = useLocation()
  // Remount every route and space: abort old reads/writes and discard all drafts/filters.
  return <FamilyScope key={familyId + location.pathname}>{children}</FamilyScope>
}

export function SpaceSelector() {
  const location = useLocation()
  const navigate = useNavigate()
  const active = location.pathname.match(/^\/familias\/([0-9a-f-]{36})\//i)?.[1] || ''
  const state = useResource(
    (signal) => request<Page<Family>>('/families/?page_size=100', { signal }),
    [location.pathname],
  )
  return (
    <div className="border-b border-slate-200 bg-white px-5 py-3">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3">
        <label className="text-sm font-medium" htmlFor="financial-space">
          Espacio activo
        </label>
        <select
          id="financial-space"
          aria-label="Espacio activo"
          className="input max-w-xs"
          value={active}
          onChange={(event) =>
            navigate(
              event.target.value === 'create'
                ? '/familias/nueva'
                : event.target.value
                  ? `/familias/${event.target.value}/dashboard`
                  : '/dashboard',
            )
          }
        >
          <option value="">Mi espacio personal</option>
          {active && !state.data?.results.some((family) => family.id === active) ? (
            <option value={active}>Familia actual{state.loading ? ' (cargando…)' : ' (no disponible)'}</option>
          ) : null}
          {state.data?.results.map((family) => (
            <option key={family.id} value={family.id}>
              Familia: {family.name}
            </option>
          ))}
          <option value="create">Crear familia</option>
        </select>
        <Link className="text-link text-sm" to="/familias">
          Mis familias
        </Link>
        <Link className="text-link text-sm" to="/familias/invitaciones">
          Invitaciones
        </Link>
        {state.error ? (
          <span role="alert" className="text-sm text-red-700">
            No se pudieron cargar tus espacios.
          </span>
        ) : null}
      </div>
    </div>
  )
}
