import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

type DemoBooking = { id: string; service: string; slot: string; status: 'Confirmed' | 'Cancelled' }
type DemoSession = { expiresAt: number; bookings: DemoBooking[] }

const STORAGE_KEY = 'typein_public_demo_v1'
const SESSION_MS = 60 * 60 * 1000
const SERVICES = [
  { name: 'Haircut', duration: '45 minutes', price: '₹500' },
  { name: 'Skin consultation', duration: '30 minutes', price: '₹750' },
  { name: 'Yoga class', duration: '60 minutes', price: '₹300' },
] as const
const SLOTS = ['10:00 AM', '11:30 AM', '2:00 PM', '4:00 PM'] as const

function freshSession(): DemoSession {
  return { expiresAt: Date.now() + SESSION_MS, bookings: [] }
}

function loadSession(): DemoSession {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (raw) {
      const value: unknown = JSON.parse(raw)
      if (typeof value === 'object' && value !== null && 'expiresAt' in value && 'bookings' in value &&
          typeof value.expiresAt === 'number' && value.expiresAt > Date.now() && Array.isArray(value.bookings)) {
        return value as DemoSession
      }
    }
  } catch {
    // An unavailable or old browser session starts a clean demo.
  }
  return freshSession()
}

export function DemoPage() {
  const [session, setSession] = useState<DemoSession>(loadSession)
  const [now, setNow] = useState(() => Date.now())
  const [service, setService] = useState<string>(SERVICES[0].name)
  const [slot, setSlot] = useState<string>(SLOTS[0])
  const [rescheduling, setRescheduling] = useState<string | null>(null)

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSession(freshSession())
      setRescheduling(null)
    }, Math.max(0, session.expiresAt - Date.now()))
    return () => window.clearTimeout(timer)
  }, [session.expiresAt])

  useEffect(() => {
    try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session)) } catch { /* Memory-only demo */ }
  }, [session])

  const minutesLeft = Math.max(0, Math.ceil((session.expiresAt - now) / 60_000))
  const confirmed = session.bookings.filter((booking) => booking.status === 'Confirmed')
  const day = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
    .format(new Date(now + 2 * 24 * 60 * 60 * 1000))

  function makeBooking() {
    setSession((current) => ({
      ...current,
      bookings: [{ id: crypto.randomUUID(), service, slot: `${day}, ${slot}`, status: 'Confirmed' }, ...current.bookings],
    }))
  }

  function cancelBooking(id: string) {
    setSession((current) => ({
      ...current,
      bookings: current.bookings.map((booking) => booking.id === id ? { ...booking, status: 'Cancelled' } : booking),
    }))
  }

  function moveBooking(id: string) {
    setSession((current) => ({
      ...current,
      bookings: current.bookings.map((booking) => booking.id === id ? { ...booking, slot: `${day}, ${slot}` } : booking),
    }))
    setRescheduling(null)
  }

  return <main className="min-h-svh bg-[#f4f7f5] text-[#123c2d]">
    <header className="bg-[#123c2d] px-5 py-5 text-white"><div className="mx-auto flex max-w-5xl items-center justify-between gap-4"><strong className="text-xl">typein demo</strong><Link to="/login" className="rounded-lg border border-white/40 px-4 py-2 text-sm font-semibold">Sign in</Link></div></header>
    <div className="mx-auto max-w-5xl space-y-6 px-5 py-8">
      <div className="rounded-2xl border border-[#c7d5cd] bg-white p-5"><h1 className="text-3xl font-bold">Explore a sample business</h1><p className="mt-2 text-[#456254]">This demo uses only sample data in this browser session. It resets after 60 minutes. No payments, messages, exports, or real customer data are involved.</p><p className="mt-2 text-sm font-semibold" role="status">{minutesLeft} minutes remaining</p></div>
      <section className="grid gap-4 sm:grid-cols-3" aria-label="Sample owner dashboard"><div className="rounded-2xl bg-white p-5"><p className="text-sm text-[#456254]">Sample services</p><strong className="text-3xl">{SERVICES.length}</strong></div><div className="rounded-2xl bg-white p-5"><p className="text-sm text-[#456254]">Your demo bookings</p><strong className="text-3xl">{confirmed.length}</strong></div><div className="rounded-2xl bg-white p-5"><p className="text-sm text-[#456254]">Available sample slots</p><strong className="text-3xl">{SLOTS.length}</strong></div></section>
      <section className="rounded-2xl bg-white p-5"><h2 className="text-2xl font-bold">Services and availability</h2><ul className="mt-4 grid gap-3 sm:grid-cols-3">{SERVICES.map((item) => <li key={item.name} className="rounded-xl border border-[#dce4df] p-4"><strong>{item.name}</strong><p className="mt-1 text-sm text-[#456254]">{item.duration} · {item.price}</p></li>)}</ul><p className="mt-4 text-sm text-[#456254]">Sample availability for {day}: {SLOTS.join(', ')}</p></section>
      <section className="rounded-2xl bg-white p-5"><h2 className="text-2xl font-bold">Simulate a booking</h2><div className="mt-4 flex flex-wrap items-end gap-3"><label className="grid gap-1 text-sm font-semibold">Service<select className="rounded-lg border p-2" value={service} onChange={(event) => setService(event.target.value)}>{SERVICES.map((item) => <option key={item.name}>{item.name}</option>)}</select></label><label className="grid gap-1 text-sm font-semibold">Time<select className="rounded-lg border p-2" value={slot} onChange={(event) => setSlot(event.target.value)}>{SLOTS.map((value) => <option key={value}>{value}</option>)}</select></label><button type="button" onClick={makeBooking} className="rounded-lg bg-[#166b4a] px-4 py-2 font-semibold text-white">Create sample booking</button></div></section>
      <section className="rounded-2xl bg-white p-5"><h2 className="text-2xl font-bold">Sample bookings</h2>{session.bookings.length === 0 ? <p className="mt-3 text-[#456254]">No demo bookings yet.</p> : <ul className="mt-3 divide-y">{session.bookings.map((booking) => <li key={booking.id} className="flex flex-wrap items-center justify-between gap-3 py-4"><div><strong>{booking.service}</strong><p className="text-sm text-[#456254]">{booking.slot} · {booking.status}</p></div>{booking.status === 'Confirmed' && <div className="flex gap-2">{rescheduling === booking.id ? <button type="button" onClick={() => moveBooking(booking.id)} className="rounded-lg border px-3 py-2 text-sm">Confirm new time above</button> : <button type="button" onClick={() => setRescheduling(booking.id)} className="rounded-lg border px-3 py-2 text-sm">Reschedule</button>}<button type="button" onClick={() => cancelBooking(booking.id)} className="rounded-lg border px-3 py-2 text-sm">Cancel</button></div>}</li>)}</ul>}</section>
      <button type="button" onClick={() => { setSession(freshSession()); setRescheduling(null) }} className="text-sm font-semibold underline">Reset demo now</button>
    </div>
  </main>
}
