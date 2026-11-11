import { CreditCard, LoaderCircle } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { api, errorMessage } from '../lib/api'
import type { BillingDetail, Merchant } from '../lib/types'

type CheckoutResult = {
  razorpay_payment_id: string
  razorpay_subscription_id: string
  razorpay_signature: string
}
type CheckoutOptions = {
  key: string
  subscription_id: string
  name: string
  description: string
  prefill: { name: string; email: string; contact: string }
  theme: { color: string }
  handler: (result: CheckoutResult) => void
}
type CheckoutInstance = { open: () => void }
type CheckoutWindow = Window & {
  Razorpay?: new (options: CheckoutOptions) => CheckoutInstance
}

function loadCheckout(): Promise<void> {
  if ((window as CheckoutWindow).Razorpay) return Promise.resolve()
  return new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>('script[data-typein-checkout]')
    if (existing) {
      existing.addEventListener('load', () => resolve(), { once: true })
      existing.addEventListener('error', () => reject(new Error('Checkout unavailable')), { once: true })
      return
    }
    const script = document.createElement('script')
    script.src = 'https://checkout.razorpay.com/v1/checkout.js'
    script.async = true
    script.dataset.typeinCheckout = 'true'
    script.onload = () => resolve()
    script.onerror = () => { script.remove(); reject(new Error('Checkout unavailable')) }
    document.head.appendChild(script)
  })
}

function displayDate(value: string | null): string {
  return value ? new Date(value).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'
}

export function BillingPage() {
  const [billing, setBilling] = useState<BillingDetail | null>(null)
  const [merchant, setMerchant] = useState<Merchant | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [confirmCancel, setConfirmCancel] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const [billingResponse, merchantResponse] = await Promise.all([
        api.get<BillingDetail>('/billing'),
        api.get<Merchant>('/merchant/me'),
      ])
      setBilling(billingResponse.data)
      setMerchant(merchantResponse.data)
      window.dispatchEvent(new Event('typein:billing-updated'))
      setError('')
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => { void refresh() }, 0)
    return () => window.clearTimeout(timer)
  }, [refresh])
  useEffect(() => {
    if (!billing?.summary.processing) return
    const timer = window.setInterval(() => { void refresh() }, 5000)
    return () => window.clearInterval(timer)
  }, [billing?.summary.processing, refresh])

  async function subscribe() {
    if (!merchant || busy) return
    setBusy(true)
    setError('')
    try {
      const { data } = await api.post<{ subscription_id: string; key_id: string }>('/billing/subscribe')
      await loadCheckout()
      const Checkout = (window as CheckoutWindow).Razorpay
      if (!Checkout) throw new Error('Checkout unavailable')
      new Checkout({
        key: data.key_id,
        subscription_id: data.subscription_id,
        name: 'typein',
        description: 'Rs 1,499 per month',
        prefill: {
          name: merchant.business_name,
          email: merchant.email,
          contact: merchant.phone_number,
        },
        theme: { color: '#166b4a' },
        handler: (result) => {
          setBusy(true)
          api.post('/billing/confirm', result).then(() => {
            void refresh()
          }).catch((requestError) => {
            setError(errorMessage(requestError))
          }).finally(() => setBusy(false))
        },
      }).open()
    } catch (requestError) {
      setError(errorMessage(requestError) === 'Something went wrong.'
        ? 'Checkout could not open. Please try again.' : errorMessage(requestError))
    } finally {
      setBusy(false)
    }
  }

  async function cancel() {
    if (!confirmCancel || busy) return
    setBusy(true)
    setError('')
    try {
      await api.post('/billing/cancel')
      setConfirmCancel(false)
      await refresh()
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setBusy(false)
    }
  }

  const summary = billing?.summary
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <p className="flex items-center gap-2 text-sm font-bold uppercase tracking-widest text-[#166b4a]"><CreditCard size={17} /> Billing</p>
        <h1 className="mt-2 text-3xl font-bold text-[#123c2d]">Your subscription</h1>
      </header>
      {loading && <p role="status" className="text-[#456254]">Loading billing details…</p>}
      {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-800">{error}</p>}
      {summary && <section className="rounded-3xl border border-[#dce4df] bg-white p-6 shadow-sm sm:p-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><h2 className="text-xl font-bold text-[#123c2d]">typein monthly</h2><p className="mt-1 text-[#456254]">Rs 1,499 per month</p></div>
          <span className="rounded-full bg-[#eaf5ee] px-4 py-2 text-sm font-bold capitalize text-[#166b4a]">{summary.effective_status.replace('_', ' ')}</span>
        </div>
        <dl className="mt-6 grid gap-4 border-t border-[#dce4df] pt-5 text-sm sm:grid-cols-2">
          {summary.effective_status === 'trialing' && <div><dt className="text-[#456254]">Trial remaining</dt><dd className="mt-1 font-semibold">{summary.days_left} {summary.days_left === 1 ? 'day' : 'days'}</dd></div>}
          <div><dt className="text-[#456254]">Trial ends</dt><dd className="mt-1 font-semibold">{displayDate(summary.trial_ends_at)}</dd></div>
          {summary.current_period_end && <div><dt className="text-[#456254]">Current period ends</dt><dd className="mt-1 font-semibold">{displayDate(summary.current_period_end)}</dd></div>}
          {summary.grace_ends_at && <div><dt className="text-[#456254]">Payment grace ends</dt><dd className="mt-1 font-semibold">{displayDate(summary.grace_ends_at)}</dd></div>}
        </dl>
        {summary.processing && <p role="status" className="mt-5 rounded-xl bg-[#fff8e9] p-4 text-sm text-[#614819]"><LoaderCircle className="mr-2 inline animate-spin" size={16} />Payment authorization is processing. Access updates after Razorpay confirms it.</p>}
        {summary.authorization_confirmed && summary.effective_status === 'trialing' && <p role="status" className="mt-5 rounded-xl bg-[#eaf5ee] p-4 text-sm text-[#166b4a]">Subscription authorization received. Your free trial continues; paid access begins when Razorpay starts the billing cycle.</p>}
        {summary.cancel_at_period_end && <p role="status" className="mt-5 rounded-xl bg-[#fff8e9] p-4 text-sm text-[#614819]">Cancellation is scheduled for the end of your current billing cycle.</p>}
        {summary.effective_status === 'past_due' && <p role="status" className="mt-5 rounded-xl bg-[#fff8e9] p-4 text-sm text-[#614819]">{summary.grace_ends_at && !summary.locked ? `Your payment needs attention. You can keep using typein until ${displayDate(summary.grace_ends_at)}.` : 'Your account is locked until billing is resolved. Your billing page remains available.'}</p>}
        {summary.effective_status === 'cancelled' && !summary.locked && <p role="status" className="mt-5 rounded-xl bg-[#eaf5ee] p-4 text-sm text-[#166b4a]">Your subscription is cancelled. Your existing trial or paid access continues until its scheduled end.</p>}
        <div className="mt-6 flex flex-wrap gap-3">
          {!summary.cancel_at_period_end && !summary.processing && ((!summary.authorization_confirmed && summary.effective_status === 'trialing') || (summary.effective_status === 'cancelled' && !summary.current_period_end) || summary.locked) && <button type="button" onClick={() => void subscribe()} disabled={busy || !merchant} className="rounded-xl bg-[#166b4a] px-5 py-3 font-bold text-white disabled:opacity-50">{busy ? 'Please wait…' : 'Subscribe'}</button>}
          {summary.has_subscription && (summary.effective_status === 'trialing' || summary.effective_status === 'active') && !summary.cancel_at_period_end && !confirmCancel && <button type="button" onClick={() => setConfirmCancel(true)} className="rounded-xl border border-[#c7d5cd] px-5 py-3 font-semibold text-[#123c2d]">Cancel subscription</button>}
          {confirmCancel && <div className="w-full rounded-xl border border-[#e6cf9b] bg-[#fff8e9] p-4"><p className="text-sm text-[#614819]">{summary.effective_status === 'trialing' ? 'Cancel now? Your free trial will continue until its original end date.' : 'Cancel at the end of this billing cycle? You can keep using typein until then.'}</p><div className="mt-3 flex gap-3"><button type="button" onClick={() => void cancel()} disabled={busy} className="rounded-lg bg-[#123c2d] px-4 py-2 font-semibold text-white disabled:opacity-50">Confirm cancellation</button><button type="button" onClick={() => setConfirmCancel(false)} className="rounded-lg px-4 py-2 font-semibold text-[#123c2d]">Keep subscription</button></div></div>}
        </div>
      </section>}
      {billing && <section className="rounded-3xl border border-[#dce4df] bg-white p-6 shadow-sm sm:p-8"><h2 className="text-xl font-bold text-[#123c2d]">Payment history</h2>{billing.payments.length === 0 ? <p className="mt-4 text-[#456254]">No subscription payments recorded yet.</p> : <ul className="mt-4 divide-y divide-[#dce4df]">{billing.payments.map((payment) => <li key={payment.razorpay_payment_id} className="flex flex-wrap items-center justify-between gap-2 py-4 text-sm"><span><span className="block font-semibold">Rs {(payment.amount_paise / 100).toLocaleString('en-IN')}</span><span className="text-[#456254]">{displayDate(payment.paid_at)}</span></span><span className="capitalize text-[#456254]">{payment.status}</span></li>)}</ul>}</section>}
    </div>
  )
}
