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

      {/* Features */}
      <section className="bg-slate-800/30 border-t border-slate-700/50 py-28">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl sm:text-4xl font-bold text-center mb-4">Built for homeowners</h2>
          <p className="text-slate-400 text-center mb-16 text-lg">No guesswork. No sales pitch. Just accurate numbers.</p>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              {
                title: "Real usage analysis",
                desc: "We simulate your battery against your actual half-hourly consumption data, not averages.",
              },
              {
                title: "Payback calculator",
                desc: "See exactly how many years until your battery pays for itself, based on current energy prices.",
              },
              {
                title: "Multiple battery options",
                desc: "Compare leading home battery systems side by side to find the best fit for your home.",
              },
              {
                title: "Tariff aware",
                desc: "Supports Octopus Agile, Economy 7, and standard rates — including export tariffs for solar homes.",
              },
              {
                title: "Solar compatible",
                desc: "Have solar panels? We factor in your generation profile to maximise self-sufficiency.",
              },
              {
                title: "Instant & free",
                desc: "No account needed. Get your full recommendation in seconds, completely free.",
              },
            ].map(({ title, desc }) => (
              <div key={title} className="flex gap-4 p-6 rounded-xl bg-slate-800/40 border border-slate-700/40">
                <div className="mt-1 shrink-0 w-5 h-5 rounded-full bg-[#f97316] flex items-center justify-center">
                  <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                </div>
                <div>
                  <h3 className="font-semibold mb-1">{title}</h3>
                  <p className="text-slate-400 text-sm leading-relaxed">{desc}</p>
                </div>
              </div>
            ))}
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
