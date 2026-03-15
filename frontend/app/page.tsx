import Image from "next/image";
import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen bg-[#0a1628] text-white font-sans">
      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-5 max-w-6xl mx-auto">
        <Image
          src="/batterysizer-logo.png"
          alt="BatterySizer"
          width={260}
          height={60}
          priority
        />
        <Link
          href="/calculator"
          className="hidden sm:inline-flex items-center gap-2 bg-[#f97316] hover:bg-[#ea6c0a] text-white font-semibold px-5 py-2.5 rounded-full transition-colors text-sm"
        >
          Get Started
        </Link>
      </nav>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 pt-20 pb-28 text-center">
        <h1 className="text-5xl sm:text-6xl font-bold leading-tight tracking-tight mb-6">
          Find the right battery size<br />
          <span className="text-[#f97316]">for your home.</span>
        </h1>
        <p className="text-lg sm:text-xl text-slate-300 max-w-2xl mx-auto mb-10 leading-relaxed">
          BatterySizer analyses your actual energy usage, compares tariffs, and
          tells you exactly what size home battery storage system will save you
          the most money — with a clear payback timeline.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            href="/calculator"
            className="inline-flex items-center justify-center gap-2 bg-[#f97316] hover:bg-[#ea6c0a] text-white font-semibold px-8 py-4 rounded-full transition-colors text-lg"
          >
            Calculate My Battery Size
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
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
      <div className="border-y border-slate-700/50 bg-slate-800/30 py-5">
        <div className="max-w-4xl mx-auto px-6 flex flex-wrap justify-center gap-8 text-slate-400 text-sm font-medium">
          <span>✓ No sign-up required</span>
          <span>✓ Upload your own usage data</span>
          <span>✓ UK tariffs supported</span>
          <span>✓ Instant results</span>
        </div>
      </div>

      {/* How it works */}
      <section id="how-it-works" className="max-w-6xl mx-auto px-6 py-28">
        <h2 className="text-3xl sm:text-4xl font-bold text-center mb-4">How it works</h2>
        <p className="text-slate-400 text-center mb-16 text-lg">Three steps to your personalised battery recommendation</p>

        <div className="grid sm:grid-cols-3 gap-10">
          {[
            {
              step: "01",
              icon: (
                <svg className="w-8 h-8 text-[#f97316]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                </svg>
              ),
              title: "Upload your usage data",
              desc: "Import a CSV export from your smart meter or energy supplier — or enter your annual consumption manually.",
            },
            {
              step: "02",
              icon: (
                <svg className="w-8 h-8 text-[#f97316]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                </svg>
              ),
              title: "Select your tariff",
              desc: "Choose your current energy tariff from our UK tariff library, or enter a custom rate. We factor in time-of-use pricing.",
            },
            {
              step: "03",
              icon: (
                <svg className="w-8 h-8 text-[#f97316]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              ),
              title: "Get your recommendation",
              desc: "See the optimal battery size, projected annual savings, and a clear payback period — so you can buy with confidence.",
            },
          ].map(({ step, icon, title, desc }) => (
            <div key={step} className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-8">
              <div className="flex items-center gap-3 mb-5">
                <span className="text-xs font-bold text-[#f97316] tracking-widest">{step}</span>
                {icon}
              </div>
              <h3 className="text-xl font-semibold mb-3">{title}</h3>
              <p className="text-slate-400 leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Two audience sections */}
      <section className="bg-slate-800/30 border-t border-slate-700/50 py-28">
        <div className="max-w-6xl mx-auto px-6 grid lg:grid-cols-2 gap-8">

          {/* Homeowners */}
          <div className="bg-[#0a1628] border border-slate-700/50 rounded-2xl p-8 flex flex-col">
            <div className="mb-6">
              <div className="inline-flex items-center gap-2 text-xs font-bold tracking-widest text-[#f97316] uppercase mb-4">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12l8.954-8.955a1.126 1.126 0 011.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" />
                </svg>
                For Homeowners
              </div>
              <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
                Find the battery and tariff combination to save you the most money
              </h2>
              <p className="text-slate-400 leading-relaxed">
                Stop guessing. See exactly which battery size and energy tariff will give you the fastest payback — based on your actual usage.
              </p>
            </div>

            <ul className="space-y-4 mb-8 flex-1">
              {[
                {
                  title: "Personalised to your home",
                  desc: "Upload your half-hourly smart meter data or enter your annual usage — we model your real consumption, not UK averages.",
                },
                {
                  title: "Compare every tariff side by side",
                  desc: "We run your data against Octopus Go, Economy 7, Intelligent Go, and more to show you exactly which tariff maximises your savings.",
                },
                {
                  title: "Clear payback timeline",
                  desc: "See your break-even point, 10-year ROI, and annual saving in pounds — so you can make a confident buying decision.",
                },
              ].map(({ title, desc }) => (
                <li key={title} className="flex gap-3">
                  <div className="mt-1 shrink-0 w-5 h-5 rounded-full bg-[#f97316] flex items-center justify-center">
                    <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                    </svg>
                  </div>
                  <div>
                    <span className="font-semibold text-white">{title}</span>
                    <p className="text-slate-400 text-sm leading-relaxed mt-0.5">{desc}</p>
                  </div>
                </li>
              ))}
            </ul>

            <Link
              href="/calculator"
              className="inline-flex items-center justify-center gap-2 bg-[#f97316] hover:bg-[#ea6c0a] text-white font-semibold px-7 py-3.5 rounded-full transition-colors text-base"
            >
              Start for free
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </Link>
          </div>

          {/* Installers */}
          <div className="bg-[#0d1f3c] border border-[#f97316]/30 rounded-2xl p-8 flex flex-col">
            <div className="mb-6">
              <div className="inline-flex items-center gap-2 text-xs font-bold tracking-widest text-[#f97316] uppercase mb-4">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17L17.25 21A2.652 2.652 0 0021 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 11-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 004.486-6.336l-3.276 3.277a3.004 3.004 0 01-2.25-2.25l3.276-3.276a4.5 4.5 0 00-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085m-1.745 1.437L5.909 7.5H4.5L2.25 3.75l1.5-1.5L7.5 4.5v1.409l4.26 4.26m-1.745 1.437l1.745-1.437m6.615 8.206L15.75 15.75M4.867 19.125h.008v.008h-.008v-.008z" />
                </svg>
                For Battery Installers
              </div>
              <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
                Design the best battery system for your customer
              </h2>
              <p className="text-slate-400 leading-relaxed">
                Give your customers a data-backed recommendation they can trust — and close more installations with confidence.
              </p>
            </div>

            <ul className="space-y-4 mb-8 flex-1">
              {[
                {
                  title: "Instant sizing for any customer",
                  desc: "Upload their smart meter CSV or enter annual consumption — get a full battery size and tariff recommendation in seconds, on-site or in the office.",
                },
                {
                  title: "Professional-grade output",
                  desc: "Show customers a clear breakdown of savings, payback period, and ROI across multiple battery sizes — built on real half-hourly simulation, not rule of thumb.",
                },
                {
                  title: "Supports every major UK tariff",
                  desc: "Model savings on Octopus Go, Intelligent Go, Economy 7, E.ON Drive, EDF, Scottish Power and more — so you can recommend the right system for each household.",
                },
              ].map(({ title, desc }) => (
                <li key={title} className="flex gap-3">
                  <div className="mt-1 shrink-0 w-5 h-5 rounded-full bg-[#f97316] flex items-center justify-center">
                    <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                    </svg>
                  </div>
                  <div>
                    <span className="font-semibold text-white">{title}</span>
                    <p className="text-slate-400 text-sm leading-relaxed mt-0.5">{desc}</p>
                  </div>
                </li>
              ))}
            </ul>

            <a
              href="mailto:hello@batterysizer.co.uk"
              className="inline-flex items-center justify-center gap-2 border-2 border-[#f97316] text-[#f97316] hover:bg-[#f97316] hover:text-white font-semibold px-7 py-3.5 rounded-full transition-colors text-base"
            >
              Contact us for pricing
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </a>
          </div>

        </div>
      </section>

      {/* CTA */}
      <section className="max-w-3xl mx-auto px-6 py-28 text-center">
        <h2 className="text-4xl sm:text-5xl font-bold mb-6">
          Ready to size your battery?
        </h2>
        <p className="text-slate-400 text-lg mb-10">
          Takes less than 2 minutes. Free, instant, and no sign-up required.
        </p>
        <Link
          href="/calculator"
          className="inline-flex items-center justify-center gap-2 bg-[#f97316] hover:bg-[#ea6c0a] text-white font-bold px-10 py-5 rounded-full transition-colors text-xl"
        >
          Start for free
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
        </Link>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-700/50 py-8">
        <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-slate-500 text-sm">
          <Image
            src="/batterysizer-logo.png"
            alt="BatterySizer"
            width={160}
            height={36}
            className="opacity-50"
          />
          <p>© {new Date().getFullYear()} BatterySizer. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
