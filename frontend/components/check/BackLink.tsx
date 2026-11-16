"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { stepHref } from "@/lib/journey";

/** "← Back to …" that keeps the answers so far. */
export default function BackLink({ href, children }: { href: string; children: React.ReactNode }) {
  const query = useSearchParams().toString();
  return (
    <Link href={stepHref(href, query)} className="text-slate-300 underline-offset-4 hover:text-white hover:underline">
      <span aria-hidden="true">←</span> {children}
    </Link>
  );
}
