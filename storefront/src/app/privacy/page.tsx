import Link from "next/link";

import { LegalPage } from "@/components/legal-page";
import { SITE_CONFIG, publicMetadata } from "@/lib/site-config";

export const metadata = publicMetadata("Privacy", "How typein handles business, booking and early-access information.", "/privacy");

export default function PrivacyPage() {
  return <LegalPage eyebrow="Privacy" title="Privacy policy" intro="This page explains the information used to run typein and how to ask about or remove it.">
    <section><h2>Information collected</h2><p>For business accounts, typein may receive an owner’s name, email address, phone number, business details, services and schedules. A business’s booking page collects customer names and phone numbers and the details needed to make and manage bookings. The early-access form collects a name, business type and WhatsApp number.</p></section>
    <section><h2>Who controls booking information</h2><p>Each business decides what services it offers and how it uses its customers’ booking information. The business controls that customer data; typein processes it on the business’s behalf to provide booking and scheduling software.</p></section>
    <section><h2>Why information is used</h2><p>Account and booking information is used to display booking pages, check availability, maintain schedules, manage bookings, support business accounts and respond to requests. Early-access details are used to contact people about typein on WhatsApp, as stated beside the form.</p></section>
    <section><h2>Messages</h2><p>Service or account information may be sent by email. Automated WhatsApp booking confirmations are marked “Coming soon” and are not presented as an active feature. Early-access WhatsApp contact follows the notice shown when joining the list.</p></section>
    <section><h2>Service providers</h2><p>typein uses or may use Vercel for web hosting, Render for backend hosting, Neon for database hosting and Resend for email. Meta WhatsApp and Razorpay may be used if the corresponding upcoming messaging or payment features are enabled. Information is shared with a provider only as needed for the relevant service.</p></section>
    <section><h2>Retention</h2><p>For planned trial and subscription accounts: {SITE_CONFIG.DATA_RETENTION} A business can ask about its own account data by email. Customers should first contact the business they booked with; typein can help route a privacy request.</p></section>
    <section><h2>Security</h2><p>Business account access requires login credentials. No internet service can guarantee absolute security. Please contact typein if you have a concern about information held in the service.</p></section>
    <section><h2>Your choices and requests</h2><p>Business owners can ask to access, correct or delete their information. People who joined early access can request removal of their waitlist details. Customers can request information about a booking through the relevant business or contact typein for assistance.</p></section>
    <section><h2>Privacy contact</h2><p>Email <a href={`mailto:${SITE_CONFIG.EMAIL}`}>{SITE_CONFIG.EMAIL}</a> or use the <Link href="/contact">Contact page</Link>.</p></section>
  </LegalPage>;
}
