import { ArrowRight, LockKeyhole, Sparkles } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { api, errorMessage } from '../lib/api'
import { isAuthenticated, setAccessToken } from '../lib/auth'

export function AuthPage({ mode }: { mode: 'login' | 'signup' }) {
  const navigate = useNavigate()
  const location = useLocation()
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  if (isAuthenticated()) return <Navigate to="/dashboard" replace />

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    const form = new FormData(event.currentTarget)
    try {
      const payload = mode === 'login'
        ? { email: form.get('email'), password: form.get('password') }
        : {
            business_name: form.get('business_name'), slug: form.get('slug'),
            business_type: form.get('business_type'), owner_name: form.get('owner_name'),
            phone_number: form.get('phone_number'), email: form.get('email'),
            password: form.get('password'),
          }
      const { data } = await api.post<{ access_token: string }>(`/auth/${mode}`, payload)
      setAccessToken(data.access_token)
      const destination = (location.state as { from?: string } | null)?.from ?? '/dashboard'
      navigate(destination, { replace: true })
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="grid min-h-svh bg-[#f4f7f5] lg:grid-cols-[1.05fr_0.95fr]">
      <section className="hidden bg-[#123c2d] p-14 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="flex items-center gap-3 text-lg font-bold"><span className="grid size-11 place-items-center rounded-2xl bg-[#f2a92f] text-[#123c2d]"><Sparkles size={21} /></span>Take-India</div>
        <div className="max-w-xl"><p className="mb-5 text-sm font-semibold uppercase tracking-[0.2em] text-[#9bd0b8]">Merchant workspace</p><h1 className="text-5xl font-bold leading-[1.08] tracking-[-0.04em]">Run every booking mode from one calm workspace.</h1><p className="mt-6 text-lg leading-8 text-[#c8ded3]">Configure services, staff, opening hours, classes and custom-order intake.</p></div>
        <p className="text-sm text-[#9bd0b8]">Phase 1 · Booking engine configuration</p>
      </section>
      <section className="flex items-center justify-center px-5 py-10 sm:px-10"><div className="w-full max-w-md rounded-3xl border border-[#dce4df] bg-white p-7 shadow-[0_24px_80px_rgba(18,60,45,0.09)] sm:p-9">
        <span className="mb-5 grid size-12 place-items-center rounded-2xl bg-[#edf6f1] text-[#176848]"><LockKeyhole size={21} /></span>
        <h2 className="text-3xl font-bold tracking-[-0.035em]">{mode === 'login' ? 'Welcome back' : 'Create your storefront'}</h2>
        <p className="mt-2 text-sm leading-6 text-[#66736c]">{mode === 'login' ? 'Sign in to manage your bookings.' : 'Start configuring your Phase 1 booking page.'}</p>
        <form onSubmit={submit} className="mt-7 grid gap-4">
          {mode === 'signup' && <><label>Business name<input required name="business_name" /></label><label>Storefront slug<input required name="slug" pattern="[a-z0-9]+(?:-[a-z0-9]+)*" placeholder="my-business" /></label><div className="grid grid-cols-2 gap-3"><label>Owner name<input required name="owner_name" /></label><label>Phone<input required name="phone_number" placeholder="9876543210" /></label></div><label>Business type<select name="business_type"><option>SALON</option><option>CLINIC</option><option>BAKERY</option><option>FITNESS</option><option>ACADEMY</option></select></label></>}
          <label>Email address<input required name="email" type="email" placeholder="owner@example.com" /></label>
          <label>Password<input required name="password" type="password" minLength={8} /></label>
          {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}
          <button disabled={submitting} className="mt-2 flex h-12 items-center justify-center gap-2 rounded-xl bg-[#176848] font-semibold text-white disabled:opacity-50">{submitting ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'} <ArrowRight size={18} /></button>
        </form>
        <p className="mt-6 text-center text-sm text-[#66736c]">{mode === 'login' ? 'New to Take-India?' : 'Already registered?'} <Link className="font-semibold text-[#176848]" to={mode === 'login' ? '/signup' : '/login'}>{mode === 'login' ? 'Create an account' : 'Sign in'}</Link></p>
      </div></section>
    </main>
  )
}
