"use client";

import axios from "axios";
import { CalendarDays, LoaderCircle } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { apiBaseUrl } from "@/lib/api";
import type { Availability, AvailabilitySlot, ManagedBooking } from "@/lib/types";

function requestError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    return error.response?.data?.detail ?? error.response?.data?.error?.message ??
      "We could not update this booking. Please try again.";
  }
  return "We could not update this booking. Please try again.";
}

export function ManageClient({ token, initialBooking }: { token: string; initialBooking: ManagedBooking }) {
  const [booking, setBooking] = useState(initialBooking);
  const [bookingDate, setBookingDate] = useState(initialBooking.booking_date);
  const [availability, setAvailability] = useState<Availability | null>(null);
  const [availabilityState, setAvailabilityState] = useState<"loading" | "ready" | "error">("loading");
  const [selectedStart, setSelectedStart] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!booking.can_reschedule) return;
    const controller = new AbortController();
    axios.get<Availability>(
      `${apiBaseUrl}/storefront/${encodeURIComponent(booking.merchant_slug)}/available-slots`,
      {
        params: { service_id: booking.service_id, date: bookingDate },
        signal: controller.signal,
      },
    ).then(({ data }) => {
      setAvailability(data);
      setAvailabilityState("ready");
    }).catch((requestFailure) => {
      if (!axios.isCancel(requestFailure)) setAvailabilityState("error");
    });
    return () => controller.abort();
  }, [booking.can_reschedule, booking.merchant_slug, booking.service_id, bookingDate]);

  function changeDate(value: string) {
    setBookingDate(value);
    setSelectedStart("");
    setAvailability(null);
    setAvailabilityState("loading");
    setError("");
  }

  async function cancel() {
    if (busy) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await axios.post(`${apiBaseUrl}/manage/${encodeURIComponent(token)}/cancel`);
      setBooking((current) => ({ ...current, booking_status: "CANCELLED", can_cancel: false, can_reschedule: false }));
      setMessage("Your booking has been cancelled.");
    } catch (requestFailure) {
      setError(requestError(requestFailure));
    } finally {
      setBusy(false);
    }
  }

  async function reschedule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !selectedStart || availabilityState !== "ready") return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await axios.post(`${apiBaseUrl}/manage/${encodeURIComponent(token)}/reschedule`, {
        new_booking_date: bookingDate,
        new_start_time: selectedStart,
      });
      setMessage("Your booking has been rescheduled.");
      setSelectedStart("");
      try {
        const { data } = await axios.get<ManagedBooking>(`${apiBaseUrl}/manage/${encodeURIComponent(token)}`);
        setBooking(data);
        setBookingDate(data.booking_date);
      } catch {
        setMessage("Your booking was rescheduled. Refresh this page to see the updated details.");
      }
    } catch (requestFailure) {
      setError(requestError(requestFailure));
    } finally {
      setBusy(false);
    }
  }

  const slots: AvailabilitySlot[] = availability?.available_slots.filter((slot) => slot.available) ?? [];
  const locked = !booking.can_cancel && !booking.can_reschedule;

  return (
    <div>
      <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">{booking.business_name}</p>
      <h1 className="mt-3 text-3xl font-bold">Manage your booking</h1>
      <section className="mt-6 rounded-3xl border border-[var(--border)] bg-white p-6 shadow-sm">
        <h2 className="text-xl font-bold">{booking.service_title}</h2>
        <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
          <div><dt className="text-[var(--muted)]">Date</dt><dd className="font-semibold">{booking.booking_date}</dd></div>
          <div><dt className="text-[var(--muted)]">Time</dt><dd className="font-semibold">{booking.start_time.slice(0, 5)}–{booking.end_time.slice(0, 5)}</dd></div>
          <div><dt className="text-[var(--muted)]">Status</dt><dd className="font-semibold">{booking.booking_status.replaceAll("_", " ")}</dd></div>
          <div><dt className="text-[var(--muted)]">Reference</dt><dd className="font-semibold">{booking.booking_reference}</dd></div>
        </dl>
        <p className="mt-4 text-xs text-[var(--muted)]">Times shown in {booking.timezone}.</p>
      </section>

      {message && <p role="status" className="mt-5 rounded-2xl border border-[#b8dbc8] bg-[#f3fbf6] p-4 text-[var(--brand)]">{message}</p>}
      {error && <p role="alert" className="mt-5 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700">{error}</p>}

      {locked && booking.booking_status === "CONFIRMED" && (
        <p className="mt-6 rounded-2xl bg-[#fff7e8] p-5 text-[#7b5717]">Changes are locked this close to the appointment. Please contact the business.</p>
      )}
      {booking.booking_status === "CANCELLED" && <p className="mt-6">This booking is cancelled.</p>}

      {booking.can_reschedule && (
        <form onSubmit={reschedule} className="mt-7 rounded-3xl border border-[var(--border)] bg-white p-6 shadow-sm">
          <h2 className="flex items-center gap-2 text-xl font-bold"><CalendarDays size={20} />Choose a new time</h2>
          <label className="mt-5 block text-sm font-semibold">Date
            <input type="date" required value={bookingDate} onChange={(event) => changeDate(event.target.value)} className="mt-2 h-12 w-full rounded-xl border border-[var(--border)] px-4" />
          </label>
          {availabilityState === "loading" && <p className="mt-4 flex items-center gap-2 text-sm text-[var(--muted)]"><LoaderCircle size={17} className="animate-spin" />Checking availability…</p>}
          {availabilityState === "error" && <p role="alert" className="mt-4 text-sm text-red-700">Availability could not be loaded. Try another date.</p>}
          {availabilityState === "ready" && slots.length === 0 && <p className="mt-4 text-sm text-[var(--muted)]">No times available on this date.</p>}
          {availabilityState === "ready" && booking.booking_mode === "CUSTOM_ORDER" && slots.length > 0 ? (
            <label className="mt-5 block text-sm font-semibold">New start time
              <input type="time" required min={slots[0].start_time.slice(0, 5)} max={slots[0].end_time.slice(0, 5)} value={selectedStart} onChange={(event) => setSelectedStart(event.target.value)} className="mt-2 h-12 w-full rounded-xl border border-[var(--border)] px-4" />
            </label>
          ) : availabilityState === "ready" && slots.length > 0 ? (
            <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-3" role="group" aria-label="Available times">
              {slots.map((slot) => (
                <button key={`${slot.start_time}-${slot.batch_schedule_id ?? ""}`} type="button" aria-pressed={selectedStart === slot.start_time.slice(0, 5)} onClick={() => setSelectedStart(slot.start_time.slice(0, 5))} className={`rounded-xl border px-3 py-3 text-sm font-semibold ${selectedStart === slot.start_time.slice(0, 5) ? "border-[var(--brand)] bg-[#edf7f1]" : "border-[var(--border)]"}`}>
                  {slot.start_time.slice(0, 5)}
                </button>
              ))}
            </div>
          ) : null}
          <button type="submit" disabled={!selectedStart || busy || availabilityState !== "ready"} className="mt-5 w-full rounded-xl bg-[var(--brand)] px-5 py-3 font-bold text-white disabled:opacity-50">
            {busy ? "Saving…" : "Reschedule booking"}
          </button>
        </form>
      )}

      {booking.can_cancel && (
        <section className="mt-7 rounded-3xl border border-[var(--border)] bg-white p-6 shadow-sm">
          <h2 className="text-xl font-bold">Need to cancel?</h2>
          <button type="button" onClick={() => void cancel()} disabled={busy} className="mt-4 rounded-xl border border-red-300 px-5 py-3 font-semibold text-red-700 disabled:opacity-50">
            {busy ? "Please wait…" : "Cancel booking"}
          </button>
        </section>
      )}
    </div>
  );
}
