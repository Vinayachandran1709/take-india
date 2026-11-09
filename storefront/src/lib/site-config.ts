import type { Metadata } from "next";

export const SITE_CONFIG = {
  TRADE_NAME: "typein",
  LEGAL_NAME: "typein",
  OPERATOR_NAME: "Vinayachandran",
  EMAIL: "hello@typein.co",
  PHONE: "+91 86109 58827",
  SITE_URL: "https://typein.co",
  PRICING: { trialDays: 30, monthlyInr: 1499, noCardNeeded: true },
  CANCELLATION: "Cancel any time from the dashboard or by email. No further subscription charges after cancelling.",
  REFUND_RULE: "Subscription fees are not refundable, except where typein charged you by mistake, such as a duplicate charge. That charge is refunded to the original payment method.",
  DATA_RETENTION: "When a trial ends or a subscription lapses, the account is locked and data is kept for 60 days so the owner can resume. After that it is deleted, except records that must be kept by law. Owners can request earlier deletion by email. Residual copies in backups are removed on a rolling basis.",
  GOVERNING_LAW: "Laws of India",
  SUPPORT: "Support is available by email and phone. Replies typically arrive within 2 working days.",
  EFFECTIVE_DATE: "9 November 2026",
  SIGNUP_ENABLED: false,
  SIGNUP_URL: "https://app.typein.co/signup",
  PRODUCT_VIDEO_URL: "",
} as const;

export const PUBLIC_PATHS = ["/", "/pricing", "/terms", "/privacy", "/refund-policy", "/contact"] as const;

export function publicMetadata(title: string, description: string, path: string): Metadata {
  const url = `${SITE_CONFIG.SITE_URL}${path === "/" ? "" : path}`;
  return {
    title: `${title} | ${SITE_CONFIG.TRADE_NAME}`,
    description,
    alternates: { canonical: url },
    openGraph: {
      title: `${title} | ${SITE_CONFIG.TRADE_NAME}`,
      description,
      siteName: SITE_CONFIG.TRADE_NAME,
      url,
      type: "website",
    },
  };
}
