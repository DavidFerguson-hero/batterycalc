import type { Metadata } from "next";
import Link from "next/link";

// The old calculator, kept for a month after the switch to /check (task 2.11).
// Remove this page and public/calculator.html after 16 December 2026.
export const metadata: Metadata = {
  title: "Classic calculator",
  description: "The previous version of the BatterySizer calculator, available until mid-December 2026.",
  robots: { index: false, follow: false },
};

export default function CalculatorClassicPage() {
  return (
    <div className="flex h-screen flex-col bg-[#0a1628]">
      <p className="border-b border-slate-800 px-4 py-2 text-center text-sm text-slate-200">
        This is the old calculator. It will be removed after 16 December 2026.{" "}
        <Link href="/check" className="font-semibold text-white underline underline-offset-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white">
          Try the new check
        </Link>
      </p>
      <iframe
        src="/calculator.html"
        className="block w-full flex-1 border-0"
        title="BatterySizer classic calculator"
      />
    </div>
  );
}
