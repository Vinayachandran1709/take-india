import type { Storefront } from "./types";

export const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export async function getStorefront(slug: string): Promise<Storefront | null> {
  const response = await fetch(`${apiBaseUrl}/storefront/${encodeURIComponent(slug)}`, {
    cache: "no-store",
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error("The storefront is temporarily unavailable.");
  return response.json() as Promise<Storefront>;
}

export function rupees(value: string): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number(value));
}
