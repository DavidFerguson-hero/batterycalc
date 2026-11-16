import { Suspense } from "react";

import Term from "@/components/Term";
import BackLink from "@/components/check/BackLink";
import SupplierHowTo from "@/components/check/SupplierHowTo";
import UploadStep from "@/components/check/UploadStep";

/** Route A — upload half-hourly usage data (story H4). */
export default function CheckUpload() {
  return (
    <section aria-labelledby="upload-heading">
      <h1 id="upload-heading" className="mb-4 text-3xl font-bold tracking-tight sm:text-4xl">
        Upload your usage data
      </h1>
      <p className="mb-8 text-lg leading-relaxed text-slate-300">
        Your smart meter records how much electricity you use every half-hour. A year of that{" "}
        <Term k="half_hourly" /> shows exactly when you use power, which is what decides a battery&apos;s value.
      </p>

      <SupplierHowTo />

      <Suspense fallback={<p className="mt-8 text-slate-300">Loading…</p>}>
        <UploadStep />
      </Suspense>

      <p className="mt-10">
        <Suspense>
          <BackLink href="/check/usage">Choose a different way</BackLink>
        </Suspense>
      </p>
    </section>
  );
}
