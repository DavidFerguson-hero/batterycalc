import { Suspense } from "react";

import ResultsView from "@/components/results/ResultsView";

/** Step 4 — your answer (stories H7–H22). */
export default function CheckResults() {
  return (
    <section aria-labelledby="results-heading">
      <h1 id="results-heading" className="mb-6 text-3xl font-bold tracking-tight sm:text-4xl">
        Is a battery worth it for your home?
      </h1>
      <Suspense fallback={<p className="text-slate-300">Loading…</p>}>
        <ResultsView />
      </Suspense>
    </section>
  );
}
