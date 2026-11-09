import Link from "next/link";
import { ArrowUpRight, Menu } from "lucide-react";

import { SITE_CONFIG } from "@/lib/site-config";

const links = [
  { label: "Home", href: "/" },
  { label: "Pricing", href: "/pricing" },
  { label: "Contact", href: "/contact" },
];

export function SiteHeader() {
  return (
    <header className="site-header">
      <a className="site-skip-link" href="#main-content">Skip to content</a>
      <div className="site-container site-header-inner">
        <Link href="/" className="site-wordmark" aria-label="typein home">
          <span className="site-mark" aria-hidden="true">t<span>.</span></span>
          <span>{SITE_CONFIG.TRADE_NAME}</span>
        </Link>
        <nav className="site-desktop-nav" aria-label="Main navigation">
          {links.map((link) => <Link key={link.href} href={link.href}>{link.label}</Link>)}
        </nav>
        <Link className="site-header-cta" href={SITE_CONFIG.SIGNUP_ENABLED ? SITE_CONFIG.SIGNUP_URL : "/#early-access"}>
          {SITE_CONFIG.SIGNUP_ENABLED ? "Start 1 month free" : "Join early access"}
          <ArrowUpRight aria-hidden="true" size={16} />
        </Link>
        <details className="site-mobile-nav">
          <summary aria-label="Open navigation"><Menu aria-hidden="true" size={22} /></summary>
          <nav aria-label="Mobile navigation">
            {links.map((link) => <Link key={link.href} href={link.href}>{link.label}</Link>)}
            <Link href={SITE_CONFIG.SIGNUP_ENABLED ? SITE_CONFIG.SIGNUP_URL : "/#early-access"}>
              {SITE_CONFIG.SIGNUP_ENABLED ? "Start 1 month free" : "Join early access"}
            </Link>
          </nav>
        </details>
      </div>
    </header>
  );
}
