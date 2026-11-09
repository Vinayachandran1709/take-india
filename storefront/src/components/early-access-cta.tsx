"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { ArrowRight } from "lucide-react";

import { SITE_CONFIG } from "@/lib/site-config";

const businessTypes = [
  "Salon & hair studio",
  "Makeup, lash & nail artist",
  "Custom baker",
  "Aesthetic or dental clinic",
  "Yoga, dance or fitness studio",
  "Other",
] as const;

function waitlistEndpoint(): string | null {
  const raw = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (!raw) return null;
  try {
    const url = new URL(raw);
    if (url.protocol !== "https:" && !(url.protocol === "http:" && ["localhost", "127.0.0.1"].includes(url.hostname))) return null;
    const base = url.toString().replace(/\/$/, "");
    return `${base.endsWith("/api/v1") ? base : `${base}/api/v1`}/waitlist`;
  } catch {
    return null;
  }
}

export function EarlyAccessCTA() {
  const formRef = useRef<HTMLFormElement>(null);
  const [state, setState] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const endpoint = waitlistEndpoint();

  if (SITE_CONFIG.SIGNUP_ENABLED) {
    return <Link className="site-button site-button-primary" href={SITE_CONFIG.SIGNUP_URL}>Start 1 month free <ArrowRight aria-hidden="true" size={18} /></Link>;
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!endpoint || state === "loading") return;
    const form = formRef.current;
    if (!form || !form.reportValidity()) return;
    const values = new FormData(form);
    const payload = {
      name: String(values.get("name") ?? "").trim(),
      business_type: String(values.get("business_type") ?? "").trim(),
      whatsapp: String(values.get("whatsapp") ?? "").trim(),
    };
    setState("loading");
    setMessage("Submitting your details…");
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 90_000);
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        credentials: "omit",
        cache: "no-store",
        signal: controller.signal,
      });
      if (!response.ok) {
        setState("error");
        setMessage(response.status === 400 || response.status === 422
          ? "Check your name, business type and Indian WhatsApp number."
          : response.status === 429
            ? "Too many attempts. Please wait a little before trying again."
            : "Your details could not be saved. Please try again shortly.");
        return;
      }
      const result: unknown = await response.json();
      if (!result || typeof result !== "object" || !("accepted" in result) || result.accepted !== true) throw new Error("Not acknowledged");
      form.reset();
      setState("success");
      setMessage("You're on the early-access list. Your details were submitted successfully; typein will contact you on WhatsApp about early access.");
    } catch {
      setState("error");
      setMessage("Your registration could not be confirmed. Please try again; your details are still here.");
    } finally {
      clearTimeout(timeout);
    }
  }

  return (
    <div className="waitlist-panel">
      <form ref={formRef} onSubmit={submit} aria-busy={state === "loading"}>
        <div className="waitlist-grid">
          <label>Name<input name="name" type="text" autoComplete="name" maxLength={120} required disabled={!endpoint || state === "loading"} placeholder="Your name" /></label>
          <label>Business type<select name="business_type" defaultValue="" required disabled={!endpoint || state === "loading"}>
            <option value="" disabled>Choose your business</option>
            {businessTypes.map((type) => <option key={type} value={type}>{type}</option>)}
          </select></label>
          <label>WhatsApp number<input name="whatsapp" type="tel" autoComplete="tel" inputMode="tel" maxLength={32} required disabled={!endpoint || state === "loading"} placeholder="+91 98765 43210" /></label>
          <button type="submit" className="site-button site-button-primary" disabled={!endpoint || state === "loading"}>{state === "loading" ? "Joining…" : "Join early access"}<ArrowRight aria-hidden="true" size={18} /></button>
        </div>
        <p className="waitlist-consent">By joining, you agree to receive typein early-access updates on WhatsApp. <Link href="/privacy">Privacy</Link></p>
        <p className={`waitlist-status ${state}`} role="status" aria-live="polite">{endpoint ? message : "Sign-up is temporarily unavailable. Please check back soon."}</p>
      </form>
    </div>
  );
}
