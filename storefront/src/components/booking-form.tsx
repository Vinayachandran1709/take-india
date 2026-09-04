"use client";

import axios from "axios";
import { CalendarDays, CheckCircle2, Clock3, LoaderCircle, Users } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { apiBaseUrl, rupees } from "@/lib/api";
import type {
  Availability,
  AvailabilitySlot,
  BookingResult,
  Service,
} from "@/lib/types";

type ApiError = { error?: { code?: string; message?: string } };

function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function shortTime(value: string): string {
  return value.slice(0, 5);
}

export function BookingForm({ slug, service }: { slug: string; service: Service }) {
  const [bookingDate, setBookingDate] = useState(today());
  const [availability, setAvailability] = useState<Availability | null>(null);
  const [availabilityState, setAvailabilityState] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [selectedSlot, setSelectedSlot] = useState<AvailabilitySlot | null>(null);
  const [staffId, setStaffId] = useState("");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [responses, setResponses] = useState<Record<string, string | boolean>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<BookingResult | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    axios
      .get<Availability>(`${apiBaseUrl}/storefront/${encodeURIComponent(slug)}/available-slots`, {
        params: { service_id: service.id, date: bookingDate },
        signal: controller.signal,
      })
      .then(({ data }) => {
        setAvailability(data);
        setAvailabilityState("ready");
      })
      .catch((requestError) => {
        if (!axios.isCancel(requestError)) setAvailabilityState("error");
      });
    return () => controller.abort();
  }, [bookingDate, service.id, slug]);

  const slots = availability?.available_slots ?? [];
  const payable = Number(service.advance_token_amount) > 0
    ? service.advance_token_amount
    : service.price;
  const canSubmit = useMemo(() => {
    if (!name.trim() || !phone.trim()) return false;
    if (service.booking_mode === "CUSTOM_ORDER") return Boolean(customStart && customEnd);
    return Boolean(selectedSlot);
  }, [customEnd, customStart, name, phone, selectedSlot, service.booking_mode]);

  function changeDate(value: string) {
    setBookingDate(value);
    setAvailabilityState("loading");
    setSelectedSlot(null);
    setStaffId("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const intent: Record<string, unknown> = {
        service_id: service.id,
        customer_name: name,
        customer_phone: phone,
        booking_date: bookingDate,
        custom_field_responses: responses,
      };
      if (service.booking_mode === "APPOINTMENT") {
        intent.start_time = selectedSlot?.start_time;
        if (staffId) intent.staff_member_id = staffId;
      } else if (service.booking_mode === "BATCH") {
        intent.batch_schedule_id = selectedSlot?.batch_schedule_id;
      } else {
        intent.start_time = customStart;
        intent.end_time = customEnd;
      }
      const { data } = await axios.post<BookingResult>(`${apiBaseUrl}/bookings/initiate`, intent);
      setResult(data);
    } catch (requestError) {
      if (axios.isAxiosError<ApiError>(requestError)) {
        const code = requestError.response?.data?.error?.code;
        setError(
          code === "SLOT_UNAVAILABLE" || code === "BATCH_FULL"
            ? "That option was just taken. Refresh availability and choose another."
            : requestError.response?.data?.error?.message ?? "We could not hold this booking.",
        );
      } else {
        setError("We could not hold this booking.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (result) {
    return (
      <section className="rounded-3xl border border-[#b8dbc8] bg-[#f3fbf6] p-6 shadow-sm sm:p-8">
        <CheckCircle2 className="text-[var(--brand)]" size={38} aria-hidden="true" />
        <p className="mt-5 text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">
          Booking held
        </p>
        <h2 className="mt-2 text-3xl font-bold tracking-tight">{result.booking_reference}</h2>
        <dl className="mt-6 grid grid-cols-2 gap-4 text-sm">
          <div><dt className="text-[var(--muted)]">Date</dt><dd className="mt-1 font-semibold">{result.booking_date}</dd></div>
          <div><dt className="text-[var(--muted)]">Time</dt><dd className="mt-1 font-semibold">{shortTime(result.start_time)}–{shortTime(result.end_time)}</dd></div>
          <div><dt className="text-[var(--muted)]">Amount due</dt><dd className="mt-1 font-semibold">{rupees(result.amount_to_pay)}</dd></div>
          <div><dt className="text-[var(--muted)]">Hold expires</dt><dd className="mt-1 font-semibold">{new Date(result.hold_expires_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</dd></div>
        </dl>
        <p className="mt-6 rounded-2xl bg-white p-4 text-sm leading-6 text-[var(--muted)]">
          Payment will be connected in Phase 2. This is an unpaid temporary hold.
        </p>
      </section>
    );
  }

  return (
    <form onSubmit={submit} className="min-w-0 space-y-7">
      <section className="min-w-0 overflow-hidden rounded-3xl border border-[var(--border)] bg-white p-5 shadow-sm sm:p-7">
        <h2 className="flex items-center gap-2 text-lg font-bold"><CalendarDays size={19} /> Choose a date</h2>
        <input type="date" min={today()} value={bookingDate} onChange={(event) => changeDate(event.target.value)} className="mt-4 h-12 w-full rounded-xl border border-[var(--border)] px-4 outline-none focus:border-[var(--brand)]" />
        <div className="mt-5">
          {availabilityState === "loading" && <p className="flex items-center gap-2 text-sm text-[var(--muted)]"><LoaderCircle className="animate-spin" size={17} /> Checking live availability…</p>}
          {availabilityState === "error" && <p className="text-sm text-red-700">Availability could not be loaded. Try another date.</p>}
          {availabilityState === "ready" && service.booking_mode !== "CUSTOM_ORDER" && slots.length === 0 && <p className="rounded-xl bg-[#fff7e8] p-4 text-sm text-[#7b5717]">No times are available on this date.</p>}
          {service.booking_mode === "APPOINTMENT" && (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {slots.filter((slot) => slot.available).map((slot) => (
                <button key={slot.start_time} type="button" onClick={() => { setSelectedSlot(slot); setStaffId(""); }} className={`rounded-xl border px-3 py-3 text-sm font-semibold ${selectedSlot?.start_time === slot.start_time ? "border-[var(--brand)] bg-[#edf7f1] text-[var(--brand)]" : "border-[var(--border)]"}`}>
                  {shortTime(slot.start_time)}
                </button>
              ))}
            </div>
          )}
          {service.booking_mode === "BATCH" && (
            <div className="space-y-2">
              {slots.filter((slot) => slot.available).map((slot) => (
                <button key={slot.batch_schedule_id} type="button" onClick={() => setSelectedSlot(slot)} className={`flex w-full items-center justify-between rounded-xl border p-4 text-left ${selectedSlot?.batch_schedule_id === slot.batch_schedule_id ? "border-[var(--brand)] bg-[#edf7f1]" : "border-[var(--border)]"}`}>
                  <span><span className="block font-semibold">{shortTime(slot.start_time)}–{shortTime(slot.end_time)}</span><span className="text-xs text-[var(--muted)]">{slot.remaining_capacity} seats remaining</span></span><Users size={18} />
                </button>
              ))}
            </div>
          )}
          {service.booking_mode === "CUSTOM_ORDER" && slots.length > 0 && (
            <div className="grid grid-cols-2 gap-3">
              <label className="text-sm font-semibold">From<input required type="time" value={customStart} min={slots[0].start_time} max={slots[0].end_time} onChange={(event) => setCustomStart(event.target.value)} className="mt-2 h-12 w-full rounded-xl border border-[var(--border)] px-3" /></label>
              <label className="text-sm font-semibold">Until<input required type="time" value={customEnd} min={slots[0].start_time} max={slots[0].end_time} onChange={(event) => setCustomEnd(event.target.value)} className="mt-2 h-12 w-full rounded-xl border border-[var(--border)] px-3" /></label>
              <p className="col-span-2 text-xs leading-5 text-[var(--muted)]">Allowed business window: {slots[0].business_open_time}–{slots[0].business_close_time}</p>
            </div>
          )}
        </div>
        {service.booking_mode === "APPOINTMENT" && selectedSlot && (selectedSlot.available_staff?.length ?? 0) > 0 && (
          <label className="mt-5 block text-sm font-semibold">Preferred professional (optional)<select value={staffId} onChange={(event) => setStaffId(event.target.value)} className="mt-2 h-12 w-full rounded-xl border border-[var(--border)] bg-white px-3"><option value="">Assign anyone available</option>{selectedSlot.available_staff?.map((member) => <option key={member.id} value={member.id}>{member.name}</option>)}</select></label>
        )}
      </section>

      <section className="min-w-0 overflow-hidden rounded-3xl border border-[var(--border)] bg-white p-5 shadow-sm sm:p-7">
        <h2 className="text-lg font-bold">Your details</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-semibold">Full name<input required value={name} onChange={(event) => setName(event.target.value)} className="mt-2 h-12 w-full rounded-xl border border-[var(--border)] px-4" /></label>
          <label className="text-sm font-semibold">Mobile number<input required type="tel" inputMode="tel" placeholder="9876543210" value={phone} onChange={(event) => setPhone(event.target.value)} className="mt-2 h-12 w-full rounded-xl border border-[var(--border)] px-4" /></label>
        </div>
        {service.custom_fields.length > 0 && <div className="mt-5 grid gap-4">{service.custom_fields.map((field) => {
          if (field.field_type === "FILE_UPLOAD") return <p key={field.id} className="rounded-xl bg-[#f4f5f4] p-3 text-sm text-[var(--muted)]">{field.field_label}: file upload will be available in a later phase.</p>;
          if (field.field_type === "BOOLEAN") return <label key={field.id} className="flex items-center gap-3 text-sm font-semibold"><input type="checkbox" checked={Boolean(responses[field.field_label])} onChange={(event) => setResponses({ ...responses, [field.field_label]: event.target.checked })} className="size-5 accent-[var(--brand)]" />{field.field_label}{field.is_required && " *"}</label>;
          if (field.field_type === "DROPDOWN") return <label key={field.id} className="text-sm font-semibold">{field.field_label}{field.is_required && " *"}<select required={field.is_required} value={String(responses[field.field_label] ?? "")} onChange={(event) => setResponses({ ...responses, [field.field_label]: event.target.value })} className="mt-2 h-12 w-full rounded-xl border border-[var(--border)] bg-white px-3"><option value="">Choose one</option>{field.options?.map((option) => <option key={option}>{option}</option>)}</select></label>;
          return <label key={field.id} className="text-sm font-semibold">{field.field_label}{field.is_required && " *"}<input required={field.is_required} value={String(responses[field.field_label] ?? "")} onChange={(event) => setResponses({ ...responses, [field.field_label]: event.target.value })} className="mt-2 h-12 w-full rounded-xl border border-[var(--border)] px-4" /></label>;
        })}</div>}
      </section>

      {error && <p role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</p>}
      <button type="submit" disabled={!canSubmit || submitting} className="flex h-14 w-full items-center justify-center gap-2 rounded-2xl bg-[var(--brand)] font-bold text-white shadow-lg transition hover:bg-[#0b583c] disabled:cursor-not-allowed disabled:opacity-50">
        {submitting ? <><LoaderCircle className="animate-spin" size={19} /> Creating hold…</> : <><Clock3 size={19} /> Hold booking · {rupees(payable)}</>}
      </button>
    </form>
  );
}
