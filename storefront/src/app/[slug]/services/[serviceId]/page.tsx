import { ArrowLeft, BadgeIndianRupee, Clock3 } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { BookingForm } from "@/components/booking-form";
import { StorefrontHeader } from "@/components/storefront-header";
import { getStorefront, rupees } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ServicePage({
  params,
}: PageProps<"/[slug]/services/[serviceId]">) {
  const { slug, serviceId } = await params;
  const storefront = await getStorefront(slug);
  if (!storefront) notFound();
  const service = storefront.services.find((item) => item.id === serviceId);
  if (!service) notFound();

  return (
    <main className="min-h-screen">
      <StorefrontHeader storefront={storefront} />
      <div className="mx-auto max-w-5xl px-5 py-8 sm:px-8 sm:py-12">
        <Link href={`/${slug}`} className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--brand)]"><ArrowLeft size={16} /> All services</Link>
        <div className="mt-6 grid gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:items-start">
          <section className="lg:sticky lg:top-8">
            <span className="rounded-full bg-[#fff1d7] px-3 py-1 text-xs font-semibold uppercase tracking-wide text-[#80570f]">{service.booking_mode.replace("_", " ")}</span>
            <h1 className="mt-5 text-4xl font-bold tracking-[-0.04em]">{service.title}</h1>
            <p className="mt-4 leading-7 text-[var(--muted)]">{service.description ?? "Choose an available time and confirm your booking."}</p>
            <div className="mt-7 flex flex-wrap gap-3 text-sm font-semibold">
              <span className="flex items-center gap-2 rounded-xl border border-[var(--border)] bg-white px-3 py-2"><BadgeIndianRupee size={17} />{rupees(service.price)}</span>
              <span className="flex items-center gap-2 rounded-xl border border-[var(--border)] bg-white px-3 py-2"><Clock3 size={17} />{service.duration_minutes ? `${service.duration_minutes} minutes` : service.booking_mode === "CUSTOM_ORDER" ? `${service.prep_lead_time_hours ?? 0}h lead time` : "Fixed schedule"}</span>
            </div>
          </section>
          {storefront.merchant.accepting_bookings ? <BookingForm slug={slug} service={service} /> : <p role="status" className="rounded-3xl border border-[#e6cf9b] bg-[#fff8e9] p-6 font-semibold text-[#614819]">This business is not accepting bookings right now.</p>}
        </div>
      </div>
    </main>
  );
}
