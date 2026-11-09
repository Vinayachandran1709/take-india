import { CalendarRange, CreditCard, LayoutDashboard, LogOut, Settings, Sparkles, Store } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'

import { api } from '../lib/api'
import { clearAccessToken } from '../lib/auth'
import type { BillingSummary, Merchant } from '../lib/types'

const links = [
  { to: '/dashboard', label: 'Agenda', icon: LayoutDashboard, end: true },
  { to: '/dashboard/services', label: 'Services', icon: Store },
  { to: '/dashboard/schedules', label: 'Schedules', icon: CalendarRange },
  { to: '/dashboard/settings', label: 'Settings', icon: Settings },
  { to: '/dashboard/billing', label: 'Billing', icon: CreditCard },
]

export function Shell({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const location = useLocation()
  const [billing, setBilling] = useState<BillingSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [unavailable, setUnavailable] = useState(false)

  useEffect(() => {
    let active = true
    const refresh = () => {
      api.get<Merchant>('/merchant/me').then(({ data }) => {
        if (active) { setBilling(data.billing); setUnavailable(false); setLoading(false) }
      }).catch(() => {
        if (active) { setUnavailable(true); setLoading(false) }
      })
    }
    const locked = () => { setBilling((current) => current ? { ...current, locked: true } : current); refresh() }
    refresh()
    window.addEventListener('typein:subscription-required', locked)
    window.addEventListener('typein:billing-updated', refresh)
    return () => {
      active = false
      window.removeEventListener('typein:subscription-required', locked)
      window.removeEventListener('typein:billing-updated', refresh)
    }
  }, [])

  const signOut = () => { clearAccessToken(); navigate('/login') }
  const isBilling = location.pathname.startsWith('/dashboard/billing')
  return (
    <div className="min-h-svh bg-[#f4f7f5] lg:grid lg:grid-cols-[250px_1fr]">
      <aside className="border-b border-[#dce4df] bg-[#123c2d] p-4 text-white lg:min-h-svh lg:border-b-0 lg:p-6">
        <div className="flex items-center justify-between lg:block">
          <div className="flex items-center gap-3 font-bold"><span className="grid size-10 place-items-center rounded-xl bg-[#f2a92f] text-[#123c2d]"><Sparkles size={19} /></span>typein</div>
          <button onClick={signOut} className="rounded-xl p-2 text-[#b9d4c7] hover:bg-white/10 lg:hidden" aria-label="Sign out"><LogOut size={19} /></button>
        </div>
        <nav className="mt-4 flex gap-2 overflow-x-auto lg:mt-10 lg:block lg:space-y-2" aria-label="Dashboard">
          {links.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} className={({ isActive }) => `flex shrink-0 items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition ${isActive ? 'bg-white text-[#123c2d]' : 'text-[#c8ded3] hover:bg-white/10'}`}><Icon size={18} />{label}</NavLink>)}
        </nav>
        <button onClick={signOut} className="mt-10 hidden w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-[#c8ded3] hover:bg-white/10 lg:flex"><LogOut size={18} /> Sign out</button>
      </aside>
      <main className="min-w-0 p-5 sm:p-8 lg:p-10">
        {loading && <p role="status" className="text-[#456254]">Checking your account…</p>}
        {!loading && unavailable && !isBilling && <section role="alert" className="rounded-2xl bg-white p-6"><h1 className="text-xl font-bold">Account status unavailable</h1><p className="mt-2">Please try again shortly.</p><NavLink to="/dashboard/billing" className="mt-4 inline-block font-semibold text-[#166b4a] underline">View billing</NavLink></section>}
        {!loading && !unavailable && billing?.effective_status === 'trialing' && billing.days_left <= 10 && <div role="status" className="mb-6 rounded-2xl border border-[#e6cf9b] bg-[#fff8e9] p-4 text-sm text-[#614819]">Your free trial has {billing.days_left} {billing.days_left === 1 ? 'day' : 'days'} left. <NavLink className="font-bold underline" to="/dashboard/billing">View billing</NavLink></div>}
        {!loading && !unavailable && billing?.locked && !isBilling && <section className="max-w-xl rounded-3xl border border-[#dce4df] bg-white p-8 shadow-sm"><h1 className="text-2xl font-bold text-[#123c2d]">Your account needs a subscription</h1><p className="mt-3 text-[#456254]">Booking setup is paused because your trial or subscription is no longer active. Your existing customer management links remain available.</p><NavLink to="/dashboard/billing" className="mt-6 inline-block rounded-xl bg-[#166b4a] px-5 py-3 font-bold text-white">Subscribe</NavLink></section>}
        {!loading && (isBilling || (!unavailable && !billing?.locked)) && children}
      </main>
    </div>
  )
}
