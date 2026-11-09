import { SITE_CONFIG } from "@/lib/site-config";
import { PublicShell } from "./public-shell";

export function LegalPage({
  eyebrow,
  title,
  intro,
  children,
}: {
  eyebrow: string;
  title: string;
  intro: string;
  children: React.ReactNode;
}) {
  return (
    <PublicShell>
      <div className="site-container legal-page">
        <p className="site-eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="legal-intro">{intro}</p>
        <p className="legal-updated">Last updated: {SITE_CONFIG.EFFECTIVE_DATE}</p>
        <div className="legal-content">{children}</div>
      </div>
    </PublicShell>
  );
}
