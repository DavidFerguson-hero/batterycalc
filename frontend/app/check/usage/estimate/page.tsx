import { Suspense } from "react";

import BackLink from "@/components/check/BackLink";
import EstimateStep from "@/components/check/EstimateStep";

/** Route B — quick estimate from the EPC register and a couple of questions (story H3). */
export default function CheckEstimate() {
  return (
    <section aria-labelledby="estimate-heading">
      <h1 id="estimate-heading" className="mb-4 text-3xl font-bold tracking-tight sm:text-4xl">Quick estimate</h1>
      <p className="mb-8 text-lg leading-relaxed text-slate-300">
        We&apos;ll estimate how much electricity your home uses from its details. It takes about two minutes.
      </p>
      <Suspense fallback={<p className="text-slate-300">Loading…</p>}>
        <EstimateStep />
      </Suspense>
      <p className="mt-10">
        <Suspense>
          <BackLink href="/check/usage">Choose a different way</BackLink>
        </Suspense>
      </p>
    </section>
  );
}
