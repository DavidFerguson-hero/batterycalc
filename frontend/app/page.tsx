import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Free Solar & Battery Calculator for UK Homeowners — BatterySizer",
  description:
    "Find out whether solar panels, a home battery, or both are right for your home. Upload your smart meter data and get a personalised recommendation with payback period, annual savings, and AI-powered explanation — free and instant.",
  alternates: {
    canonical: "https://www.batterysizer.co.uk",
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "WebApplication",
  name: "BatterySizer",
  url: "https://www.batterysizer.co.uk",
  description:
    "Free UK solar and battery storage calculator for homeowners. Analyses your actual half-hourly energy consumption, models solar, battery, and combined scenarios across all major UK time-of-use tariffs, and delivers a personalised recommendation with full payback and ROI calculation.",
  applicationCategory: "UtilityApplication",
  operatingSystem: "Web",
  offers: {
    "@type": "Offer",
    price: "0",
    priceCurrency: "GBP",
  },
  featureList: [
    "Half-hourly smart meter data analysis",
    "Solar panel and home battery scenario modelling",
    "Personalised recommendations for existing solar or battery owners",
    "UK tariff comparison (Octopus Go, Economy 7, Intelligent Go and more)",
    "Payback period and 10-year ROI projection",
    "AI-powered plain-English recommendation",
  ],
  audience: {
    "@type": "Audience",
    audienceType: "UK homeowners considering solar panels or home battery storage",
  },
};

export default function Home() {
  return (
    <div className="min-h-screen bg-[#0a1628] text-white font-sans">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      {/* Header */}
      <header>
        <nav className="flex items-center justify-between px-6 py-5 max-w-6xl mx-auto" aria-label="Main navigation">
          <Link href="/" aria-label="BatterySizer home">
            <Image
              src="/batterysizer-logo.png"
              alt="BatterySizer — Solar and Home Battery Calculator"
              width={260}
              height={60}
              priority
            />
          </Link>
          <Link
            href="/calculator"
            className="hidden sm:inline-flex items-center gap-2 bg-[#f97316] hover:bg-[#ea6c0a] text-white font-semibold px-5 py-2.5 rounded-full transition-colors text-sm"
          >
            Get My Recommendation
          </Link>
        </nav>
      </header>

      <main>
        {/* Hero */}
        <section aria-labelledby="hero-heading" className="max-w-6xl mx-auto px-6 pt-20 pb-28 text-center">
          <h1 id="hero-heading" className="text-5xl sm:text-6xl font-bold leading-tight tracking-tight mb-6">
            Solar panels, a home battery,<br />
            <span className="text-[#f97316]">or both — what&apos;s right for your home?</span>
          </h1>
          <p className="text-lg sm:text-xl text-slate-300 max-w-2xl mx-auto mb-10 leading-relaxed">
            Upload your smart meter data and get a personalised recommendation
            in seconds — with real savings figures, a clear payback timeline,
            and an AI-powered explanation of why. Completely free, no sign-up needed.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/calculator"
              className="inline-flex items-center justify-center gap-2 bg-[#f97316] hover:bg-[#ea6c0a] text-white font-semibold px-8 py-4 rounded-full transition-colors text-lg"
            >
              Get My Free Recommendation
              <svg className="w-5 h-5" aria-hidden="true" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </Link>
            <a
              href="#how-it-works"
              className="inline-flex items-center justify-center gap-2 border border-slate-500 hover:border-slate-300 text-slate-300 hover:text-white font-semibold px-8 py-4 rounded-full transition-colors text-lg"
            >
              See how it works
            </a>
          </div>
        </section>

        {/* Social proof strip */}
        <aside aria-label="Key features" className="border-y border-slate-700/50 bg-slate-800/30 py-5">
          <ul className="max-w-4xl mx-auto px-6 flex flex-wrap justify-center gap-8 text-slate-400 text-sm font-medium list-none">
            <li>✓ No sign-up required</li>
            <li>✓ Works with your actual usage data</li>
            <li>✓ Solar, battery &amp; combined scenarios</li>
            <li>✓ AI-powered plain-English explanation</li>
          </ul>
        </aside>

        {/* How it works */}
        <section id="how-it-works" aria-labelledby="how-it-works-heading" className="max-w-6xl mx-auto px-6 py-28">
          <h2 id="how-it-works-heading" className="text-3xl sm:text-4xl font-bold text-center mb-4">How it works</h2>
          <p className="text-slate-400 text-center mb-16 text-lg">Three steps to your personalised recommendation</p>

          <div className="grid sm:grid-cols-3 gap-10">
            {[
              {
                step: "01",
                icon: (
                  <svg className="w-8 h-8 text-[#f97316]" aria-hidden="true" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                  </svg>
                ),
                title: "Tell us about your home",
                desc: "Enter your postcode and import your smart meter data — or just enter your annual usage. Tell us if you already have solar panels or a battery.",
              },
              {
                step: "02",
                icon: (
                  <svg className="w-8 h-8 text-[#f97316]" aria-hidden="true" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                  </svg>
                ),
                title: "We model your options",
                desc: "Our engine simulates solar, battery, and combined scenarios against your real consumption and the major UK time-of-use tariffs.",
              },
              {
                step: "03",
                icon: (
                  <svg className="w-8 h-8 text-[#f97316]" aria-hidden="true" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                ),
                title: "Get a clear recommendation",
                desc: "See your best option, projected annual savings, payback period, and a plain-English AI explanation of why it suits your home.",
              },
            ].map(({ step, icon, title, desc }) => (
              <article key={step} className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-8">
                <div className="flex items-center gap-3 mb-5" aria-hidden="true">
                  <span className="text-xs font-bold text-[#f97316] tracking-widest">{step}</span>
                  {icon}
                </div>
                <h3 className="text-xl font-semibold mb-3">{title}</h3>
                <p className="text-slate-400 leading-relaxed">{desc}</p>
              </article>
            ))}
          </div>
        </section>

        {/* Features */}
        <section aria-labelledby="features-heading" className="bg-slate-800/30 border-t border-slate-700/50 py-28">
          <div className="max-w-6xl mx-auto px-6">
            <h2 id="features-heading" className="text-3xl sm:text-4xl font-bold text-center mb-4">
              Built for UK homeowners
            </h2>
            <p className="text-slate-400 text-center mb-16 text-lg max-w-2xl mx-auto">
              Whether you&apos;re starting from scratch or already have solar or a battery, BatterySizer works out the numbers for your specific situation.
            </p>

            <div className="grid md:grid-cols-2 gap-6">
              {[
                {
                  icon: (
                    <svg className="w-6 h-6 text-[#f97316]" aria-hidden="true" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12l8.954-8.955a1.126 1.126 0 011.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" />
                    </svg>
                  ),
                  title: "Personalised to your home",
                  desc: "Upload your half-hourly smart meter data or enter your annual usage. We model your real consumption patterns, not UK averages.",
                },
                {
                  icon: (
                    <svg className="w-6 h-6 text-[#f97316]" aria-hidden="true" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
                    </svg>
                  ),
                  title: "Already have solar or a battery?",
                  desc: "Tell us what you already have and we'll show you the incremental value of adding the missing piece — with costs and savings calculated on top of your existing setup.",
                },
                {
                  icon: (
                    <svg className="w-6 h-6 text-[#f97316]" aria-hidden="true" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                    </svg>
                  ),
                  title: "All major UK tariffs compared",
                  desc: "We run your data against Octopus Go, Intelligent Go, Economy 7, and more — so you see which tariff and system combination maximises your savings.",
                },
                {
                  icon: (
                    <svg className="w-6 h-6 text-[#f97316]" aria-hidden="true" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                    </svg>
                  ),
                  title: "AI-powered plain-English explanation",
                  desc: "Get a clear, jargon-free explanation of your recommendation — why it suits your consumption profile, which tariff to pair it with, and what to expect.",
                },
                {
                  icon: (
                    <svg className="w-6 h-6 text-[#f97316]" aria-hidden="true" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
                    </svg>
                  ),
                  title: "Clear payback and ROI",
                  desc: "See your break-even point, 10-year return on investment, and annual saving in pounds — so you can make a confident, informed buying decision.",
                },
                {
                  icon: (
                    <svg className="w-6 h-6 text-[#f97316]" aria-hidden="true" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
                    </svg>
                  ),
                  title: "Carbon savings included",
                  desc: "We factor in UK grid carbon intensity so you can see the environmental impact of your system — in kg CO₂ saved and trees equivalent.",
                },
              ].map(({ icon, title, desc }) => (
                <article key={title} className="bg-[#0a1628] border border-slate-700/50 rounded-2xl p-7 flex gap-5">
                  <div className="mt-0.5 shrink-0 w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center">
                    {icon}
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-white mb-1.5">{title}</h3>
                    <p className="text-slate-400 text-sm leading-relaxed">{desc}</p>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section aria-labelledby="cta-heading" className="max-w-3xl mx-auto px-6 py-28 text-center">
          <h2 id="cta-heading" className="text-4xl sm:text-5xl font-bold mb-6">
            Ready to find your best option?
          </h2>
          <p className="text-slate-400 text-lg mb-10">
            Takes less than 2 minutes. Free, instant, and no sign-up required.
          </p>
          <Link
            href="/calculator"
            className="inline-flex items-center justify-center gap-2 bg-[#f97316] hover:bg-[#ea6c0a] text-white font-bold px-10 py-5 rounded-full transition-colors text-xl"
          >
            Get My Free Recommendation
            <svg className="w-5 h-5" aria-hidden="true" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </Link>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-700/50 bg-[#0a1628] py-8">
        <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-slate-500 text-sm">
          <Link href="/" aria-label="BatterySizer home">
            <Image
              src="/batterysizer-logo.png"
              alt="BatterySizer"
              width={160}
              height={36}
              className="opacity-40"
            />
          </Link>
          <p>© {new Date().getFullYear()} BatterySizer. All rights reserved.</p>
          <nav aria-label="Footer navigation">
            <ul className="flex gap-5 text-xs list-none">
              <li><Link href="/calculator" className="hover:text-slate-300 transition-colors">How we calculate</Link></li>
              <li><Link href="/calculator" className="hover:text-slate-300 transition-colors">Legal disclaimer</Link></li>
            </ul>
          </nav>
        </div>
      </footer>
    </div>
  );
}
