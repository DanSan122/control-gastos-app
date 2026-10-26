import { useFinancialScope } from '../families/Scope'
import { useState, type FormEvent } from 'react'
import { Field, SubmitButton, type FormFeedback } from '../components/Form'
import { type Area, type Category, type Subcategory } from './api'
import { FinanceFeedback, LoadState, PageHeader, Select, feedbackFrom, useResource } from './ui'

type Catalog = { areas: Area[]; categories: Category[]; subcategories: Subcategory[] }
function ClassificationEditor({ resource, label, records, parents, parentField, reload }: {
  resource: string; label: string; records: Area[]; parents?: Area[]; parentField?: 'area' | 'category'; reload: () => void
}) {
  const { finance, family } = useFinancialScope()
  const [editing, setEditing] = useState<Area>()
  const [error, setError] = useState<FormFeedback>()
  const [success, setSuccess] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form)
    setBusy(true); setError(undefined); setSuccess('')
    try {
      await finance.save(resource, { name: String(data.get('name')).trim(), ...(parentField ? { [parentField]: data.get(parentField) } : {}),
        ...(resource === 'categories' ? { kind: data.get('kind') } : {}), ...(editing ? { is_active: data.get('is_active') === 'on' } : {}) }, editing?.id)
      setEditing(undefined); form.reset(); reload(); setSuccess('Clasificación guardada.')
    } catch (reason) { setError(feedbackFrom(reason)) } finally { setBusy(false) }
  }
  const deactivate = async (item: Area) => {
    if (!window.confirm(`¿Desactivar ${item.name}? Los movimientos asociados se conservarán.`)) return
    setBusy(true); setError(undefined)
    try { await finance.remove(resource, item.id); reload() } catch (reason) { setError(feedbackFrom(reason)) } finally { setBusy(false) }
  }
  const parentValue = editing && parentField ? (editing as Category & Subcategory)[parentField] : ''
  return <section className="card min-w-0"><h2 className="mb-5 text-xl font-semibold">{label}</h2><FinanceFeedback error={error} success={success} />
    <form aria-label={`${editing ? 'Editar' : 'Nueva'} ${label.toLowerCase()}`} className="mt-4" onSubmit={submit} key={editing?.id || 'new'}><fieldset disabled={busy || Boolean(family && family.role !== 'ADMIN')} className="space-y-4">
      <Field label={`Nombre de ${label.toLowerCase()}`} name="name" defaultValue={editing?.name} required maxLength={100} />
      {parentField ? <Select label={parentField === 'area' ? 'Área padre' : 'Categoría padre'} name={parentField} defaultValue={parentValue} required><option value="">Selecciona</option>
        {parents?.filter((item) => item.is_active || item.id === parentValue).map((item) => <option key={item.id} value={item.id}>{item.name}{'kind' in item ? ` · ${(item as Category).kind === 'INCOME' ? 'Ingreso' : 'Gasto'}` : ''}</option>)}</Select> : null}
      {resource === 'categories' ? <Select label="Tipo de categoría" name="kind" defaultValue={(editing as Category | undefined)?.kind || 'EXPENSE'}><option value="EXPENSE">Gasto</option><option value="INCOME">Ingreso</option></Select> : null}
      {editing ? <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="is_active" defaultChecked={editing.is_active} />Activa</label> : null}
      <SubmitButton busy={busy}>{editing ? 'Guardar cambios' : `Crear ${label.toLowerCase()}`}</SubmitButton>
      {editing ? <button type="button" className="button-secondary" onClick={() => setEditing(undefined)}>Cancelar</button> : null}
    </fieldset></form>
    <ul className="mt-7 divide-y divide-slate-100">{records.map((item) => <li key={item.id} className="py-3">
      <p className="break-words font-medium">{item.name} <span className="text-xs font-normal text-slate-400">{item.is_active ? '' : 'Inactiva'}</span></p>
      {parentField ? <p className="mt-1 text-xs text-slate-500">{parents?.find((parent) => parent.id === (item as Category & Subcategory)[parentField])?.name}{'kind' in item ? ` · ${(item as Category).kind === 'INCOME' ? 'Ingreso' : 'Gasto'}` : ''}</p> : null}
      <div className="mt-2 flex gap-4 text-sm"><button type="button" className="text-link" disabled={busy || Boolean(family && family.role !== 'ADMIN')} onClick={() => setEditing(item)}>Editar</button>{item.is_active ? <button className="text-red-700" disabled={busy || Boolean(family && family.role !== 'ADMIN')} onClick={() => deactivate(item)}>Desactivar</button> : null}</div>
    </li>)}</ul>{!records.length ? <p className="mt-5 text-sm text-slate-500">Sin clasificaciones todavía.</p> : null}
  </section>
}
export default function Classifications() {
  const { finance, family } = useFinancialScope()
  const state = useResource<Catalog>(async (signal) => {
    const [areas, categories, subcategories] = await Promise.all([finance.all<Area>('areas', '', signal), finance.all<Category>('categories', '', signal), finance.all<Subcategory>('subcategories', '', signal)])
    return { areas, categories, subcategories }
  })
  return <><PageHeader eyebrow="CLASIFICACIONES" title="Organiza tus movimientos">Área → categoría → subcategoría. Desactiva lo que no uses; tu historial permanece.</PageHeader><LoadState {...state} retry={state.reload} />
    {state.data ? <div className="grid items-start gap-6 xl:grid-cols-3">
      <ClassificationEditor resource="areas" label="Área" records={state.data.areas} reload={state.reload} />
      <ClassificationEditor resource="categories" label="Categoría" records={state.data.categories} parents={state.data.areas} parentField="area" reload={state.reload} />
      <ClassificationEditor resource="subcategories" label="Subcategoría" records={state.data.subcategories} parents={state.data.categories} parentField="category" reload={state.reload} />
    </div> : null}</>
}
