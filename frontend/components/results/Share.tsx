"use client";

import { useState } from "react";

import { countStep } from "@/lib/analytics";
import { shareNote } from "@/lib/summary";

const primary =
  "rounded-full bg-[#f97316] px-5 py-2 font-semibold text-[#0a1628] hover:bg-[#fb8a3c] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white";
const secondary =
  "rounded-full border border-slate-400 px-5 py-2 font-semibold text-white hover:border-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white";

/** "Copy link" and "Save as PDF" (the browser's print dialog, which prints the one-page summary). */
export default function ShareBar({ route, compact = false }: { route: "estimate" | "upload"; compact?: boolean }) {
  const [status, setStatus] = useState("");
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setStatus("Link copied.");
      countStep("Share", { method: "link", route });
    } catch {
      setStatus("Couldn't copy. Copy the address from your browser's address bar instead.");
    }
  };
  return (
    <div className="print:hidden">
      {!compact && <p className="mb-3 text-sm text-slate-300">{shareNote(route)}</p>}
      <div className="flex flex-wrap gap-3">
        <button type="button" onClick={copy} className={primary}>Copy link</button>
        <button type="button" onClick={() => { countStep("Share", { method: "print", route }); window.print(); }} className={secondary}>Save as PDF or print</button>
      </div>
      <p role="status" className="mt-2 min-h-5 text-sm text-slate-300">{status}</p>
    </div>
  );
}
