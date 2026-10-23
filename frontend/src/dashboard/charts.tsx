import { useState } from 'react';
import { formatCompact, formatNumber, type Segment, type TrendPoint } from './data';

export function DonutChart({ title, subtitle, segments, totalLabel }: {
  title: string;
  subtitle: string;
  segments: Segment[];
  totalLabel: string;
}) {
  const [active, setActive] = useState<number | null>(null);
  const circumference = 2 * Math.PI * 70;
  let offset = 0;

  return <section className="rounded-2xl border border-neutral/10 bg-input p-5 sm:p-6">
    <div><h3 className="text-base font-bold tracking-tight text-cream">{title}</h3><p className="mt-1 text-xs text-muted">{subtitle}</p></div>
    <div className="mt-5 flex flex-col items-center gap-5 sm:flex-row sm:gap-7 lg:flex-col xl:flex-row">
      <div className="relative size-44 shrink-0">
        <svg viewBox="0 0 180 180" className="size-full" aria-label={`${title} pie chart`}>
          <circle cx="90" cy="90" r="70" fill="none" stroke="var(--color-neutral)" strokeOpacity=".12" strokeWidth="19" />
          {segments.map((segment, index) => {
            const length = circumference * segment.value / 100;
            const segmentOffset = offset;
            offset += length;
            return <circle
              key={segment.label}
              cx="90" cy="90" r="70" fill="none"
              stroke={segment.color}
              strokeWidth={active === index ? 25 : 19}
              strokeDasharray={`${Math.max(0, length - 3)} ${circumference - Math.max(0, length - 3)}`}
              strokeDashoffset={-segmentOffset}
              strokeLinecap="butt"
              transform="rotate(-90 90 90)"
              className="cursor-pointer transition-all duration-150 focus:outline-none"
              tabIndex={0}
              role="button"
              aria-label={`${segment.label}: ${segment.value}%`}
              onMouseEnter={() => setActive(index)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(index)}
              onBlur={() => setActive(null)}
            />;
          })}
        </svg>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center" aria-live="polite">
          <strong className="text-2xl font-black tracking-tight text-cream">{active === null ? totalLabel : `${segments[active].value}%`}</strong>
          <span className="mt-1 max-w-24 font-mono text-[10px] uppercase tracking-widest text-muted">{active === null ? 'Total' : segments[active].label}</span>
        </div>
      </div>
      <div className="w-full min-w-0 flex-1 space-y-1">
        {segments.map((segment, index) => <button key={segment.label} onMouseEnter={() => setActive(index)} onMouseLeave={() => setActive(null)} onFocus={() => setActive(index)} onBlur={() => setActive(null)} className={`flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left transition ${active === index ? 'bg-neutral/5' : 'hover:bg-neutral/5'}`}>
          <span className="size-2.5 rounded-full" style={{ backgroundColor: segment.color }} />
          <span className="flex-1 text-xs text-cream/70">{segment.label}</span>
          <span className="font-mono text-xs font-semibold text-cream">{segment.value}%</span>
        </button>)}
      </div>
    </div>
  </section>;
}

type Metric = 'activePlayers' | 'registrations';

export function ActivityBars({ points, periodLabel }: { points: TrendPoint[]; periodLabel: string }) {
  const [metric, setMetric] = useState<Metric>('activePlayers');
  const [active, setActive] = useState<number | null>(null);
  const peak = Math.max(...points.map((point) => point[metric]));
  const step = peak < 250 ? 50 : peak < 1000 ? 100 : 500;
  const maxValue = Math.ceil(peak / step) * step || step;
  const selected = active === null ? null : points[active];

  return <section id="activity" className="scroll-mt-20 rounded-2xl border border-neutral/10 bg-input p-5 sm:p-6 lg:p-7">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div><h2 className="text-lg font-bold tracking-tight">Player activity</h2><p className="mt-1 text-xs text-muted">{periodLabel} · hover or focus a bar for details</p></div>
      <div className="flex rounded-lg border border-neutral/10 bg-background p-1" role="group" aria-label="Chart metric">
        <button onClick={() => { setMetric('activePlayers'); setActive(null); }} aria-pressed={metric === 'activePlayers'} className={`rounded-md px-3 py-1.5 text-[11px] font-semibold transition ${metric === 'activePlayers' ? 'bg-selected text-cream' : 'text-muted hover:text-cream'}`}>Active players</button>
        <button onClick={() => { setMetric('registrations'); setActive(null); }} aria-pressed={metric === 'registrations'} className={`rounded-md px-3 py-1.5 text-[11px] font-semibold transition ${metric === 'registrations' ? 'bg-selected text-cream' : 'text-muted hover:text-cream'}`}>Registrations</button>
      </div>
    </div>

    <div className="relative mt-7">
      <div className="absolute right-0 top-0 z-10 rounded-lg border border-neutral/10 bg-raised px-3 py-2 text-right shadow-lg" aria-live="polite">
        {selected ? <><span className="block font-mono text-[10px] text-muted">{selected.label}</span><strong className="block text-sm">{formatNumber(selected[metric])} {metric === 'activePlayers' ? 'active' : 'new'}</strong></> : <><span className="block font-mono text-[10px] text-muted">PEAK</span><strong className="block text-sm">{formatNumber(Math.max(...points.map((point) => point[metric])))}</strong></>}
      </div>
      <div className="overflow-x-auto pb-1">
        <div className={`grid grid-cols-[42px_1fr] gap-3 ${points.length > 7 ? 'min-w-[500px]' : 'min-w-0'}`}>
          <div className="flex h-56 flex-col justify-between pb-6 text-right font-mono text-[10px] text-muted"><span>{formatCompact(maxValue)}</span><span>{formatCompact(maxValue / 2)}</span><span>0</span></div>
          <div className="relative h-56">
            <div className="pointer-events-none absolute inset-x-0 top-0 bottom-6 flex flex-col justify-between"><span className="border-t border-dashed border-neutral/10" /><span className="border-t border-dashed border-neutral/10" /><span className="border-t border-neutral/15" /></div>
            <div className="relative flex h-full items-end gap-1 sm:gap-2">
              {points.map((point, index) => <button
                key={point.label}
                type="button"
                aria-label={`${point.label}: ${formatNumber(point.activePlayers)} active players, ${formatNumber(point.registrations)} registrations`}
                onMouseEnter={() => setActive(index)} onMouseLeave={() => setActive(null)}
                onFocus={() => setActive(index)} onBlur={() => setActive(null)}
                className="group flex h-full min-w-0 flex-1 flex-col justify-end focus-visible:outline-2 focus-visible:outline-amber"
              >
                <span className={`mx-auto block w-full max-w-10 rounded-t-md transition-all duration-150 ${active === index ? 'bg-accent-hover' : metric === 'activePlayers' ? 'bg-amber/75 group-hover:bg-amber' : 'bg-[#83a9c7]/75 group-hover:bg-[#83a9c7]'}`} style={{ height: `${Math.max(4, point[metric] / maxValue * 100)}%` }} />
                <span className="flex h-6 items-end justify-center whitespace-nowrap font-mono text-[9px] text-muted sm:text-[10px]">{point.label}</span>
              </button>)}
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>;
}
