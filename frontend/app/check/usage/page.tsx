import Link from "next/link";

/**
 * Step 2 — choose a route (usage data or quick estimate). Built in task 2.3;
 * this placeholder only lets step 1 be tried end to end.
 */
export default function CheckUsage() {
  return (
    <section aria-labelledby="usage-heading">
      <h1 id="usage-heading" className="mb-4 text-3xl font-bold tracking-tight">Your usage</h1>
      <p className="mb-6 text-lg text-slate-300">
        This step is still being built. Until the new calculator is ready, please use the classic one.
      </p>
      <Link
        href="/calculator"
        className="inline-block rounded-full bg-[#f97316] px-6 py-3 font-semibold text-[#0a1628] hover:bg-[#fb8a3c]"
      >
        Go to the classic calculator
      </Link>
    </section>
  );
}
