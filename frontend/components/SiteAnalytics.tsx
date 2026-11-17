"use client";

import { Analytics } from "@vercel/analytics/next";

import { withoutQuery } from "@/lib/analytics";

/** Vercel Web Analytics, sending paths only (see lib/analytics.ts). */
export default function SiteAnalytics() {
  return <Analytics beforeSend={withoutQuery} />;
}
