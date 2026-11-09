import Link from "next/link";
import { Check } from "lucide-react";

import { EarlyAccessCTA } from "@/components/early-access-cta";
import { PublicShell } from "@/components/public-shell";
import { SITE_CONFIG, publicMetadata } from "@/lib/site-config";

export const metadata = publicMetadata("Pricing", `Planned typein pricing: ${SITE_CONFIG.PRICING.trialDays} days free with no card needed, then ₹${SITE_CONFIG.PRICING.monthlyInr.toLocaleString("en-IN")} per month. Self-serve signup is coming soon.`, "/pricing");

const included = ["A business booking page", "Multiple services and class timetables", "Teachers and available seats", "Customer cancel and reschedule within your policy", "A bookings dashboard"];

export default function PricingPage() {
  return <PublicShell>
    <section className="site-container page-hero"><p className="site-eyebrow">Pricing</p><h1>Start simple.<br /><em>Grow at your pace.</em></h1><p>The planned self-serve offer is one month free, then a straightforward monthly subscription. Self-serve signup is coming soon.</p></section>
    <section className="site-container pricing-cards" aria-label="Planned pricing">
      <article className="pricing-card"><span className="pricing-card-label">Free trial</span><h2>Try typein</h2><p className="pricing-number">{SITE_CONFIG.PRICING.trialDays} <span>days</span></p><p>No card needed. Explore the booking page and dashboard before deciding.</p><span className="coming-badge">Self-serve signup coming soon</span></article>
      <article className="pricing-card pricing-card-accent"><span className="pricing-card-label">After the trial</span><h2>typein monthly</h2><p className="pricing-number">₹{SITE_CONFIG.PRICING.monthlyInr.toLocaleString("en-IN")} <span>/ month</span></p><p>Continue using the booking page and dashboard with a monthly subscription.</p><span className="pricing-small">Cancel any time; no further charges after cancelling.</span></article>
    </section>
    <section className="site-container included-section"><div><p className="site-eyebrow">Included</p><h2>Everything needed to take a booking.</h2></div><ul>{included.map((item) => <li key={item}><Check aria-hidden="true" size={18} />{item}</li>)}</ul></section>
    <section className="site-section"><div className="site-container faq-layout"><div><p className="site-eyebrow">Pricing FAQ</p><h2>Before you decide.</h2></div><div className="faq-list">
      <details><summary>What happens after the free trial?<span aria-hidden="true">+</span></summary><p>When subscriptions are available, continuing after the {SITE_CONFIG.PRICING.trialDays}-day trial will cost ₹{SITE_CONFIG.PRICING.monthlyInr.toLocaleString("en-IN")} per month. If access lapses, the account is locked under the <Link href="/terms">Terms</Link>.</p></details>
      <details><summary>Can I cancel any time?<span aria-hidden="true">+</span></summary><p>Yes. Cancel from the dashboard when billing is available, or email <a href={`mailto:${SITE_CONFIG.EMAIL}`}>{SITE_CONFIG.EMAIL}</a>. No further subscription charges follow cancellation.</p></details>
      <details><summary>Are subscription fees refundable?<span aria-hidden="true">+</span></summary><p>Generally no. A mistaken charge, such as a duplicate charge, is refunded to the original payment method. Read the <Link href="/refund-policy">Refund & Cancellation policy</Link>.</p></details>
      <details><summary>Will typein hold customer payments?<span aria-hidden="true">+</span></summary><p>No. UPI advance payments are coming soon. When offered, those payments will go directly to the business.</p></details>
    </div></div></section>
    <section className="site-section early-access-section" id="early-access"><div className="site-container early-access-layout"><div><p className="site-eyebrow">Early access</p><h2>Want to try it?</h2><p>Join the list for updates about when typein becomes available.</p></div><EarlyAccessCTA /></div></section>
  </PublicShell>;
}
