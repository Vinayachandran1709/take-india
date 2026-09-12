import { CalendarRange, LayoutDashboard, LogOut, Settings, Sparkles, Store } from 'lucide-react'
import type { ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'

import { clearAccessToken } from '../lib/auth'

const links = [
  { to: '/dashboard', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/dashboard/services', label: 'Services', icon: Store },
  { to: '/dashboard/schedules', label: 'Schedules', icon: CalendarRange },
  { to: '/dashboard/settings', label: 'Settings', icon: Settings },
  { to: '/dashboard/payments', label: 'Test payments', icon: Store },
]

export function Shell({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  return (
    <div className="min-h-svh bg-[#f4f7f5] lg:grid lg:grid-cols-[250px_1fr]">
      <aside className="border-b border-[#dce4df] bg-[#123c2d] p-4 text-white lg:min-h-svh lg:border-b-0 lg:p-6">
        <div className="flex items-center justify-between lg:block">
          <div className="flex items-center gap-3 font-bold"><span className="grid size-10 place-items-center rounded-xl bg-[#f2a92f] text-[#123c2d]"><Sparkles size={19} /></span>Take-India</div>
          <button onClick={() => { clearAccessToken(); navigate('/login') }} className="rounded-xl p-2 text-[#b9d4c7] hover:bg-white/10 lg:hidden" aria-label="Sign out"><LogOut size={19} /></button>
        </div>
        <nav className="mt-4 flex gap-2 overflow-x-auto lg:mt-10 lg:block lg:space-y-2">
          {links.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} className={({ isActive }) => `flex shrink-0 items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition ${isActive ? 'bg-white text-[#123c2d]' : 'text-[#c8ded3] hover:bg-white/10'}`}><Icon size={18} />{label}</NavLink>)}
        </nav>
        <button onClick={() => { clearAccessToken(); navigate('/login') }} className="mt-10 hidden w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-[#c8ded3] hover:bg-white/10 lg:flex"><LogOut size={18} /> Sign out</button>
      </aside>
      <main className="min-w-0 p-5 sm:p-8 lg:p-10">{children}</main>
    </div>
  )
}
