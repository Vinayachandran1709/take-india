import Link from "next/link";
import { MapPin, Sparkles } from "lucide-react";

import type { Storefront } from "@/lib/types";

export function StorefrontHeader({ storefront }: { storefront: Storefront }) {
  return (
    <header className="border-b border-[var(--border)] bg-white/80 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-5 py-4 sm:px-8">
        <Link href={`/${storefront.merchant.slug}`} className="flex min-w-0 flex-1 items-center gap-3 overflow-hidden">
          <span className="grid size-11 shrink-0 place-items-center rounded-2xl bg-[var(--brand)] text-white">
            <Sparkles aria-hidden="true" size={20} />
          </span>
          <span className="min-w-0">
            <span className="block truncate font-bold tracking-tight">
              {storefront.merchant.business_name}
            </span>
            <span className="flex items-center gap-1 truncate text-xs text-[var(--muted)]">
              <MapPin aria-hidden="true" size={12} />
              {storefront.merchant.address ?? "Book directly with this business"}
            </span>
          </span>
        </Link>
        <span className="shrink-0 rounded-full bg-[#eef7f1] px-3 py-1.5 text-xs font-semibold text-[var(--brand)]">
          Secure hold
        </span>
      </div>
    </header>
  );
}
