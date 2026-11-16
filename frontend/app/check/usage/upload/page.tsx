import Link from "next/link";
import { Suspense } from "react";

import BackLink from "@/components/check/BackLink";

/** Placeholder: built in task 2.4. */
export default function CheckUpload() {
  return (
    <section aria-labelledby="upload-heading">
      <h1 id="upload-heading" className="mb-4 text-3xl font-bold tracking-tight">Upload your usage data</h1>
      <p className="mb-6 text-lg text-slate-300">
        This step, using your half-hourly smart meter data, is still being built. Until it&apos;s ready, please use the classic calculator.
      </p>
      <Link
        href="/calculator"
        className="mb-8 inline-block rounded-full bg-[#f97316] px-6 py-3 font-semibold text-[#0a1628] hover:bg-[#fb8a3c]"
      >
        Go to the classic calculator
      </Link>
      <p>
        <Suspense>
          <BackLink href="/check/usage">Choose a different way</BackLink>
        </Suspense>
      </p>
    </section>
  );
}
