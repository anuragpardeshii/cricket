import { useId, useState } from 'react';

export type BattingRow = { id: string; name: string; runs: number; balls: number; fours: number; sixes: number; dismissal: string };
export type BowlingRow = { id: string; name: string; balls: number; runs: number; wickets: number; maidens: number };
export type ScorecardData = { side: string; score: string; batting: BattingRow[]; bowling: BowlingRow[] };

export function Scorecard({ cards, names = { you: 'YOU', opp: 'OPPONENT' } }: { cards: ScorecardData[]; names?: Record<string, string> }) {
  const [side, setSide] = useState<string | null>(null);
  const contentId = useId();
  const card = cards.find(c => c.side === side) ?? cards[0];
  if (!card) return null;
  // A non-striker can participate without facing a ball; retain their not-out row.
  const batting = card.batting.filter(p => p.balls > 0 || p.runs > 0 || p.dismissal !== 'did not bat');
  const bowling = card.bowling.filter(p => p.balls > 0);
  const fours = batting.reduce((sum, p) => sum + p.fours, 0);
  const sixes = batting.reduce((sum, p) => sum + p.sixes, 0);
  const totalRuns = Number(card.score.split('/')[0]);
  const overs = card.score.match(/\((\d+)\.(\d)\)/);
  const balls = overs ? Number(overs[1]) * 6 + Number(overs[2]) : 0;
  const runRate = balls && Number.isFinite(totalRuns) ? (totalRuns / balls * 6).toFixed(2) : '—';
  return <section aria-label="Match scorecard" className="overflow-hidden rounded-2xl border border-neutral/15 bg-panel">
    <div className="flex items-center justify-between gap-3 px-4 pb-3 pt-4 sm:px-5">
      <h2 className="text-sm font-bold">Scorecard</h2><span className="font-mono text-[10px] uppercase tracking-widest text-muted">Full time</span>
    </div>
    <div className="mx-3 mb-4 grid grid-cols-2 gap-2 sm:mx-4" aria-label="Select innings">
      {cards.map(c => <button key={c.side} type="button" aria-pressed={c.side === card.side} aria-controls={contentId} onClick={() => setSide(c.side)} className={`min-w-0 rounded-xl border p-3 text-left transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber sm:px-4 ${c.side === card.side ? 'border-amber/50 bg-amber/5' : 'border-neutral/10 hover:bg-neutral/5'}`}>
        <span className="flex items-center justify-between gap-2"><span className="truncate text-xs font-semibold text-cream sm:text-sm">{names[c.side] ?? c.side}</span><span aria-hidden="true" className={`size-1.5 shrink-0 rounded-full ${c.side === card.side ? 'bg-amber' : 'bg-neutral/20'}`}/></span>
        <span className="mt-2 flex flex-wrap items-baseline gap-x-2"><span className="font-mono text-2xl font-bold tracking-tight text-cream">{c.score.split(' (')[0]}</span><span className="font-mono text-[11px] text-muted">{c.score.match(/\(([^)]+)\)/)?.[1]} ov</span></span>
        <span className="mt-1 block text-[10px] text-muted">{c.side === card.side ? 'Selected innings' : 'View innings'}</span>
      </button>)}
    </div>
    <div id={contentId} key={card.side} className="tournament-reveal">
      <div className="flex flex-wrap items-center justify-between gap-2 border-y border-neutral/10 bg-neutral/[.025] px-4 py-2 sm:px-5"><p className="text-xs font-medium text-cream">{names[card.side] ?? card.side} innings</p><p className="text-[11px] text-muted">RR <strong className="font-mono font-medium text-cream">{runRate}</strong><span className="mx-2 text-neutral/20">/</span><strong className="font-mono font-medium text-cream">{fours}</strong> fours<span className="mx-2 text-neutral/20">/</span><strong className="font-mono font-medium text-cream">{sixes}</strong> sixes</p></div>
      <div className="grid items-start md:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <div className="min-w-0 md:border-r md:border-neutral/10">
          <SectionTitle title="Batting" detail="R / B · boundaries · strike rate"/>
          <div className="overflow-x-auto"><table aria-label={`${names[card.side] ?? card.side} batting`} className="w-full text-left text-xs tabular-nums sm:text-[13px]">
            <thead className="border-y border-neutral/10 bg-neutral/[.025] text-[10px] text-muted"><tr><th scope="col" className="w-full py-2 pl-4 pr-2 font-medium">Batter</th>{['R', 'B', '4s', '6s', 'SR'].map(h => <th scope="col" className="px-2 py-2 text-right font-medium last:pr-4" key={h}>{h}</th>)}</tr></thead>
            <tbody>{batting.map(p => <tr key={p.id} className="border-b border-neutral/5 last:border-0 hover:bg-neutral/[.025]">
              <th scope="row" className="min-w-32 py-3 pl-4 pr-2 text-left font-normal"><span className="font-semibold text-cream">{p.name}{p.dismissal === 'not out' && <span aria-label="Not out" className="ml-0.5">*</span>}</span><span className="mt-1 block text-[11px] leading-4 text-muted">{p.dismissal}</span></th>
              <td className="bg-neutral/[.025] px-2 text-right text-sm font-bold text-cream">{p.runs}</td><td className="px-2 text-right text-muted">{p.balls}</td><td className="px-2 text-right text-muted">{p.fours}</td><td className="px-2 text-right text-muted">{p.sixes}</td><td className="whitespace-nowrap pl-2 pr-4 text-right text-muted">{p.balls ? (p.runs / p.balls * 100).toFixed(1) : '—'}</td>
            </tr>)}</tbody>
          </table></div>
          {!batting.length && <p className="p-4 text-xs text-muted">No batting recorded.</p>}
        </div>
        <div className="min-w-0 border-t border-neutral/10 md:border-0">
          <SectionTitle title="Bowling" detail="Overs · maidens · runs · wickets"/>
          <div className="overflow-x-auto"><table aria-label={`${names[card.side] ?? card.side} innings bowling`} className="w-full text-left text-xs tabular-nums sm:text-[13px]">
            <thead className="border-y border-neutral/10 bg-neutral/[.025] text-[10px] text-muted"><tr><th scope="col" className="w-full py-2 pl-4 pr-2 font-medium">Bowler</th>{['O', 'M', 'R', 'W', 'Econ'].map(h => <th scope="col" key={h} className="px-2 py-2 text-right font-medium last:pr-4">{h}</th>)}</tr></thead>
            <tbody>{bowling.map(p => <tr key={p.id} className="border-b border-neutral/5 last:border-0 hover:bg-neutral/[.025]">
              <th scope="row" className="min-w-28 py-3 pl-4 pr-2 font-semibold text-cream">{p.name}</th><td className="px-2 text-right text-muted">{Math.floor(p.balls / 6)}.{p.balls % 6}</td><td className="px-2 text-right text-muted">{p.maidens}</td><td className="px-2 text-right text-muted">{p.runs}</td><td className="bg-neutral/[.025] px-2 text-right text-sm font-bold text-cream">{p.wickets}</td><td className="whitespace-nowrap pl-2 pr-4 text-right text-muted">{(p.runs / p.balls * 6).toFixed(2)}</td>
            </tr>)}</tbody>
          </table></div>
          {!bowling.length && <p className="p-4 text-xs text-muted">No bowling recorded.</p>}
        </div>
      </div>
    </div>
  </section>;
}

function SectionTitle({ title, detail }: { title: string; detail: string }) {
  return <div className="flex flex-wrap items-baseline justify-between gap-1 px-4 py-3"><h3 className="text-sm font-bold">{title}</h3><span className="text-[10px] text-muted">{detail}</span></div>;
}
