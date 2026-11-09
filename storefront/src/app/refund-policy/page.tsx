import Link from "next/link";

import { LegalPage } from "@/components/legal-page";
import { SITE_CONFIG, publicMetadata } from "@/lib/site-config";

export const metadata = publicMetadata("Refund & Cancellation", "How future typein subscriptions can be cancelled and when a mistaken charge is refunded.", "/refund-policy");

export default function RefundPolicyPage() {
  return <LegalPage eyebrow="Billing policy" title="Refund & Cancellation" intro="This policy applies to typein subscription fees when paid subscriptions become available. Self-serve billing is not yet active.">
    <section><h2>How to cancel</h2><p>{SITE_CONFIG.CANCELLATION} If a dashboard cancellation control is not available, email <a href={`mailto:${SITE_CONFIG.EMAIL}`}>{SITE_CONFIG.EMAIL}</a> with the account details needed to identify your subscription. Do not send payment credentials by email.</p></section>
    <section><h2>Refunds</h2><p>{SITE_CONFIG.REFUND_RULE}</p></section>
    <section><h2>Report a mistaken charge</h2><p>Email <a href={`mailto:${SITE_CONFIG.EMAIL}`}>{SITE_CONFIG.EMAIL}</a> and describe the charge and the account concerned. typein will review it and, if it was charged by mistake, refund it to the original payment method.</p></section>
    <section><h2>Customer payments to a business</h2><p>UPI advance payments are coming soon. If introduced, customers pay the business directly; typein does not hold those funds. A refund for a business’s service is handled under that business’s own policy.</p></section>
    <section><h2>More information</h2><p>See the <Link href="/terms">Terms of service</Link> or <Link href="/contact">contact typein</Link>.</p></section>
  </LegalPage>;
}
