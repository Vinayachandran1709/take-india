import { Plus, Trash2 } from 'lucide-react'
import { type FormEvent, useEffect, useState } from 'react'

import { api, errorMessage } from '../lib/api'
import type { BatchSchedule, Service } from '../lib/types'

const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

export function SchedulesPage() {
  const [services, setServices] = useState<Service[]>([])
  const [serviceId, setServiceId] = useState('')
  const [schedules, setSchedules] = useState<BatchSchedule[]>([])
  const [error, setError] = useState('')
  useEffect(() => { void api.get<Service[]>('/services').then(({ data }) => { const batch = data.filter((item) => item.booking_mode === 'BATCH' && item.is_active); setServices(batch); if (batch[0]) setServiceId(batch[0].id) }) }, [])
  useEffect(() => { if (serviceId) void api.get<BatchSchedule[]>(`/services/${serviceId}/batch-schedules`).then(({ data }) => setSchedules(data)) }, [serviceId])
  async function reload() { setSchedules((await api.get<BatchSchedule[]>(`/services/${serviceId}/batch-schedules`)).data) }
  async function add(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); try { await api.post(`/services/${serviceId}/batch-schedules`, { day_of_week: Number(form.get('day')), start_time: form.get('start'), end_time: form.get('end'), max_capacity: Number(form.get('capacity')) }); event.currentTarget.reset(); await reload() } catch (requestError) { setError(errorMessage(requestError)) } }
  return <div className="mx-auto max-w-5xl"><h1 className="text-3xl font-bold tracking-tight">Batch schedules</h1><p className="mt-2 text-[#68756e]">Define recurring weekly sessions. Times are merchant-local.</p><section className="panel mt-8">{services.length === 0 ? <p className="text-[#68756e]">Create a batch-mode service first.</p> : <><label>Batch service<select value={serviceId} onChange={(event) => setServiceId(event.target.value)}>{services.map((service) => <option key={service.id} value={service.id}>{service.title}</option>)}</select></label><form onSubmit={add} className="mt-6 grid gap-3 sm:grid-cols-4"><label>Day<select name="day">{days.map((day, index) => <option key={day} value={index}>{day}</option>)}</select></label><label>Starts<input required name="start" type="time" /></label><label>Ends<input required name="end" type="time" /></label><label>Capacity<input required name="capacity" type="number" min="1" /></label>{error && <p className="sm:col-span-4 text-sm text-red-700">{error}</p>}<button className="primary sm:col-span-4"><Plus size={17} /> Add schedule</button></form><div className="mt-6 space-y-2">{schedules.map((schedule) => <div key={schedule.id} className="flex items-center justify-between rounded-xl bg-[#f5f7f5] p-4"><div><p className={schedule.is_active ? 'font-semibold' : 'line-through'}>{days[schedule.day_of_week]} · {schedule.start_time.slice(0, 5)}–{schedule.end_time.slice(0, 5)}</p><p className="text-xs text-[#68756e]">Capacity {schedule.max_capacity}</p></div>{schedule.is_active && <button className="icon-button" onClick={async () => { await api.delete(`/services/${serviceId}/batch-schedules/${schedule.id}`); await reload() }}><Trash2 size={16} /></button>}</div>)}</div></>}</section></div>
}
