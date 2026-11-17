/**
 * Visitor counts with Vercel Web Analytics (task 3.3): cookieless, no personal data.
 *
 * The funnel: landing page → route chosen → result → share. On Vercel's free plan only page
 * views are counted; that covers the first three steps by page (/, /check/usage/estimate or
 * /check/usage/upload, /check/results). The named events below also need Vercel's paid plan
 * to show up; until then they're simply not counted.
 *
 * Every address is cut back to its path before it's sent: the query string holds the
 * homeowner's answers (yearly use, home type, tariff…), which we don't collect.
 */
import { track } from "@vercel/analytics";

type PathOnly = { url: string };

/** "https://x/check/results?kwh=3500#top" → "https://x/check/results". Anything unparseable is dropped. */
export function withoutQuery<T extends PathOnly>(event: T): T | null {
  try {
    const u = new URL(event.url);
    return { ...event, url: `${u.origin}${u.pathname}` };
  } catch {
    return null;
  }
}

type FunnelEvent =
  | { name: "Route chosen"; data: { route: "estimate" | "upload" } }
  | { name: "Result shown"; data: { route: "estimate" | "upload"; verdict: string } }
  | { name: "Share"; data: { method: "link" | "print"; route: "estimate" | "upload" } };

/** Count a funnel step. Never throws: analytics must not break the page. */
export function countStep<N extends FunnelEvent["name"]>(name: N, data: Extract<FunnelEvent, { name: N }>["data"]): void {
  try {
    track(name, data);
  } catch {
    /* ignore */
  }
}
