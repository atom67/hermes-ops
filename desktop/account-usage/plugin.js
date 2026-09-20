// account-usage — Hermes Desktop pane (runtime plugin, plain ESM, no build step).
// Renders the multi-profile quota report with real contrast: progress bars per
// window, balances, alerts on top, per-model activity. Data comes from the
// backend plugin through the gateway RPC `cli.exec` → `hermes usage --json`
// (no chat session needed). Install: copy this folder to
// <hermes home>/desktop-plugins/account-usage/ (install.py does it).
import React from 'react'
import { Button, host, PANES_AREA } from '@hermes/plugin-sdk'

const h = React.createElement
const REFRESH_MS = 5 * 60 * 1000

function parseJson(output) {
  const start = Math.min(...['[', '{'].map(c => output.indexOf(c)).filter(i => i >= 0))
  if (!Number.isFinite(start)) throw new Error('no JSON in output: ' + output.slice(0, 200))
  return JSON.parse(output.slice(start))
}

async function fetchReports(scope) {
  const argv = scope === 'local' ? ['usage', '--local', '--json'] : ['usage', '--json']
  const res = await host.request('cli.exec', { argv, timeout: 120 })
  if (res?.blocked) throw new Error(res.hint || 'cli.exec blocked')
  const data = parseJson(res?.output || '')
  return Array.isArray(data) ? data : [data]
}

function pct(n) { return `${Math.max(0, Math.min(100, Math.round(n)))}%` }

function resetIn(iso) {
  if (!iso) return ''
  const ms = new Date(iso).getTime() - Date.now()
  if (!Number.isFinite(ms)) return ''
  const m = Math.round(ms / 60000)
  if (m < 60) return `resets in ${m}m`
  const hrs = Math.floor(m / 60)
  return hrs < 48 ? `resets in ${hrs}h ${m % 60}m` : `resets in ${Math.floor(hrs / 24)}d ${hrs % 24}h`
}

function tone(remaining) { return remaining < 15 ? 'bg-red-500' : remaining < 35 ? 'bg-amber-500' : 'bg-emerald-500' }

function WindowBar({ w }) {
  if (w.used_percent == null) return h('div', { className: 'text-xs text-muted-foreground' }, w.label)
  const remaining = 100 - Number(w.used_percent)
  return h('div', { className: 'space-y-0.5' },
    h('div', { className: 'flex justify-between text-xs' },
      h('span', null, w.label),
      h('span', { className: 'tabular-nums' }, `${pct(remaining)} left`, ' ',
        h('span', { className: 'text-muted-foreground' }, resetIn(w.reset_at)))),
    h('div', { className: 'h-1.5 w-full rounded bg-muted' },
      h('div', { className: `h-1.5 rounded ${tone(remaining)}`, style: { width: pct(remaining) } })))
}

function ProviderBlock({ b }) {
  const id = b.identity || {}
  const who = id.email || id.name
  const plan = id.chatgpt_plan_type || id.plan_type
  const usage = b.usage || {}
  const act = b.activity || {}
  const models = act.models && typeof act.models === 'object' ? Object.entries(act.models) : []
  const balanceLines = (usage.lines || []).filter(l => /balance|credits|usable|quota/i.test(l) && !/^Provider:/.test(l))
  return h('div', { className: 'rounded-md border border-border/60 p-2 space-y-1.5' },
    h('div', { className: 'flex items-baseline justify-between gap-2' },
      h('span', { className: 'font-medium' }, b.provider),
      h('span', { className: 'text-[11px] uppercase tracking-wide text-muted-foreground' }, b.kind)),
    who ? h('div', { className: 'text-xs text-muted-foreground' }, who, plan ? ` · ${plan}` : '') : null,
    b.same_as ? h('div', { className: 'text-xs text-muted-foreground italic' }, `same account as ${b.same_as} — limits shown there`) : null,
    ...(b.same_as ? [] : usage.windows || []).map((w, i) => h(WindowBar, { key: i, w })),
    !b.same_as && !(usage.windows || []).length && usage.balance_usd != null
      ? h('div', { className: 'text-sm' }, `Balance: $${Number(usage.balance_usd).toFixed(2)}`) : null,
    ...(b.same_as ? [] : balanceLines.slice(0, 3)).map((l, i) => h('div', { key: 'l' + i, className: 'text-xs text-muted-foreground' }, l)),
    !b.same_as && usage.unavailable_reason && !usage.windows?.length && b.kind !== 'spend'
      ? h('div', { className: `text-xs ${usage.not_fetchable ? 'text-muted-foreground' : 'text-amber-500'}` },
          usage.not_fetchable ? 'limits not fetchable in this Hermes version' : `unavailable: ${usage.unavailable_reason}`) : null,
    act.calls != null ? h('div', { className: 'text-xs text-muted-foreground' },
      `last ${act.days}d: ${act.calls} calls · ${act.cost_source === 'included in subscription' ? 'subscription'
        : act.cost_source === 'no pricing data' ? 'cost n/a' : `≈$${Number(act.spend_usd || 0).toFixed(2)}`}`,
      models.length ? ' — ' + models.map(([m, v]) => `${m} ${v.calls}`).join(', ') : '') : null)
}

function alertsOf(reports) {
  const out = []
  for (const r of reports) for (const b of r.providers || []) {
    if (b.same_as) continue
    const u = b.usage || {}
    for (const w of u.windows || []) if (w.used_percent != null && 100 - w.used_percent < 15) out.push(`${r.profile}/${b.provider} ${w.label}: ${pct(100 - w.used_percent)} left`)
    if (u.balance_usd != null && u.balance_usd < 5) out.push(`${r.profile}/${b.provider}: balance $${Number(u.balance_usd).toFixed(2)}`)
    if (u.unavailable_reason && !u.not_fetchable && b.kind !== 'spend') out.push(`${r.profile}/${b.provider}: ${u.unavailable_reason}`)
    if (r.error) out.push(`${r.profile}: ${r.error}`)
  }
  return out
}

function Pane() {
  const [scope, setScope] = React.useState('all')
  const [state, setState] = React.useState({ loading: true, reports: [], error: null, at: null })
  const load = React.useCallback(async (s = scope) => {
    setState(st => ({ ...st, loading: true, error: null }))
    try {
      const reports = await fetchReports(s)
      setState({ loading: false, reports, error: null, at: new Date() })
    } catch (e) {
      setState(st => ({ ...st, loading: false, error: String(e?.message || e) }))
    }
  }, [scope])
  React.useEffect(() => { load(scope); const t = setInterval(() => load(scope), REFRESH_MS); return () => clearInterval(t) }, [scope, load])
  const alerts = alertsOf(state.reports)
  return h('div', { className: 'flex h-full flex-col gap-2 overflow-auto p-2 text-sm text-foreground' },
    h('div', { className: 'flex items-center gap-2' },
      h(Button, { size: 'sm', variant: scope === 'all' ? 'default' : 'outline', onClick: () => setScope('all') }, 'All profiles'),
      h(Button, { size: 'sm', variant: scope === 'local' ? 'default' : 'outline', onClick: () => setScope('local') }, 'This profile'),
      h('span', { className: 'flex-1' }),
      h(Button, { size: 'sm', variant: 'ghost', disabled: state.loading, onClick: () => load(scope) }, state.loading ? '…' : '↻')),
    state.at ? h('div', { className: 'text-[11px] text-muted-foreground' }, `updated ${state.at.toLocaleTimeString()}`) : null,
    state.error ? h('div', { className: 'rounded border border-red-500/40 p-2 text-xs text-red-500' }, state.error) : null,
    alerts.length ? h('div', { className: 'rounded border border-amber-500/40 bg-amber-500/10 p-2 text-xs' },
      ...alerts.map((a, i) => h('div', { key: i }, '⚠ ', a))) : null,
    ...state.reports.map(r => h('div', { key: r.profile, className: 'space-y-1.5' },
      h('div', { className: 'text-xs font-semibold uppercase tracking-wide text-muted-foreground' }, r.profile),
      ...(r.providers || []).map((b, i) => h(ProviderBlock, { key: i, b })),
      !(r.providers || []).length ? h('div', { className: 'text-xs text-muted-foreground' }, r.error || 'no providers') : null)))
}

export default {
  id: 'account-usage',
  name: 'Account Usage',
  defaultEnabled: true,
  register(ctx) {
    ctx.register({
      id: 'pane',
      area: PANES_AREA,
      title: 'quota',
      data: { placement: 'right', collapsible: true, dock: { pane: 'workspace', pos: 'right' }, width: '340px', minWidth: '280px', maxWidth: '520px' },
      render: () => h(Pane)
    })
  }
}
