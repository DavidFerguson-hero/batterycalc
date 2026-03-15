'use client'

import { useEffect, useState } from 'react'
import Image from 'next/image'
import Link from 'next/link'

// ── Types ─────────────────────────────────────────────────────────────────────

interface TariffResult {
  key: string
  name: string
  status: 'ok' | 'changed' | 'error' | 'manual'
  source: string
  source_url?: string
  product_code?: string
  current_rates?: Record<string, number>
  found_rates?: Record<string, number>
  changes?: string[]
  error?: string
  notes?: string
}

interface RunSummary {
  total: number
  ok: number
  changed: number
  manual: number
  error: number
}

interface Run {
  id: string
  timestamp: string
  overall: 'ok' | 'alert' | 'error'
  summary: RunSummary
  tariffs: Record<string, TariffResult>
}

interface LogData {
  runs: Run[]
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', timeZone: 'UTC',
  }) + ' UTC'
}

function fmtRate(key: string, val: number) {
  return `${val}p`
}

function fmtRates(rates: Record<string, number> | undefined) {
  if (!rates) return '—'
  return Object.entries(rates)
    .map(([k, v]) => `${k.replace(/_p$/, '')}: ${v}p`)
    .join(' · ')
}

const STATUS_CONFIG = {
  ok:      { label: 'No change',   bg: 'bg-emerald-500/15', text: 'text-emerald-400', border: 'border-emerald-500/30', dot: 'bg-emerald-400' },
  changed: { label: 'Changed',     bg: 'bg-orange-500/15',  text: 'text-orange-400',  border: 'border-orange-500/30',  dot: 'bg-orange-400'  },
  error:   { label: 'Error',       bg: 'bg-red-500/15',     text: 'text-red-400',     border: 'border-red-500/30',     dot: 'bg-red-400'     },
  manual:  { label: 'Manual check',bg: 'bg-slate-500/15',   text: 'text-slate-400',   border: 'border-slate-500/30',   dot: 'bg-slate-400'   },
}

const OVERALL_CONFIG = {
  ok:    { label: 'All clear',       bg: 'bg-emerald-500/10', text: 'text-emerald-300', border: 'border-emerald-500/20' },
  alert: { label: 'Changes found',   bg: 'bg-orange-500/10',  text: 'text-orange-300',  border: 'border-orange-500/20'  },
  error: { label: 'Check errors',    bg: 'bg-red-500/10',     text: 'text-red-300',     border: 'border-red-500/20'     },
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: TariffResult['status'] }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.manual
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${cfg.bg} ${cfg.text} ${cfg.border}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  )
}

function TariffRow({ t }: { t: TariffResult }) {
  const [open, setOpen] = useState(false)
  const hasDetail = t.changes?.length || t.error || t.notes || t.found_rates

  return (
    <div className="border border-white/5 rounded-lg overflow-hidden">
      <button
        onClick={() => hasDetail && setOpen(o => !o)}
        className={`w-full flex items-center gap-3 px-4 py-3 text-left transition-colors ${hasDetail ? 'hover:bg-white/5 cursor-pointer' : 'cursor-default'}`}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm font-medium text-white">{t.name}</span>
            <StatusBadge status={t.status} />
            {t.status === 'changed' && t.changes?.length ? (
              <span className="text-xs text-orange-300">
                {t.changes.length} rate{t.changes.length > 1 ? 's' : ''} changed
              </span>
            ) : null}
          </div>
          <div className="text-xs text-slate-500 mt-0.5">{t.source}</div>
        </div>
        {hasDetail && (
          <svg className={`w-4 h-4 text-slate-500 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        )}
      </button>

      {open && hasDetail && (
        <div className="border-t border-white/5 px-4 py-3 space-y-3 bg-white/[0.02]">
          {/* Rate changes */}
          {t.status === 'changed' && t.changes?.length ? (
            <div>
              <div className="text-xs font-medium text-orange-400 mb-1.5">Rate changes detected</div>
              <div className="space-y-1">
                {t.changes.map((ch, i) => (
                  <div key={i} className="text-xs font-mono text-orange-300 bg-orange-500/5 border border-orange-500/10 rounded px-2.5 py-1">
                    {ch}
                  </div>
                ))}
              </div>
              <div className="mt-2 text-xs text-slate-400">
                Update <code className="text-orange-300">api/engine/tariffs.py</code> to apply these changes.
              </div>
            </div>
          ) : null}

          {/* Rate comparison */}
          {t.current_rates && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
              <div className="bg-white/5 rounded px-3 py-2">
                <div className="text-slate-500 mb-1">Current in tariffs.py</div>
                <div className="text-slate-300 font-mono">{fmtRates(t.current_rates)}</div>
              </div>
              {t.found_rates && (
                <div className={`rounded px-3 py-2 ${t.status === 'changed' ? 'bg-orange-500/10' : 'bg-white/5'}`}>
                  <div className="text-slate-500 mb-1">Found from source</div>
                  <div className={`font-mono ${t.status === 'changed' ? 'text-orange-300' : 'text-slate-300'}`}>
                    {fmtRates(t.found_rates)}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Error */}
          {t.error && (
            <div className="text-xs text-red-300 bg-red-500/5 border border-red-500/10 rounded px-3 py-2 font-mono">
              {t.error}
            </div>
          )}

          {/* Notes */}
          {t.notes && (
            <div className="text-xs text-slate-400">{t.notes}</div>
          )}

          {/* Source link */}
          {t.source_url && (
            <a
              href={t.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-[#f97316] hover:text-orange-300 transition-colors"
            >
              View source
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          )}

          {/* Product code */}
          {t.product_code && (
            <div className="text-xs text-slate-600 font-mono">Product code: {t.product_code}</div>
          )}
        </div>
      )}
    </div>
  )
}

function RunCard({ run }: { run: Run }) {
  const [open, setOpen] = useState(false)
  const cfg = OVERALL_CONFIG[run.overall] ?? OVERALL_CONFIG.ok
  const tariffList = Object.values(run.tariffs)
  const changed = tariffList.filter(t => t.status === 'changed')
  const errors  = tariffList.filter(t => t.status === 'error')

  return (
    <div className={`border rounded-xl overflow-hidden ${cfg.border} ${cfg.bg}`}>
      {/* Header row */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-start sm:items-center gap-4 px-5 py-4 text-left hover:bg-white/5 transition-colors cursor-pointer"
      >
        {/* Overall status dot */}
        <div className={`mt-1 sm:mt-0 w-2.5 h-2.5 rounded-full shrink-0 ${
          run.overall === 'ok' ? 'bg-emerald-400' :
          run.overall === 'alert' ? 'bg-orange-400' : 'bg-red-400'
        }`} />

        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="text-sm font-semibold text-white">{fmtDate(run.timestamp)}</span>
            <span className={`text-xs font-medium ${cfg.text}`}>{cfg.label}</span>
          </div>
          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-slate-500">
            {run.summary.ok      > 0 && <span className="text-emerald-500">{run.summary.ok} no change</span>}
            {run.summary.changed > 0 && <span className="text-orange-400 font-medium">{run.summary.changed} changed</span>}
            {run.summary.manual  > 0 && <span>{run.summary.manual} manual</span>}
            {run.summary.error   > 0 && <span className="text-red-400">{run.summary.error} error{run.summary.error > 1 ? 's' : ''}</span>}
          </div>
        </div>

        {/* Expand chevron */}
        <svg className={`w-4 h-4 text-slate-500 shrink-0 mt-1 sm:mt-0 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Expanded tariff list */}
      {open && (
        <div className="border-t border-white/10 px-5 py-4">
          {/* Highlight changed/errored tariffs first */}
          {(changed.length > 0 || errors.length > 0) && (
            <div className="mb-3 space-y-2">
              {[...changed, ...errors].map(t => <TariffRow key={t.key} t={t} />)}
            </div>
          )}
          {/* Rest */}
          <div className="space-y-2">
            {tariffList
              .filter(t => t.status !== 'changed' && t.status !== 'error')
              .map(t => <TariffRow key={t.key} t={t} />)}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function TariffUpdatesPage() {
  const [data, setData] = useState<LogData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/tariff-logs.json')
      .then(r => r.json())
      .then(setData)
      .catch(() => setError('Could not load tariff log.'))
      .finally(() => setLoading(false))
  }, [])

  const latest = data?.runs?.[0]
  const totalRuns = data?.runs?.length ?? 0

  return (
    <div className="min-h-screen bg-[#0a1628] text-white font-sans">

      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-5 max-w-6xl mx-auto">
        <Link href="/" style={{ display: 'block', lineHeight: 0 }}>
          <Image src="/batterysizer-logo.png" alt="BatterySizer" width={260} height={60} priority />
        </Link>
        <Link
          href="/calculator"
          className="text-sm font-medium text-slate-300 hover:text-white transition-colors"
        >
          ← Calculator
        </Link>
      </nav>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 pt-10 pb-8">
        <h1 className="text-3xl sm:text-4xl font-bold text-white mb-3">
          Tariff Rate Monitor
        </h1>
        <p className="text-slate-400 text-lg max-w-2xl">
          Runs every night at 02:00 UTC. Checks live sources for each tariff and flags
          any rate changes that need to be applied to the calculator.
        </p>

        {/* Stats row */}
        {data && (
          <div className="mt-6 flex flex-wrap gap-4">
            <div className="bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-center min-w-[100px]">
              <div className="text-2xl font-bold text-white">{totalRuns}</div>
              <div className="text-xs text-slate-500 mt-0.5">Runs logged</div>
            </div>
            {latest && (
              <>
                <div className="bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-center min-w-[100px]">
                  <div className="text-2xl font-bold text-emerald-400">{latest.summary.ok}</div>
                  <div className="text-xs text-slate-500 mt-0.5">Up to date</div>
                </div>
                <div className={`bg-white/5 border rounded-lg px-4 py-3 text-center min-w-[100px] ${latest.summary.changed > 0 ? 'border-orange-500/30' : 'border-white/10'}`}>
                  <div className={`text-2xl font-bold ${latest.summary.changed > 0 ? 'text-orange-400' : 'text-slate-500'}`}>
                    {latest.summary.changed}
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5">Need update</div>
                </div>
                <div className="bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-center min-w-[100px]">
                  <div className="text-2xl font-bold text-slate-400">{latest.summary.manual}</div>
                  <div className="text-xs text-slate-500 mt-0.5">Manual check</div>
                </div>
              </>
            )}
          </div>
        )}
      </section>

      {/* How it works */}
      <section className="max-w-6xl mx-auto px-6 pb-8">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            { icon: '🐙', title: 'Octopus API', desc: 'Go, Intelligent Go and Cosy rates pulled from the official Octopus Energy API — unit rates and standing charges.' },
            { icon: '⚡', title: 'Ofgem Price Cap', desc: 'Standard Variable and British Gas SV rates checked against the latest Ofgem price cap figures.' },
            { icon: '🔗', title: 'Manual sources', desc: 'Economy 7, E.ON, EDF and Scottish Power flagged with direct links to their tariff pages for manual review.' },
          ].map(item => (
            <div key={item.title} className="bg-white/[0.03] border border-white/8 rounded-xl p-4">
              <div className="text-xl mb-2">{item.icon}</div>
              <div className="text-sm font-semibold text-white mb-1">{item.title}</div>
              <div className="text-xs text-slate-500 leading-relaxed">{item.desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Run log */}
      <section className="max-w-6xl mx-auto px-6 pb-20">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Run history</h2>
          {data && <span className="text-xs text-slate-500">{totalRuns} run{totalRuns !== 1 ? 's' : ''} · last 90 days</span>}
        </div>

        {loading && (
          <div className="text-slate-500 text-sm py-12 text-center">Loading…</div>
        )}

        {error && (
          <div className="text-red-400 text-sm py-12 text-center">{error}</div>
        )}

        {data && data.runs.length === 0 && (
          <div className="text-slate-500 text-sm py-12 text-center">
            No runs yet. The checker runs nightly at 02:00 UTC, or can be triggered manually from GitHub Actions.
          </div>
        )}

        {data && data.runs.length > 0 && (
          <div className="space-y-3">
            {data.runs.map(run => <RunCard key={run.id} run={run} />)}
          </div>
        )}
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 py-8">
        <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-slate-500 text-sm">
          <span>© {new Date().getFullYear()} BatterySizer</span>
          <div className="flex gap-6">
            <Link href="/" className="hover:text-slate-300 transition-colors">Home</Link>
            <Link href="/calculator" className="hover:text-slate-300 transition-colors">Calculator</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
