import { type FormEvent, useState } from 'react'

import { api, errorMessage } from '../lib/api'
import type { Service } from '../lib/types'

export function ServicePolicyEditor({ service, onSaved }: { service: Service; onSaved: () => Promise<unknown> }) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    const form = new FormData(event.currentTarget)
    try {
      await api.patch(`/services/${service.id}`, {
        allow_cancellations: form.get('allow_cancellations') === 'on',
        cancel_cutoff_hours: Number(form.get('cancel_cutoff_hours')),
        reschedule_cutoff_hours: form.get('reschedule_cutoff_hours') === ''
          ? null : Number(form.get('reschedule_cutoff_hours')),
      })
      await onSaved()
      setOpen(false)
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setBusy(false)
    }
  }

  return <div className="mt-4">
    <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} className="text-sm font-semibold text-[#176848]">{open ? 'Close booking policies' : 'Edit booking policies'}</button>
    {open && <form onSubmit={save} className="mt-4 grid gap-3 rounded-xl bg-[#f5f7f5] p-4">
      <label className="flex items-center gap-2 text-sm font-semibold"><input type="checkbox" name="allow_cancellations" defaultChecked={service.allow_cancellations} className="size-5" /> Allow cancellations</label>
      <label className="text-sm font-semibold">Cancel cutoff (hours)<input name="cancel_cutoff_hours" type="number" min="0" required defaultValue={service.cancel_cutoff_hours} /></label>
      <label className="text-sm font-semibold">Reschedule cutoff (hours)<input name="reschedule_cutoff_hours" type="number" min="0" defaultValue={service.reschedule_cutoff_hours ?? ''} placeholder="Disabled when blank" /></label>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <button type="submit" disabled={busy} className="primary">{busy ? 'Saving…' : 'Save policies'}</button>
    </form>}
  </div>
}
