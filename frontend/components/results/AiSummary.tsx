"use client";

import { useEffect, useState } from "react";

import { type AssessResponse, summarise } from "@/lib/api";

type State = { kind: "loading" } | { kind: "done"; text: string } | { kind: "none" };

/**
 * A short summary in plain English, written by AI from the figures on the page (task 2.9).
 * Clearly labelled; if it can't be written for any reason, it's simply left out.
 */
export default function AiSummary({ data }: { data: AssessResponse }) {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const ctrl = new AbortController();
    summarise(data, ctrl.signal)
      .then((r) => setState(r.summary.trim() ? { kind: "done", text: r.summary.trim() } : { kind: "none" }))
      .catch(() => { if (!ctrl.signal.aborted) setState({ kind: "none" }); });
    return () => ctrl.abort();
  }, [data]);

  if (state.kind === "none") return null;
  return (
    <section aria-labelledby="ai-summary-heading" aria-busy={state.kind === "loading"}
      className="rounded-xl border border-dashed border-slate-500 p-5 print:hidden">
      <h2 id="ai-summary-heading" className="mb-2 flex flex-wrap items-center gap-2 text-sm font-semibold text-slate-200">
        In a nutshell
        <span className="rounded-full border border-slate-500 px-2 py-0.5 text-xs font-normal text-slate-300">Written by AI</span>
      </h2>
      {state.kind === "loading" ? (
        <p className="text-slate-300">Writing a short summary…</p>
      ) : (
        <>
          <p className="text-slate-100">{state.text}</p>
          <p className="mt-2 text-xs text-slate-400">
            Written by AI (Claude) from the figures on this page. It can make mistakes, so rely on the numbers below.
          </p>
        </>
      )}
    </section>
  );
}
