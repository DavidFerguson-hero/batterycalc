"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { ApiError, type AssessResponse, assess } from "@/lib/api";
import { ukDate } from "@/lib/format";
import { buildAssessRequest } from "@/lib/request";
import { parseJourney, stepHref } from "@/lib/journey";
import { useUploads } from "@/lib/uploads";

import { ConfidenceBadge, HeadlineNumbers, SavingBreakdown, VerdictCard } from "./AnswerSections";
import { Assumptions, ContextPanel, NextSteps, SizeComparison, TariffCheck } from "./ExploreSections";
import WhatIfs from "./WhatIfs";

// The chart library only runs in the browser.
const BreakEvenChart = dynamic(() => import("./BreakEvenChart"), {
  ssr: false,
  loading: () => <div className="h-72 rounded-xl border border-slate-700 bg-[#0f1f38]" aria-hidden="true" />,
});
const DayInLife = dynamic(() => import("./DayInLife"), {
  ssr: false,
  loading: () => <div className="h-72 rounded-xl border border-slate-700 bg-[#0f1f38]" aria-hidden="true" />,
});

type State =
  | { kind: "loading"; key: string; slow: boolean }
  | { kind: "done"; key: string; data: AssessResponse }
  | { kind: "error"; key: string; message: string };

export default function ResultsView() {
  const query = useSearchParams().toString();
  const { files, check } = useUploads();
  const hasFiles = files.length > 0 && !!check?.combined;
  const built = buildAssessRequest(query, hasFiles);
  const requestKey = built.request ? JSON.stringify(built.request) + `|${files.length}` : "";

  const [state, setState] = useState<State | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!built.request) return;
    const ctrl = new AbortController();
    const key = requestKey;
    const slow = setTimeout(() => setState((s) => (s && s.kind === "loading" && s.key === key ? { ...s, slow: true } : s)), 5000);
    Promise.resolve().then(() => setState({ kind: "loading", key, slow: false }));
    assess(built.request, built.request.usage.route === "upload" ? files : [], ctrl.signal)
      .then((data) => setState({ kind: "done", key, data }))
      .catch((e) => {
        if (ctrl.signal.aborted) return;
        setState({ kind: "error", key, message: e instanceof ApiError ? e.message : "Something went wrong working out your answer." });
      })
      .finally(() => clearTimeout(slow));
    return () => { ctrl.abort(); clearTimeout(slow); };
    // requestKey captures everything the request depends on.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestKey, attempt]);

  if (!built.request) {
    return (
      <div className="rounded-xl border border-slate-700 bg-[#0f1f38] p-5">
        <p className="mb-3 text-slate-100">
          {built.missing.includes("files")
            ? "Your usage file isn't loaded any more (we don't keep files once the page is closed or reloaded)."
            : "We need a few more details before we can work out your answer."}
        </p>
        <Link href={stepHref("/check/confirm", query)} className="text-white underline underline-offset-4">
          Go back to check your details
        </Link>
      </div>
    );
  }

  const current = state && state.key === requestKey ? state : null;

  if (!current || current.kind === "loading") {
    return (
      <div role="status" aria-live="polite" className="rounded-xl border border-slate-700 bg-[#0f1f38] p-6">
        <p className="text-lg text-white">Working out your answer…</p>
        <p className="mt-2 text-sm text-slate-300">
          {current?.slow
            ? "Waking up the calculator. The first answer of the day can take up to a minute."
            : "We're modelling a year of your electricity use with and without a battery, on every tariff."}
        </p>
      </div>
    );
  }

  if (current.kind === "error") {
    return (
      <div role="alert" className="rounded-xl border border-[#fca5a5] bg-[#fca5a5]/10 p-5">
        <p className="mb-3 text-slate-100">{current.message}</p>
        <button type="button" onClick={() => setAttempt((a) => a + 1)}
          className="rounded-full bg-[#f97316] px-6 py-2 font-semibold text-[#0a1628] hover:bg-[#fb8a3c] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white">
          Try again
        </button>
      </div>
    );
  }

  const data = current.data;
  const home = parseJourney(query).home;
  return (
    <div className="space-y-10">
      <VerdictCard data={data} />
      <HeadlineNumbers data={data} />
      <ConfidenceBadge data={data} query={query} />
      <BreakEvenChart data={data} />
      <SavingBreakdown data={data} />
      <SizeComparison data={data} />
      <TariffCheck data={data} />
      <WhatIfs key={requestKey} data={data} base={built.request} files={files} ev={home.ev} heatPump={home.heat_pump} />
      <DayInLife data={data} />
      <ContextPanel data={data} solar={home.solar} />
      <NextSteps data={data} />
      <Assumptions data={data} solar={home.solar} />
      <p className="text-sm text-slate-400">
        Prices as of {ukDate(data.assumptions.costs_as_of)}; tariffs checked {ukDate(data.assumptions.tariffs_checked)}.
        Figures are estimates, not financial advice.{" "}
        <Link href={stepHref("/check/confirm", query)} className="underline underline-offset-4 hover:text-white">Change your details</Link>
      </p>
    </div>
  );
}
