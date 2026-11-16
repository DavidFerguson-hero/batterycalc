import { Suspense } from "react";

import ConfirmStep from "@/components/check/ConfirmStep";

/** Step 3 — check your details: summary of the answers and the current tariff (story H5). */
export default function CheckConfirm() {
  return (
    <section aria-labelledby="confirm-heading">
      <h1 id="confirm-heading" className="mb-4 text-3xl font-bold tracking-tight sm:text-4xl">Check your details</h1>
      <p className="mb-8 text-lg leading-relaxed text-slate-300">
        Here&apos;s everything we&apos;ll use to work out your answer. Change anything that&apos;s not right.
      </p>
      <Suspense fallback={<p className="text-slate-300">Loading…</p>}>
        <ConfirmStep />
      </Suspense>
    </section>
  );
}
