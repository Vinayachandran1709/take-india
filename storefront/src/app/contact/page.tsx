import { Mail, Phone } from "lucide-react";

import { LegalPage } from "@/components/legal-page";
import { SITE_CONFIG, publicMetadata } from "@/lib/site-config";

export const metadata = publicMetadata("About & Contact", "Contact typein for booking software support and questions.", "/contact");

export default function ContactPage() {
  return <LegalPage eyebrow="About & Contact" title="Get in touch" intro="typein is booking and scheduling software for local service businesses.">
    <section><h2>About typein</h2><p>The trade name and legal name are {SITE_CONFIG.TRADE_NAME}. typein is operated by {SITE_CONFIG.OPERATOR_NAME}, an individual. It provides booking pages, class schedules, customer management links and a bookings dashboard.</p></section>
    <section><h2>Contact</h2><div className="contact-options"><a href={`mailto:${SITE_CONFIG.EMAIL}`}><Mail aria-hidden="true" size={20} /><span><strong>Email</strong>{SITE_CONFIG.EMAIL}</span></a><a href={`tel:${SITE_CONFIG.PHONE.replace(/\s/g, "")}`}><Phone aria-hidden="true" size={20} /><span><strong>Phone</strong>{SITE_CONFIG.PHONE}</span></a></div></section>
    <section><h2>Support</h2><p>{SITE_CONFIG.SUPPORT}</p></section>
  </LegalPage>;
}
