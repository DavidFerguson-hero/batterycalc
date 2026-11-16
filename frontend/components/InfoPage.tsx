import Image from "next/image";
import Link from "next/link";

import { FOOTER_LINKS } from "@/lib/site";

const focus = "rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white";

/** Footer links shared by every page (task 3.2). */
export function FooterLinks({ className = "" }: { className?: string }) {
  return (
    <nav aria-label="Footer navigation" className={className}>
      <ul className="flex list-none flex-wrap justify-center gap-x-5 gap-y-2 text-sm">
        {FOOTER_LINKS.map((l) => (
          <li key={l.href}>
            <Link href={l.href} className={`text-slate-400 underline-offset-4 hover:text-white hover:underline ${focus}`}>
              {l.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** Layout for the plain information pages: How we calculate, Privacy, Legal, Contact. */
export default function InfoPage({ title, intro, children }: { title: string; intro?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#0a1628] font-sans text-white">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-[#f97316] focus:px-4 focus:py-2 focus:font-semibold focus:text-[#0a1628]"
      >
        Skip to main content
      </a>
      <header className="border-b border-slate-800">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <Link href="/" aria-label="BatterySizer home" className={focus}>
            <Image src="/batterysizer-logo.png" alt="BatterySizer" width={180} height={42} priority />
          </Link>
          <Link
            href="/check"
            className="shrink-0 rounded-full bg-[#f97316] px-4 py-2 text-sm font-semibold text-[#0a1628] hover:bg-[#fb8a3c] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
          >
            Check your home
          </Link>
        </div>
      </header>

      <main
        id="main"
        className="mx-auto max-w-3xl px-4 py-10 sm:px-6 sm:py-14
          [&_a]:underline [&_a]:underline-offset-4 [&_a:focus-visible]:outline [&_a:focus-visible]:outline-2 [&_a:focus-visible]:outline-offset-2 [&_a:focus-visible]:outline-white [&_a]:rounded
          [&_h2]:mb-3 [&_h2]:mt-10 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:text-white
          [&_h3]:mb-2 [&_h3]:mt-6 [&_h3]:font-semibold [&_h3]:text-white
          [&_li]:mb-1.5 [&_ol]:mb-4 [&_ol]:list-decimal [&_ol]:pl-6 [&_p]:mb-4 [&_ul]:mb-4 [&_ul]:list-disc [&_ul]:pl-6
          [&_table]:mb-4 [&_table]:w-full [&_table]:text-sm [&_td]:border-t [&_td]:border-slate-700 [&_td]:py-2 [&_td]:pr-3 [&_td]:align-top
          [&_th]:py-2 [&_th]:pr-3 [&_th]:text-left [&_th]:font-semibold [&_th]:text-white
          leading-relaxed text-slate-200"
      >
        <h1 className="mb-4 text-3xl font-bold text-white sm:text-4xl">{title}</h1>
        {intro && <div className="mb-8 text-lg text-slate-300">{intro}</div>}
        {children}
      </main>

      <footer className="border-t border-slate-800 py-8">
        <div className="mx-auto flex max-w-3xl flex-col items-center gap-4 px-4 text-sm text-slate-400 sm:px-6">
          <FooterLinks />
          <p>© {new Date().getFullYear()} BatterySizer. Figures are estimates, not financial advice.</p>
        </div>
      </footer>
    </div>
  );
}
