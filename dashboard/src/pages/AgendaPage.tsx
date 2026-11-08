import { CalendarDays, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api, errorMessage } from '../lib/api'
import type { AgendaBooking, AgendaResponse } from '../lib/types'

function dayLabel(value: string): string {
  return new Date(`${value}T12:00:00`).toLocaleDateString('en-IN', {
    weekday: 'long', day: 'numeric', month: 'long',
  })
}

export function AgendaPage() {
  const [agenda, setAgenda] = useState<AgendaResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function refresh() {
    setLoading(true)
    setError('')
    try {
      const { data } = await api.get<AgendaResponse>('/merchants/me/agenda')
      setAgenda(data)
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    api.get<AgendaResponse>('/merchants/me/agenda')
      .then(({ data }) => setAgenda(data))
      .catch((requestError) => setError(errorMessage(requestError)))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="mx-auto max-w-5xl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#176848]">Bookings</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight">Daily agenda</h1>
          <p className="mt-2 text-[#68756e]">Confirmed bookings for today and tomorrow.</p>
        </div>
        <button type="button" onClick={() => void refresh()} disabled={loading} className="secondary">
          <RefreshCw size={17} /> Refresh
        </button>
      </div>

      {loading && !agenda && <p className="mt-8" role="status">Loading bookings…</p>}
      {error && <p role="alert" className="mt-8 rounded-xl bg-red-50 p-4 text-red-700">{error}</p>}

      {agenda && [agenda.today, agenda.tomorrow].map((day) => {
        const bookings: AgendaBooking[] = agenda.bookings.filter((item) => item.booking_date === day)
        return (
          <section key={day} className="panel mt-8">
            <h2 className="flex items-center gap-2 text-xl font-bold">
              <CalendarDays size={20} />{dayLabel(day)}{day === agenda.today ? ' · Today' : ' · Tomorrow'}
            </h2>
            {bookings.length === 0 ? (
              <p className="mt-5 text-[#68756e]">No confirmed bookings.</p>
            ) : (
              <ol className="mt-5 divide-y divide-[#dce4df]">
                {bookings.map((booking) => (
                  <li key={booking.booking_reference} className="grid gap-2 py-4 sm:grid-cols-[8rem_1fr]">
                    <time className="font-bold text-[#176848]">{booking.start_time.slice(0, 5)}–{booking.end_time.slice(0, 5)}</time>
                    <div>
                      <p className="font-semibold">{booking.service_title}</p>
                      <p className="mt-1 text-sm">{booking.customer_name} · {booking.customer_phone}</p>
                      <p className="mt-1 text-xs text-[#68756e]">{booking.booking_reference}</p>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </section>
        )
      })}
    </div>
  )
}
