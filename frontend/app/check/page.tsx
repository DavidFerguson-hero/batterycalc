import Term from "@/components/Term";

/**
 * Step 1: your home setup. The full step (pick what you have now and what you're
 * planning) is built in task 2.2; this is the placeholder for the foundations (2.1).
 */
export default function CheckStart() {
  return (
    <section aria-labelledby="check-heading">
      <h1 id="check-heading" className="mb-4 text-3xl font-bold tracking-tight sm:text-4xl">
        Is a home battery worth it for you?
      </h1>
      <p className="mb-4 text-lg leading-relaxed text-slate-300">
        We&apos;ll work out whether a battery makes financial sense for your home, and when it would{" "}
        <Term k="payback">pay back</Term>. It takes about two minutes with a quick estimate from your{" "}
        <Term k="epc" />, or a little longer with your smart meter&apos;s <Term k="half_hourly" />.
      </p>
      <p className="text-slate-300">
        A battery saves most on a <Term k="time_of_use" />, so we&apos;ll compare your current <Term k="tariff" /> with
        the best ones for your home, measured in <Term k="kwh" />s and £ a year.
      </p>
      <p className="mt-8 rounded-lg border border-slate-700 bg-[#13233d] p-4 text-sm text-slate-300">
        This new version of the calculator is being built. Until it&apos;s ready, please use the{" "}
        <a href="/calculator" className="text-white underline underline-offset-4">
          classic calculator
        </a>
        .
      </p>
    </section>
  );
}
