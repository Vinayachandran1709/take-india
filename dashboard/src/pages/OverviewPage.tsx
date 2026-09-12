import { CalendarCheck2, ExternalLink, Store, Users } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '../lib/api'
import type { Merchant, Service, Staff } from '../lib/types'

export function OverviewPage() {
  const [merchant, setMerchant] = useState<Merchant | null>(null)
  const [services, setServices] = useState<Service[]>([])
  const [staff, setStaff] = useState<Staff[]>([])
  useEffect(() => { void Promise.all([api.get<Merchant>('/auth/me'), api.get<Service[]>('/services'), api.get<Staff[]>('/staff')]).then(([me, serviceList, staffList]) => { setMerchant(me.data); setServices(serviceList.data); setStaff(staffList.data) }) }, [])
  const storefrontBase = import.meta.env.VITE_STOREFRONT_URL ?? 'http://localhost:3000'
  return <div className="mx-auto max-w-6xl"><p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#176848]">Overview</p><div className="mt-2 flex flex-wrap items-end justify-between gap-4"><div><h1 className="text-3xl font-bold tracking-tight">{merchant ? `Hello, ${merchant.owner_name}` : 'Loading workspace…'}</h1><p className="mt-2 text-[#68756e]">Your booking configuration at a glance.</p></div>{merchant && <a href={`${storefrontBase}/${merchant.slug}`} target="_blank" rel="noreferrer" className="flex items-center gap-2 rounded-xl border border-[#ccd8d1] bg-white px-4 py-2.5 text-sm font-semibold">View storefront <ExternalLink size={16} /></a>}</div><div className="mt-8 grid gap-4 sm:grid-cols-3">{[{ label: 'Services', value: services.filter((item) => item.is_active).length, icon: Store }, { label: 'Active staff', value: staff.filter((item) => item.is_active).length, icon: Users }, { label: 'Booking modes', value: new Set(services.map((item) => item.booking_mode)).size, icon: CalendarCheck2 }].map(({ label, value, icon: Icon }) => <div key={label} className="rounded-3xl border border-[#dce4df] bg-white p-6 shadow-sm"><Icon className="text-[#176848]" size={22} /><p className="mt-6 text-3xl font-bold">{value}</p><p className="mt-1 text-sm text-[#68756e]">{label}</p></div>)}</div><section className="mt-8 rounded-3xl bg-[#123c2d] p-7 text-white"><h2 className="text-xl font-bold">Razorpay Test payments</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-[#c8ded3]">Connect your merchant Test account in Test payments to confirm bookings after captured payments. Live payments are unavailable.</p></section></div>
}
