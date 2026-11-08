import Link from "next/link";
import { CalendarDays, ChevronRight, Sparkles } from "lucide-react";

const previews = [
  {
    name: "Glow Salon & Spa",
    detail: "Hydra Facial Glow · 60 min",
    price: "₹1,500",
    href: "/glow-salon-spa",
  },
  {
    name: "Beatz Dance Studio",
    detail: "Beginner Hip Hop · Mon, Wed, Fri",
    price: "₹2,500",
    href: "/beatz-dance-studio",
  },
  {
    name: "Sweet Crumbs",
    detail: "Custom Celebration Cake · 24h notice",
    price: "From ₹2,000",
    href: "/sweet-crumbs",
  },
];

export default function Home() {
  return (
    <main className="mx-auto min-h-screen w-full max-w-5xl px-5 py-8 sm:px-8 sm:py-12">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="grid size-11 place-items-center rounded-2xl bg-[var(--brand)] text-white">
            <Sparkles aria-hidden="true" size={21} />
          </span>
          <div>
            <p className="text-lg font-bold tracking-tight">typein</p>
            <p className="text-sm text-[var(--muted)]">Local bookings, made simple</p>
          </div>
        </div>
        <span className="rounded-full border border-[var(--border)] bg-white px-3 py-1.5 text-sm font-medium text-[var(--brand)]">
          Book a service
        </span>
      </header>

      <section className="mt-12 grid gap-8 lg:grid-cols-[1fr_0.82fr] lg:items-end">
        <div>
          <p className="mb-3 text-sm font-semibold uppercase tracking-[0.18em] text-[var(--brand)]">
            Book nearby businesses
          </p>
          <h1 className="max-w-2xl text-4xl font-bold leading-[1.08] tracking-[-0.04em] sm:text-6xl">
            Your next appointment is a few taps away.
          </h1>
        </div>
        <p className="max-w-xl text-base leading-7 text-[var(--muted)] sm:text-lg">
          Choose a service, find an available time, and confirm your booking in a few taps.
        </p>
      </section>

      <section className="mt-12" aria-labelledby="preview-heading">
        <div className="mb-5 flex items-center justify-between gap-4">
          <h2 id="preview-heading" className="text-xl font-bold tracking-tight">
            Explore booking modes
          </h2>
          <span className="flex items-center gap-2 text-sm text-[var(--muted)]">
            <CalendarDays aria-hidden="true" size={17} /> Live availability
          </span>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {previews.map((preview, index) => (
            <Link
              key={preview.name}
              href={preview.href}
              className="group flex min-h-52 flex-col rounded-3xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-[0_18px_60px_rgba(26,59,43,0.07)] transition hover:-translate-y-1 hover:border-[var(--brand)]"
            >
              <span className="mb-8 w-fit rounded-full bg-[#eef7f1] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[var(--brand)]">
                Mode {String.fromCharCode(65 + index)}
              </span>
              <h3 className="text-lg font-bold">{preview.name}</h3>
              <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{preview.detail}</p>
              <div className="mt-auto flex items-center justify-between pt-6">
                <span className="text-sm font-semibold">{preview.price}</span>
                <ChevronRight
                  aria-hidden="true"
                  className="text-[var(--brand)] transition group-hover:translate-x-1"
                />
              </div>
            </Link>
          ))}
        </div>
      </section>

      <footer className="mt-12 border-t border-[var(--border)] py-6 text-sm text-[var(--muted)]">
        Simple bookings for local service businesses.
      </footer>
    </main>
  );
}
