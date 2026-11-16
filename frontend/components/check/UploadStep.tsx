"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import Term from "@/components/Term";
import { ApiError, checkUsage } from "@/lib/api";
import { stepHref } from "@/lib/journey";
import { addFiles, removeFile, setCheck, useUploads } from "@/lib/uploads";

const fmtDate = (iso?: string | null) =>
  iso ? new Date(`${iso}T12:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }) : "";

const fmtKwh = (n: number) => Math.round(n).toLocaleString("en-GB");

const CONFIDENCE: Record<string, string> = {
  high: "A full year (or nearly) of real readings, so your answer will be as accurate as we can make it.",
  medium: "A few months of real readings. We'll fill in the rest of the year using typical seasonal patterns.",
  low: "Only a short stretch of readings. We'll fill in most of the year using typical seasonal patterns, so treat the answer as a rough guide. More data will firm it up.",
};

export default function UploadStep() {
  const router = useRouter();
  const query = useSearchParams().toString();
  const { files, check } = useUploads();
  // Set only from async callbacks; "checking" is worked out from the files and the last result.
  const [failed, setFailed] = useState<{ files: File[]; message: string } | null>(null);
  const [slowFor, setSlowFor] = useState<File[] | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);

  // Check the files whenever they change (and haven't been checked yet).
  useEffect(() => {
    if (!files.length || check) return;
    const ctrl = new AbortController();
    const slow = setTimeout(() => setSlowFor(files), 5000);
    checkUsage(files, ctrl.signal)
      .then((res) => setCheck(files, res))
      .catch((e) => {
        if (ctrl.signal.aborted) return;
        setFailed({ files, message: e instanceof ApiError ? e.message : "Something went wrong checking your files." });
      })
      .finally(() => clearTimeout(slow));
    return () => { ctrl.abort(); clearTimeout(slow); };
  }, [files, check]);

  const errored = failed !== null && failed.files === files;
  const busy = files.length > 0 && !check && !errored;
  const status = busy ? (slowFor === files ? "slow" : "checking") : errored ? "error" : "idle";
  const error = errored ? failed.message : "";

  function onPicked(list: FileList | null) {
    if (list?.length) addFiles(Array.from(list));
    if (inputRef.current) inputRef.current.value = "";   // allow picking the same file again after removing it
  }

  const combined = check?.combined ?? null;
  const fileResult = (i: number) => check?.files[i];

  return (
    <section aria-labelledby="files-heading" className="mt-8">
      <h2 id="files-heading" className="mb-3 text-xl font-semibold">Add your file</h2>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); onPicked(e.dataTransfer.files); }}
        className={`relative rounded-xl border-2 border-dashed p-6 text-center transition-colors has-[input:focus-visible]:outline has-[input:focus-visible]:outline-2 has-[input:focus-visible]:outline-offset-4 has-[input:focus-visible]:outline-[#f97316] ${
          dragging ? "border-[#f97316] bg-[#f97316]/10" : "border-slate-500 bg-[#0f1f38]"
        }`}
      >
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          accept=".csv,text/csv"
          multiple
          onChange={(e) => onPicked(e.target.files)}
          className="sr-only"
        />
        <p className="mb-3 text-slate-300">Drag your CSV file here, or</p>
        <label
          htmlFor={inputId}
          className="inline-block cursor-pointer rounded-full bg-[#f97316] px-6 py-3 font-semibold text-[#0a1628] hover:bg-[#fb8a3c]"
        >
          Choose file{files.length ? "s to add" : ""}
        </label>
        <p className="mt-3 text-sm text-slate-400">
          A CSV export of your <Term k="half_hourly" />. You can add several files, for example one per month.
        </p>
      </div>

      {files.length > 0 && (
        <ul className="mt-4 space-y-2" aria-label="Your files">
          {files.map((f, i) => {
            const r = fileResult(i);
            return (
              <li key={`${f.name}-${f.lastModified}-${i}`} className="flex items-start justify-between gap-3 rounded-lg border border-slate-700 px-4 py-3">
                <div className="min-w-0">
                  <p className="truncate font-medium text-white">{f.name}</p>
                  {r && r.ok && (
                    <p className="text-sm text-slate-300">
                      ✓ {r.days_found} days{r.first_date ? `, ${fmtDate(r.first_date)} to ${fmtDate(r.last_date)}` : ""}
                    </p>
                  )}
                  {r && !r.ok && <p className="text-sm text-[#fca5a5]"><span aria-hidden="true">✗ </span>{r.error}</p>}
                </div>
                <button
                  type="button"
                  onClick={() => removeFile(i)}
                  className="shrink-0 rounded px-2 py-1 text-sm text-slate-300 underline-offset-4 hover:text-white hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#f97316]"
                >
                  Remove<span className="sr-only"> {f.name}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <div aria-live="polite" className="mt-4">
        {status === "checking" && <p className="text-slate-300">Checking your file{files.length > 1 ? "s" : ""}…</p>}
        {status === "slow" && (
          <p className="text-slate-300">Waking up the calculator. The first check can take up to a minute…</p>
        )}
        {status === "error" && <p role="alert" className="text-[#fca5a5]">{error}</p>}
        {combined && !busy && (
          <div className="rounded-xl border border-[#f97316] bg-[#f97316]/10 p-5">
            <h3 className="mb-2 text-lg font-semibold text-white">What we found</h3>
            {combined.has_dates ? (
              <p className="mb-2 text-slate-100">
                <strong>{combined.days_found} days</strong> of readings, from {fmtDate(combined.first_date)} to{" "}
                {fmtDate(combined.last_date)}: about <strong>{fmtKwh(combined.annual_kwh_estimate)} <Term k="kwh" /> a year</strong>.
              </p>
            ) : (
              <p className="mb-2 text-slate-100">
                <strong>{combined.days_found} days</strong> of readings, but without dates, so we can&apos;t check for
                gaps or seasons.
              </p>
            )}
            {(combined.missing_days_filled || combined.partial_days_filled) ? (
              <p className="mb-2 text-sm text-slate-300">
                We filled {combined.missing_days_filled ? `${combined.missing_days_filled} missing day${combined.missing_days_filled === 1 ? "" : "s"}` : ""}
                {combined.missing_days_filled && combined.partial_days_filled ? " and " : ""}
                {combined.partial_days_filled ? `gaps in ${combined.partial_days_filled} day${combined.partial_days_filled === 1 ? "" : "s"}` : ""}{" "}
                using similar days from your data.
              </p>
            ) : null}
            {combined.days_dropped_older_than_a_year ? (
              <p className="mb-2 text-sm text-slate-300">
                We&apos;ll use the most recent 12 months ({combined.days_dropped_older_than_a_year} older days left out).
              </p>
            ) : null}
            <p className="text-sm text-slate-300">{CONFIDENCE[combined.confidence] ?? ""}</p>
          </div>
        )}
      </div>

      <p className="mt-4 text-sm text-slate-400">
        Your files are read only to work out your answer. They&apos;re never stored, and they&apos;re forgotten when you close this page.
      </p>

      <div className="mt-6 flex justify-end">
        <button
          type="button"
          disabled={!combined || busy}
          onClick={() => router.push(stepHref("/check/confirm", query))}
          className="rounded-full bg-[#f97316] px-8 py-3 text-lg font-semibold text-[#0a1628] transition-colors hover:bg-[#fb8a3c] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-200"
        >
          Continue
        </button>
      </div>
      {!combined && !busy && (
        <p className="mt-2 text-right text-sm text-slate-400">Add a file we can read to continue.</p>
      )}
    </section>
  );
}
