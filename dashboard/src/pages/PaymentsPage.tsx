import { type FormEvent, useEffect, useState } from 'react'
import { api, errorMessage } from '../lib/api'

type Settings = { configured: boolean; enabled: boolean; key_id_masked?: string; webhook_url?: string }
type Booking = {
  booking_reference: string; service_name: string; booking_date: string;
  booking_status: string; payment_status: string; amount_paid: string; balance_due: string;
  payment_review_required: boolean;
  provider_status: string | null; receipt: string | null; reconciliation_state: string | null;
}

export function PaymentsPage() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [bookings, setBookings] = useState<Booking[]>([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  async function refresh() {
    const [configuration, recent] = await Promise.all([
      api.get<Settings>('/merchants/me/payment-settings'),
      api.get<Booking[]>('/merchants/me/bookings'),
    ])
    setSettings(configuration.data); setBookings(recent.data)
  }
  useEffect(() => { void Promise.resolve().then(refresh).catch((error) => setMessage(errorMessage(error))) }, [])

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    const element = event.currentTarget
    const form = new FormData(element)
    setBusy(true); setMessage('Checking Test credentials…')
    try {
      const { data } = await api.put<Settings>('/merchants/me/payment-settings', {
        mode: 'TEST', key_id: form.get('key_id'), key_secret: form.get('key_secret'),
        webhook_secret: form.get('webhook_secret'),
      })
      setSettings(data); element.reset()
      setMessage('Test configuration saved. Configure the webhook URL below in Razorpay.')
    } catch (error) { setMessage(errorMessage(error)) }
    finally { setBusy(false) }
  }

  async function disconnect() {
    setBusy(true)
    try { await api.delete('/merchants/me/payment-settings'); await refresh(); setMessage('New payments disconnected. Existing payments can still reconcile.') }
    catch (error) { setMessage(errorMessage(error)) }
    finally { setBusy(false) }
  }

  return <div className="mx-auto max-w-5xl space-y-7">
    <header><h1 className="text-3xl font-bold">Test payments</h1><p className="mt-2 text-[#68756e]">Connect your merchant Razorpay Test account. Live payments are unavailable.</p></header>
    <section className="panel space-y-4">
      <h2>Razorpay configuration</h2>
      <p>{settings?.enabled ? `Connected · ${settings.key_id_masked}` : 'Disconnected'}</p>
      <form onSubmit={save} className="grid gap-4" autoComplete="off">
        <label>Test Key ID<input required name="key_id" pattern="rzp_test_[A-Za-z0-9]+" placeholder="rzp_test_…" autoComplete="off" /></label>
        <label>Test Key Secret<input required name="key_secret" type="password" minLength={8} autoComplete="new-password" /></label>
        <label>Webhook secret<input required name="webhook_secret" type="password" minLength={16} autoComplete="new-password" /></label>
        <p className="text-sm">Secrets are write-only. Saving creates a new configuration and webhook URL; previous versions remain available for outstanding payments.</p>
        <button disabled={busy} className="primary">{busy ? 'Please wait…' : settings?.configured ? 'Save new credential version' : 'Connect Test account'}</button>
      </form>
      {settings?.webhook_url && <div className="space-y-2 text-sm"><p className="font-semibold">Webhook URL</p><code className="block break-all rounded bg-gray-100 p-3">{settings.webhook_url}</code><p>In Razorpay Test Mode, enable Automatic Capture and subscribe to payment.captured and payment.failed with the webhook secret you entered.</p><p>When rotating, keep the previous webhook endpoint configured for outstanding payment retries.</p></div>}
      {settings?.enabled && <button disabled={busy} onClick={() => void disconnect()} className="rounded-xl border px-4 py-2">Disconnect new payments</button>}
    </section>
    {message && <p role="status" className="rounded-xl bg-white p-4">{message}</p>}
    <section className="panel"><div className="flex items-center justify-between"><h2>Latest 50 bookings</h2><button onClick={() => void refresh().catch((error) => setMessage(errorMessage(error)))}>Refresh</button></div>
      <div className="mt-4 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th>Booking</th><th>Status</th><th>Paid / balance</th></tr></thead><tbody>{bookings.map((booking) => <tr key={booking.booking_reference} className="border-t"><td className="p-3">{booking.service_name}<br />{booking.booking_date}<br />{booking.booking_reference}</td><td className="p-3">{booking.booking_status}<br />{booking.payment_status}<br />{booking.provider_status}{booking.reconciliation_state === "DUPLICATE_CAPTURE_REVIEW" && <p>Duplicate capture needs investigation</p>}{booking.receipt && <p className="text-xs">{booking.receipt}</p>}{booking.payment_review_required && <p className="font-bold text-amber-800">Captured payment needs review</p>}</td><td className="p-3">₹{booking.amount_paid} / ₹{booking.balance_due}</td></tr>)}</tbody></table>{bookings.length === 0 && <p className="py-5">No bookings yet.</p>}</div>
    </section>
  </div>
}
