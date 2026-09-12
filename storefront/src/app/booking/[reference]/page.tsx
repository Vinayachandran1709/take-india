import { PaymentConfirmation } from "@/components/payment-confirmation";

export default async function BookingPage({ params }: { params: Promise<{ reference: string }> }) {
  const { reference } = await params;
  return <main className="mx-auto max-w-xl px-5 py-12"><PaymentConfirmation reference={reference} /></main>;
}
