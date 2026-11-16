import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { Suspense } from "react";

import StepProgress from "@/components/check/StepProgress";
import WarmUp from "@/components/check/WarmUp";

export const metadata: Metadata = {
  title: "Is a home battery worth it for you?",
  description:
    "Find out whether a home battery makes financial sense for your home, and when it pays back. Free, independent, and your data is never stored.",
  // Not indexed until it replaces the classic calculator (task 2.11).
  robots: { index: false, follow: false },
};

export default function CheckLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#0a1628] font-sans text-white">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-[#f97316] focus:px-4 focus:py-2 focus:font-semibold focus:text-[#0a1628]"
      >
        Skip to main content
      </a>
      <WarmUp />
      <header className="border-b border-slate-800">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-4 sm:px-6">
          <Link href="/" aria-label="BatterySizer home" className="rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white">
            <Image src="/batterysizer-logo.png" alt="BatterySizer" width={180} height={42} priority />
          </Link>
          <Link
            href="/calculator"
            className="text-sm text-slate-300 underline-offset-4 hover:text-white hover:underline"
          >
            Classic calculator
          </Link>
        </div>
      </header>

      <main id="main" className="mx-auto max-w-3xl px-4 py-8 sm:px-6 sm:py-12">
        <Suspense fallback={<div className="mb-8 h-12" aria-hidden="true" />}>
          <StepProgress />
        </Suspense>
        {children}
      </main>

      <footer className="mx-auto max-w-3xl px-4 pb-10 text-sm text-slate-400 sm:px-6">
        <p>
          Free and independent. Your usage data is used only to work out your answer and is never stored.
          Figures are estimates, not financial advice.
        </p>
      </footer>
    </div>
  );
}
