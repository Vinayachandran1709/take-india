import type { Metadata } from "next";

import { ManageClient } from "@/components/manage-client";
import { apiBaseUrl } from "@/lib/api";
import type { ManagedBooking } from "@/lib/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Manage booking | typein",
  robots: { index: false, follow: false },
};

export default async function ManagePage({ params }: PageProps<"/manage/[token]">) {
  const { token } = await params;
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}/manage/${encodeURIComponent(token)}`, {
      cache: "no-store",
    });
  } catch {
    return <main className="mx-auto max-w-xl px-5 py-12"><h1 className="text-3xl font-bold">Booking temporarily unavailable</h1><p className="mt-4">Please try again shortly.</p></main>;
  }

  if (response.status === 404) {
    return <main className="mx-auto max-w-xl px-5 py-12"><h1 className="text-3xl font-bold">Invalid or expired link</h1><p className="mt-4">Please contact the business for help with your booking.</p></main>;
  }
  if (!response.ok) {
    return <main className="mx-auto max-w-xl px-5 py-12"><h1 className="text-3xl font-bold">Booking temporarily unavailable</h1><p className="mt-4">Please try again shortly.</p></main>;
  }

  const booking = (await response.json()) as ManagedBooking;
  return (
    <main className="mx-auto max-w-2xl px-5 py-12 sm:px-8">
      <meta name="referrer" content="no-referrer" />
      <ManageClient token={token} initialBooking={booking} />
    </main>
  );
}
