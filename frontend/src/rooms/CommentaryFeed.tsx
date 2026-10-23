import type { TimelineEntry } from '../game/types';

export function CommentaryFeed({ entries, live }: { entries: TimelineEntry[]; live: boolean }) {
  const latest = entries.at(-1);
  const previous = entries.slice(0,-1).reverse();
  return <section aria-label="Over commentary" className="min-w-0">
    <div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-bold">From the commentary box</h3><span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-muted">{live&&<span className="size-1.5 animate-pulse rounded-full bg-success"/>}{live?'On air':'Match replay'}</span></div>
    <div aria-live="polite" aria-atomic="true">{latest ? <article key={`${latest.innings}-${latest.over}`} className="commentary-arrive relative overflow-hidden rounded-2xl border border-amber/30 bg-panel p-5 sm:p-6">
      <div className="absolute inset-y-0 left-0 w-1 bg-amber"/>
      <div className="mb-4 flex flex-wrap items-center gap-2 text-[10px] font-semibold uppercase tracking-wider"><span className="rounded bg-amber/10 px-2 py-1 text-amber">{latest.over}</span><span className="text-muted">Innings {latest.innings}</span>{live&&<span className="ml-auto text-success">Latest over</span>}</div>
      <p className="commentary-voice text-base leading-7 sm:text-lg sm:leading-8">{latest.text}</p>
    </article> : <div className="rounded-2xl border border-dashed border-neutral/20 p-6 text-sm leading-6 text-muted">The field is set. {live?'Waiting for the opening over…':'No completed overs to report.'}</div>}</div>
    {previous.length>0&&<details className="mt-4 rounded-xl border border-neutral/10 bg-panel"><summary className="cursor-pointer px-4 py-3 text-xs font-semibold text-muted">Earlier overs · {previous.length}</summary><ol className="max-h-80 overflow-y-auto px-4 pb-2">{previous.map(entry=><li key={`${entry.innings}-${entry.over}`} className="relative border-l border-neutral/15 pb-5 pl-4 last:pb-2"><span className="absolute -left-1 top-1 size-2 rounded-full bg-amber/60"/><p className="mb-1 font-mono text-[10px] text-amber">INN {entry.innings} · {entry.over}</p><p className="text-sm leading-6 text-muted">{entry.text}</p></li>)}</ol></details>}
  </section>;
}
