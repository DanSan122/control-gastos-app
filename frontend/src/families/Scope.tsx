import { createContext, useContext, useMemo, useLayoutEffect, useRef, type ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { request } from '../lib/api'
import { createFinance, finance as personalFinance } from '../finance/api'
import { LoadState, useResource } from '../finance/ui'

export interface Family {
  id: string
  name: string
  description: string
  currency: 'PEN'
  timezone: string
  role: 'ADMIN' | 'MEMBER'
  status: 'ACTIVE' | 'ARCHIVED'
}
const defaults = {
  family: undefined as Family | undefined,
  finance: personalFinance,
  href: (path: string) => path,
  send: request,
}
const FinancialScope = createContext(defaults)
export const useFinancialScope = () => useContext(FinancialScope)

function Provider({ family, children }: { family?: Family; children: ReactNode }) {
  const controller = useRef(new AbortController())
  useLayoutEffect(() => {
    if (controller.current.signal.aborted) controller.current = new AbortController()
    return () => controller.current.abort()
  }, [])
  const value = useMemo(() => {
    const prefix = family ? `/families/${family.id}` : ''
    const send: typeof request = (path, options = {}) =>
      request(`${prefix}${path}`, {
        ...options,
        signal: options.signal
          ? AbortSignal.any([controller.current.signal, options.signal])
          : controller.current.signal,
        private: family ? false : options.private,
      })
    const href = (path: string) => (family ? `/familias/${family.id}${path}` : path)
    return { family, finance: createFinance(send), href, send }
  }, [family, controller])
  return <FinancialScope.Provider value={value}>{children}</FinancialScope.Provider>
}

export function PersonalScope({ children }: { children: ReactNode }) {
  return <Provider>{children}</Provider>
}

export function FamilyScope({ children }: { children: ReactNode }) {
  const { familyId = '' } = useParams()
  const state = useResource(
    (signal) => request<Family>(`/families/${familyId}/`, { signal }),
    [familyId],
  )
  return (
    <>
      <LoadState {...state} retry={state.reload} />
      {state.error ? (
        <Link className="text-link" to="/familias">
          Volver a mis espacios
        </Link>
      ) : null}
      {state.data && !state.loading && !state.error ? (
        <Provider key={familyId} family={state.data}>
          <div className="mb-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <p className="font-semibold">Espacio familiar: {state.data.name}</p>
            <p className="mt-1 text-sm">
              {state.data.role === 'ADMIN' ? 'Administrador' : 'Integrante'} · {state.data.timezone}{' '}
              ·{' '}
              {state.data.status === 'ARCHIVED'
                ? 'Archivado: solo consultas'
                : 'Finanzas compartidas, independientes de tu espacio personal'}
            </p>
          </div>
          {children}
        </Provider>
      ) : null}
    </>
  )
}
