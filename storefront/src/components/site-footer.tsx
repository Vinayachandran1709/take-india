import Link from "next/link";

import { SITE_CONFIG } from "@/lib/site-config";

const footerLinks = [
  { label: "Pricing", href: "/pricing" },
  { label: "Terms", href: "/terms" },
  { label: "Privacy", href: "/privacy" },
  { label: "Refund & Cancellation", href: "/refund-policy" },
  { label: "Contact", href: "/contact" },
];

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-container site-footer-inner">
        <div>
          <Link href="/" className="site-wordmark">{SITE_CONFIG.TRADE_NAME}<span className="site-wordmark-dot">.</span></Link>
          <p>A booking page for service businesses.</p>
          <div className="site-footer-contact"><a href={`mailto:${SITE_CONFIG.EMAIL}`}>{SITE_CONFIG.EMAIL}</a><a href={`tel:${SITE_CONFIG.PHONE.replace(/\s/g, "")}`}>{SITE_CONFIG.PHONE}</a></div>
        </div>
        <nav aria-label="Footer navigation">
          {footerLinks.map((link) => <Link key={link.href} href={link.href}>{link.label}</Link>)}
        </nav>
      </div>
      <div className="site-container site-footer-bottom">
        <span>© {new Date().getFullYear()} {SITE_CONFIG.TRADE_NAME}</span>
        <span>{SITE_CONFIG.LEGAL_NAME} · Individually operated</span>
      </div>
    </footer>
  );
}
