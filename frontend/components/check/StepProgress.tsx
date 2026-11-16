"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

/** The steps of the homeowner journey, in order. Inputs travel in the query string (H22). */
export const STEPS = [
  { path: "/check", label: "Your home" },
  { path: "/check/usage", label: "Your usage" },
  { path: "/check/confirm", label: "Check details" },
  { path: "/check/results", label: "Your answer" },
] as const;

function stepIndex(pathname: string): number {
  // Longest matching path wins, so /check/usage/upload counts as "Your usage".
  let best = 0;
  STEPS.forEach((s, i) => {
    if (pathname === s.path || pathname.startsWith(`${s.path}/`)) best = i;
  });
  return best;
}

/**
 * "Step 2 of 4 — Your usage", plus a row of numbered steps. Earlier steps are links
 * back (keeping the answers so far); later steps aren't reachable yet. The current
 * step is marked with aria-current and in words, never by colour alone.
 */
export default function StepProgress() {
  const pathname = usePathname();
  const query = useSearchParams().toString();
  const current = stepIndex(pathname);

  return (
    <nav aria-label="Progress" className="mb-8">
      <p className="mb-3 text-sm text-slate-300">
        Step {current + 1} of {STEPS.length} <span aria-hidden="true">·</span>{" "}
        <span className="font-semibold text-white">{STEPS[current].label}</span>
      </p>
      <ol className="grid grid-cols-4 gap-2">
        {STEPS.map((s, i) => {
          const state = i < current ? "done" : i === current ? "current" : "todo";
          const bar = {
            done: "bg-[#f97316]",
            current: "bg-[#f97316]",
            todo: "bg-slate-700",
          }[state];
          const content = (
            <>
              <span className={`mb-2 block h-1.5 rounded-full ${bar}`} aria-hidden="true" />
              <span className="flex items-center gap-1.5 text-xs sm:text-sm">
                <span
                  aria-hidden="true"
                  className={`inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[0.7rem] font-bold ${
                    state === "todo" ? "border border-slate-500 text-slate-300" : "bg-[#f97316] text-[#0a1628]"
                  }`}
                >
                  {state === "done" ? "✓" : i + 1}
                </span>
                <span className={`hidden sm:inline ${state === "todo" ? "text-slate-400" : "text-white"}`}>
                  {s.label}
                </span>
                <span className="sr-only">
                  {s.label} — {state === "done" ? "done" : state === "current" ? "current step" : "not started"}
                </span>
              </span>
            </>
          );
          return (
            <li key={s.path}>
              {state === "done" ? (
                <Link
                  href={query ? `${s.path}?${query}` : s.path}
                  className="block rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#f97316]"
                >
                  {content}
                </Link>
              ) : (
                <div aria-current={state === "current" ? "step" : undefined}>{content}</div>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
