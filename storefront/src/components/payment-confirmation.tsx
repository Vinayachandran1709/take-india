"use client";

import axios from "axios";
import { useCallback, useEffect, useRef, useState } from "react";
import { apiBaseUrl, rupees } from "@/lib/api";
import { checkout } from "@/lib/checkout";

type Status = {
  merchant_name: string; service_name: string; booking_mode: string;
  booking_date: string; start_time: string; end_time: string; staff_name: string | null;
  booking_status: string; payment_status: string; amount_paid: string;
  balance_due: string; hold_expires_at: string; payment_review_required: boolean;
};

export function PaymentConfirmation({ reference }: { reference: string }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [message, setMessage] = useState("Loading booking…");
  const [busy, setBusy] = useState(false);
  const [expired, setExpired] = useState(false);
  const token = useRef("");
  const inFlight = useRef(false);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    if (!token.current) throw new Error("Open the private booking link in the original browser tab.");
    const { data } = await axios.get<Status>(`${apiBaseUrl}/bookings/${encodeURIComponent(reference)}/status`, {
      headers: { "X-Booking-Token": token.current },
    });
    if (mounted.current) {
      setStatus(data);
      setExpired(Date.parse(data.hold_expires_at) <= Date.now());
    }
    return data;
  }, [reference]);

  useEffect(() => {
    mounted.current = true;
    const fragment = decodeURIComponent(window.location.hash.slice(1));
    window.history.replaceState(null, "", window.location.pathname);
    try {
      if (fragment) sessionStorage.setItem(`booking:${reference}`, fragment);
      token.current = fragment || sessionStorage.getItem(`booking:${reference}`) || "";
    } catch { token.current = fragment; }
    void refresh().then(() => setMessage("")).catch(() => setMessage("Booking unavailable. Use your private booking link."));
    return () => { mounted.current = false; if (pollTimer.current) clearTimeout(pollTimer.current); };
  }, [reference, refresh]);

  useEffect(() => {
    if (!status) return;
    const timer = setTimeout(() => setExpired(true), Math.max(0, Date.parse(status.hold_expires_at) - Date.now()));
    return () => clearTimeout(timer);
  }, [status]);

  async function poll(deadline: number) {
    while (mounted.current && Date.now() < deadline) {
      try {
        const current = await refresh();
        if (current.booking_status === "CONFIRMED" || current.payment_review_required) {
          setMessage(""); return;
        }
      } catch { /* A temporary error does not turn a payment into a failure. */ }
      await new Promise<void>((resolve) => { pollTimer.current = setTimeout(resolve, 3000); });
    }
    if (mounted.current) setMessage("Confirmation is still processing. Use Refresh status to check again.");
  }

  async function pay() {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true); setMessage("Preparing secure Test Mode checkout…");
    try {
      const headers = { "X-Booking-Token": token.current };
      const { data } = await axios.post(`${apiBaseUrl}/bookings/${encodeURIComponent(reference)}/payment`, {}, { headers });
      if (data.state === "RECONCILED") { await refresh(); setMessage(""); return; }
      const result = await checkout(data);
      if (!result) {
        setMessage("Checkout closed. You can retry while your hold is active.");
        await refresh(); return;
      }
      setMessage("Checking payment confirmation…");
      await axios.post(`${apiBaseUrl}/payments/razorpay/verify`, { booking_reference: reference, ...result }, { headers });
      if (pollTimer.current) clearTimeout(pollTimer.current);
      await poll(Date.now() + 60000);
    } catch (error) {
      setMessage(axios.isAxiosError(error)
        ? error.response?.data?.error?.message ?? "Payment could not be verified. Refresh status before retrying."
        : error instanceof Error ? error.message : "Checkout unavailable.");
    } finally { inFlight.current = false; setBusy(false); }
  }

  const confirmed = status?.booking_status === "CONFIRMED";
  return <section className="space-y-5 rounded-3xl border border-[var(--border)] bg-white p-7">
    <p className="text-sm font-semibold text-[var(--brand)]">{status?.merchant_name ?? "Take-India"}</p>
    <h1 className="text-3xl font-bold">{confirmed ? "Booking confirmed" : status?.payment_review_required ? "Payment needs merchant review" : "Complete your booking"}</h1>
    <p className="break-all text-sm">{reference}</p>
    {status && <>
      <h2 className="text-xl font-semibold">{status.service_name}</h2>
      <p>{status.booking_date} · {status.start_time.slice(0, 5)}–{status.end_time.slice(0, 5)}</p>
      {status.staff_name && <p>Professional: {status.staff_name}</p>}
      <p>Paid: {rupees(status.amount_paid)} · Balance: {rupees(status.balance_due)}</p>
      <p className="text-sm">Payment: {status.payment_status.replaceAll("_", " ")}</p>
      {status.payment_review_required && <p>Your payment was received, but your booking could not be confirmed automatically. Contact the merchant with your booking reference.</p>}
      {!confirmed && !status.payment_review_required && <p>{expired ? "Your booking hold has expired." : `Hold expires at ${new Date(status.hold_expires_at).toLocaleTimeString()}`}</p>}
      {!expired && status.booking_status === "PENDING_PAYMENT" && !status.payment_review_required && <button disabled={busy} onClick={() => void pay()} className="w-full rounded-xl bg-[var(--brand)] p-3 font-bold text-white disabled:opacity-50">{busy ? "Processing…" : "Pay in Test Mode"}</button>}
    </>}
    {message && <p role="status" className="text-sm">{message}</p>}
    <button disabled={busy} onClick={() => void refresh().then(() => setMessage("")).catch(() => setMessage("Status unavailable. Try again."))} className="rounded-xl border px-4 py-2">Refresh status</button>
  </section>;
}
