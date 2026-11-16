import { Suspense } from "react";

import Term from "@/components/Term";
import HomeSetupForm from "@/components/check/HomeSetupForm";

/** Step 1 — your home setup (stories H1, H6). */
export default function CheckHomeSetup() {
  return (
    <section aria-labelledby="check-heading">
      <h1 id="check-heading" className="mb-4 text-3xl font-bold tracking-tight sm:text-4xl">
        Is a home battery worth it for you?
      </h1>
      <p className="mb-8 text-lg leading-relaxed text-slate-300">
        We&apos;ll work out whether a battery makes financial sense for your home, and when it would{" "}
        <Term k="payback">pay back</Term>. First, tell us what your home has now, or what you&apos;re planning.
      </p>
      <Suspense fallback={<p className="text-slate-300">Loading…</p>}>
        <HomeSetupForm />
      </Suspense>
    </section>
  );
}
