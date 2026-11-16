import Link from "next/link";
import { Suspense } from "react";

import BackLink from "@/components/check/BackLink";

/** Placeholder: step 3, check your details, is built in task 2.6. */
export default function CheckConfirm() {
  return (
    <section aria-labelledby="confirm-heading">
      <h1 id="confirm-heading" className="mb-4 text-3xl font-bold tracking-tight">Check your details</h1>
      <p className="mb-6 text-lg text-slate-300">
        This step is still being built. Until it&apos;s ready, please use the classic calculator.
      </p>
      <Link
        href="/calculator"
        className="mb-8 inline-block rounded-full bg-[#f97316] px-6 py-3 font-semibold text-[#0a1628] hover:bg-[#fb8a3c]"
      >
        Go to the classic calculator
      </Link>
      <p>
        <Suspense>
          <BackLink href="/check/usage">Back to your usage</BackLink>
        </Suspense>
      </p>
    </section>
  );
}
