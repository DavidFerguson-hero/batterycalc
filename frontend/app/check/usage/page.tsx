import { Suspense } from "react";

import RouteChoice from "@/components/check/RouteChoice";

/** Step 2 — choose a route: real usage data, or a quick estimate (story H2). */
export default function CheckUsage() {
  return (
    <section aria-labelledby="usage-heading">
      <h1 id="usage-heading" className="mb-4 text-3xl font-bold tracking-tight sm:text-4xl">
        How much electricity does your home use?
      </h1>
      <p className="mb-8 text-lg leading-relaxed text-slate-300">
        A battery&apos;s value depends on when you use electricity, not just how much. Choose how you&apos;d like to tell us.
      </p>
      <Suspense fallback={<p className="text-slate-300">Loading…</p>}>
        <RouteChoice />
      </Suspense>
    </section>
  );
}
