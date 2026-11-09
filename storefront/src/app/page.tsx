import Link from "next/link";
import { ArrowRight, CalendarDays, Check, Clock3, LayoutDashboard, Link2, MessageCircle, ShieldCheck, Sparkles, UsersRound } from "lucide-react";

import { EarlyAccessCTA } from "@/components/early-access-cta";
import { PublicShell } from "@/components/public-shell";
import { SITE_CONFIG, publicMetadata } from "@/lib/site-config";

export const metadata = publicMetadata(
  "Booking pages for service businesses",
  "typein gives service businesses a booking page, class timetables and a simple bookings dashboard. Join early access.",
  "/",
);

const liveFeatures = [
  { icon: Link2, title: "Your own booking page", detail: "Give customers one clear place to explore services and book at typein.co/yourname." },
  { icon: CalendarDays, title: "Services and classes", detail: "Show appointments alongside class timetables, teachers and available seats." },
  { icon: Clock3, title: "Changes within your policy", detail: "Customers can cancel or reschedule from a management link when your rules allow it." },
  { icon: LayoutDashboard, title: "A bookings dashboard", detail: "See upcoming bookings and keep the day's schedule in one place." },
];

const comingSoon = [
  { title: "UPI advance payment", detail: "If enabled later, customers will pay the business directly. typein will not hold customer funds." },
  { title: "WhatsApp confirmations", detail: "Booking updates sent to customers through approved WhatsApp messages." },
  { title: "Free demo class option", detail: "Offer a first class without charging for it." },
  { title: "Self-serve signup", detail: "Create and set up a business account without assisted onboarding." },
];

const audiences = ["Salons", "Nail studios", "Bridal studios", "Beauty clinics", "Wellness clinics", "Yoga & dance studios"];

const steps = [
  { number: "01", title: "Set up your page", detail: "Add services, class times, teachers and the rules for changes." },
  { number: "02", title: "Share your booking address", detail: "Customers open typein.co/yourname, choose a service and see available times." },
  { number: "03", title: "Stay on top of bookings", detail: "See bookings in your dashboard. Customers can manage their own changes within your policy." },
];

const questions = [
  { question: "Is typein open for self-serve signup?", answer: "Not yet. Join early access and typein will contact you about availability." },
  { question: "Can one business offer different services?", answer: "Yes. A booking page can list multiple services and scheduled classes, each with its own availability." },
  { question: "Can customers change a booking?", answer: "Customers can use their management link to cancel or reschedule when the business's policy permits it." },
  { question: "Does typein collect customer payments?", answer: "No. Advance UPI payment is coming soon; those payments would go directly to the business, not through typein." },
];

const structuredData = [
  { "@context": "https://schema.org", "@type": "Organization", name: SITE_CONFIG.TRADE_NAME, legalName: SITE_CONFIG.LEGAL_NAME, url: SITE_CONFIG.SITE_URL, email: SITE_CONFIG.EMAIL, telephone: SITE_CONFIG.PHONE },
  { "@context": "https://schema.org", "@type": "SoftwareApplication", name: SITE_CONFIG.TRADE_NAME, url: SITE_CONFIG.SITE_URL, applicationCategory: "BusinessApplication", operatingSystem: "Web", description: "Booking pages and scheduling for local service businesses." },
];

export default function HomePage() {
  return (
    <PublicShell>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData).replace(/</g, "\\u003c") }} />
      <section className="site-hero">
        <div className="site-container hero-grid">
          <div className="hero-copy">
            <p className="site-eyebrow"><span className="eyebrow-dot" /> Booking, without the back-and-forth</p>
            <h1>One booking page.<br /><em>Room for everything</em> you do.</h1>
            <p className="hero-lead">typein is your booking page for salons, nail and bridal studios, beauty and wellness clinics, and yoga and dance studios. Share your page, show what is available and keep bookings organized.</p>
            <div className="hero-actions">
              <Link className="site-button site-button-primary" href="#early-access">Join early access <ArrowRight aria-hidden="true" size={18} /></Link>
              <Link className="site-button site-button-light" href="/pricing">See pricing</Link>
            </div>
            <p className="hero-note"><Check aria-hidden="true" size={17} /> One month free when self-serve signup opens. No card needed.</p>
          </div>
          <div className="hero-visual" aria-label="Illustrative typein booking page">
            <div className="preview-label"><Sparkles aria-hidden="true" size={15} /> Illustrative booking page</div>
            <div className="preview-window">
              <div className="preview-browser"><span /><span /><span /><p>typein.co/yourname</p></div>
              <div className="preview-business"><div className="preview-avatar">t.</div><div><strong>Your studio</strong><small>Book a service or class</small></div></div>
              <div className="preview-heading"><span>Choose what works for you</span><span className="preview-available">Available</span></div>
              <div className="preview-service"><span className="preview-service-icon"><CalendarDays size={19} /></span><span><strong>Appointment</strong><small>Pick an open time</small></span><ArrowRight size={16} /></div>
              <div className="preview-service"><span className="preview-service-icon"><UsersRound size={19} /></span><span><strong>Class timetable</strong><small>See teachers and seats</small></span><ArrowRight size={16} /></div>
              <div className="preview-slots"><span>Today</span><span>Tomorrow</span><span>Next week</span></div>
              <div className="preview-selection"><span className="preview-selection-dot" /> Your next booking, all in one place.</div>
            </div>
            <div className="preview-floating"><ShieldCheck aria-hidden="true" size={18} /> Customer changes follow your policy</div>
          </div>
        </div>
      </section>

      <section className="site-section" id="features">
        <div className="site-container">
          <div className="section-heading"><div><p className="site-eyebrow">What you get</p><h2>The essentials for a smoother day.</h2></div><p>Keep the booking experience clear for customers and manageable for you.</p></div>
          <div className="feature-grid">
            {liveFeatures.map(({ icon: Icon, title, detail }) => <article className="feature-card" key={title}><span className="feature-icon"><Icon aria-hidden="true" size={22} /></span><h3>{title}</h3><p>{detail}</p></article>)}
          </div>
          <div className="coming-soon-block"><div className="coming-soon-heading"><span className="site-eyebrow">On the way</span><h3>Coming soon</h3></div><div className="coming-soon-grid">{comingSoon.map((item) => <article key={item.title}><span className="coming-badge">Coming soon</span><h4>{item.title}</h4><p>{item.detail}</p></article>)}</div></div>
        </div>
      </section>

      <section className="site-section audience-section">
        <div className="site-container audience-grid"><div><p className="site-eyebrow">Who it is for</p><h2>One flexible home for many kinds of service.</h2><p className="section-lead">A business can offer more than one service. Put appointments and classes side by side on the same page.</p></div><div className="audience-list">{audiences.map((item, index) => <div key={item}><span>{String(index + 1).padStart(2, "0")}</span><strong>{item}</strong><ArrowRight aria-hidden="true" size={18} /></div>)}</div></div>
      </section>

      <section className="site-section"><div className="site-container"><div className="section-heading"><div><p className="site-eyebrow">How it works</p><h2>From your setup to their booking.</h2></div></div><div className="steps-grid">{steps.map((step) => <article key={step.number}><span>{step.number}</span><h3>{step.title}</h3><p>{step.detail}</p></article>)}</div></div></section>

      {SITE_CONFIG.PRODUCT_VIDEO_URL ? <section className="site-section"><div className="site-container"><h2>See typein in action</h2><div className="video-frame"><iframe src={SITE_CONFIG.PRODUCT_VIDEO_URL} title="typein product video" allowFullScreen /></div></div></section> : null}

      <section className="site-container pricing-teaser"><div><p className="site-eyebrow">Simple pricing</p><h2>Start free. Decide after a month.</h2><p>Planned self-serve pricing: {SITE_CONFIG.PRICING.trialDays} days free, no card needed, then ₹{SITE_CONFIG.PRICING.monthlyInr.toLocaleString("en-IN")} per month. Self-serve signup is coming soon.</p></div><Link className="site-button site-button-light" href="/pricing">Explore pricing <ArrowRight aria-hidden="true" size={18} /></Link></section>

      <section className="site-section"><div className="site-container faq-layout"><div><p className="site-eyebrow">Good to know</p><h2>Questions before you join?</h2></div><div className="faq-list">{questions.map((item) => <details key={item.question}><summary>{item.question}<span aria-hidden="true">+</span></summary><p>{item.answer}</p></details>)}</div></div></section>

      <section className="site-section early-access-section" id="early-access"><div className="site-container early-access-layout"><div><p className="site-eyebrow">Early access</p><h2>Make room for easier bookings.</h2><p>Leave your details and typein will contact you about early access. Self-serve signup is coming soon.</p><span className="early-access-aside"><MessageCircle aria-hidden="true" size={18} /> Updates arrive on WhatsApp</span></div><EarlyAccessCTA /></div></section>
    </PublicShell>
  );
}
