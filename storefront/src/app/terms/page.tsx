import Link from "next/link";

import { LegalPage } from "@/components/legal-page";
import { SITE_CONFIG, publicMetadata } from "@/lib/site-config";

export const metadata = publicMetadata("Terms of service", "Terms for using typein booking pages and business accounts.", "/terms");

export default function TermsPage() {
  return <LegalPage eyebrow="Terms" title="Terms of service" intro="These terms explain the use of typein's booking software and the responsibilities of businesses using it.">
    <section><h2>The service</h2><p>{SITE_CONFIG.TRADE_NAME} provides software for business booking pages, service and class schedules, customer booking management and a bookings dashboard. Features marked “Coming soon” are not part of the currently available service.</p><p>{SITE_CONFIG.TRADE_NAME} is operated by {SITE_CONFIG.OPERATOR_NAME}, an individual.</p></section>
    <section><h2>Accounts and business information</h2><p>A business is responsible for its account access, the accuracy of its service details, schedules, prices and change policies, and the services it provides to customers. Self-serve signup is coming soon; early-access onboarding may be assisted.</p></section>
    <section><h2>Trial and subscription billing</h2><p>When self-serve signup and subscriptions become available, the planned trial is {SITE_CONFIG.PRICING.trialDays} days free with no card needed. Continued access after the trial is planned at ₹{SITE_CONFIG.PRICING.monthlyInr.toLocaleString("en-IN")} per month. Paid subscriptions are not currently offered through this site.</p><p>{SITE_CONFIG.CANCELLATION} The <Link href="/refund-policy">Refund & Cancellation policy</Link> explains mistaken charges.</p></section>
    <section><h2>Acceptable use</h2><p>Use typein only for lawful services and accurate bookings. Do not misuse the service, interfere with its operation, submit fraudulent bookings, or use customer information without an appropriate reason or permission.</p></section>
    <section><h2>Business and customer bookings</h2><p>typein supplies booking software. It is not a party to a booking or service agreement between a business and its customer. The business is responsible for delivering its service, resolving customer disputes and applying its published policies.</p></section>
    <section><h2>Customer payments</h2><p>UPI advance payments are coming soon. If introduced, they will go directly to the business. typein does not hold customer funds and is not the seller of a business’s services.</p></section>
    <section><h2>WhatsApp and email</h2><p>Booking confirmation messages through WhatsApp are coming soon. Where messaging is enabled, businesses must provide accurate contact details and obtain any consent required to contact customers. typein may use email for service and account communication.</p></section>
    <section><h2>Availability and liability</h2><p>typein aims to keep the software available, but uninterrupted access is not guaranteed. To the extent allowed by law, typein is not responsible for a business’s services, customer disputes, or indirect losses arising from use of the software. Nothing in these terms limits a right or liability that cannot legally be limited.</p></section>
    <section><h2>Access ending and data retention</h2><p>Under the planned trial and subscription model, access is locked when a trial ends or a subscription lapses. {SITE_CONFIG.DATA_RETENTION}</p></section>
    <section><h2>Changes to these terms</h2><p>These terms may be updated as the service develops. The date above shows the latest version. Material changes will be communicated through the service or the contact details associated with an account.</p></section>
    <section><h2>Governing law</h2><p>These terms are governed by the {SITE_CONFIG.GOVERNING_LAW}. Disputes are subject to courts with jurisdiction under applicable law.</p></section>
    <section><h2>Questions</h2><p>Contact <a href={`mailto:${SITE_CONFIG.EMAIL}`}>{SITE_CONFIG.EMAIL}</a> or see the <Link href="/contact">Contact page</Link>.</p></section>
  </LegalPage>;
}
