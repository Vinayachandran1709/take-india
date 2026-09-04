import Link from "next/link";
import { ArrowRight, CalendarClock } from "lucide-react";
import { notFound } from "next/navigation";

import { StorefrontHeader } from "@/components/storefront-header";
import { getStorefront, rupees } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function MerchantStorefront({ params }: PageProps<"/[slug]">) {
  const { slug } = await params;
  const storefront = await getStorefront(slug);
  if (!storefront) notFound();

  return (
    <main className="min-h-screen">
      <StorefrontHeader storefront={storefront} />
      <section className="mx-auto max-w-5xl px-5 py-10 sm:px-8 sm:py-14">
        <div className="max-w-2xl">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">Book direct</p>
          <h1 className="mt-3 text-4xl font-bold tracking-[-0.04em] sm:text-5xl">What can we help you with?</h1>
          <p className="mt-4 text-base leading-7 text-[var(--muted)]">Choose a service to see live availability and place a temporary unpaid hold.</p>
        </div>
        {storefront.services.length === 0 ? (
          <div className="mt-10 rounded-3xl border border-dashed border-[var(--border)] p-10 text-center text-[var(--muted)]">No services are accepting bookings yet.</div>
        ) : (
          <div className="mt-10 space-y-9">
            {storefront.categories.map((category) => (
              <section key={category}>
                <h2 className="text-lg font-bold">{category}</h2>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  {storefront.services.filter((service) => service.category === category).map((service) => (
                    <Link key={service.id} href={`/${slug}/services/${service.id}`} className="group rounded-3xl border border-[var(--border)] bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-[var(--brand)] sm:p-6">
                      <div className="flex items-start justify-between gap-4"><span className="rounded-full bg-[#eef7f1] px-3 py-1 text-xs font-semibold text-[var(--brand)]">{service.booking_mode.replace("_", " ")}</span><ArrowRight className="text-[var(--brand)] transition group-hover:translate-x-1" size={19} /></div>
                      <h3 className="mt-6 text-xl font-bold tracking-tight">{service.title}</h3>
                      <p className="mt-2 line-clamp-2 text-sm leading-6 text-[var(--muted)]">{service.description ?? "Reserve this service online."}</p>
                      <div className="mt-6 flex items-end justify-between"><span className="font-bold">{rupees(service.price)}</span><span className="flex items-center gap-1 text-xs text-[var(--muted)]"><CalendarClock size={14} />{service.duration_minutes ? `${service.duration_minutes} min` : service.booking_mode === "BATCH" ? "Scheduled class" : `${service.prep_lead_time_hours ?? 0}h notice`}</span></div>
                    </Link>
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
