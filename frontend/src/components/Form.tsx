import { useId, type InputHTMLAttributes, type ReactNode } from 'react'
import { ApiError } from '../lib/api'

export interface FormFeedback { message: string; fields: Record<string, string[]> }
export function feedbackFrom(error: unknown): FormFeedback {
  if (error instanceof ApiError) return { message: error.message, fields: error.fields }
  return { message: error instanceof Error ? error.message : 'Ha ocurrido un error. Inténtalo de nuevo.', fields: {} }
}
export function Field({ label, error, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string[] }) {
  const id = useId()
  return <div className="space-y-2">
    <label htmlFor={id} className="block text-sm font-medium text-slate-700">{label}</label>
    <input {...props} id={id} className="input" aria-invalid={Boolean(error?.length)} aria-describedby={error?.length ? `${id}-error` : undefined} />
    {error?.length ? <p id={`${id}-error`} className="text-sm text-red-700">{error.join(' ')}</p> : null}
  </div>
}
export function Feedback({ feedback, success }: { feedback?: FormFeedback; success?: string }) {
  return <>
    {feedback?.message ? <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{feedback.message}</div> : null}
    {success ? <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{success}</div> : null}
  </>
}
export function SubmitButton({ busy, children }: { busy: boolean; children: ReactNode }) {
  return <button type="submit" className="button-primary w-full" disabled={busy}>{busy ? 'Procesando…' : children}</button>
}
