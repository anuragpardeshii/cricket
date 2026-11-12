export type DraftRules = {
  draftRulesVersion?: number;
  draftRound?: number;
  draftDirection?: number;
  turnPicks?: number;
};

type Seat = { id: string; name: string; count: number };

export function DraftProgress({ state, seats, currentId, title, activity }: { state: DraftRules; seats: Seat[]; currentId: string; title?: string; activity?: string }) {
  const snake = (state.draftRulesVersion ?? 1) >= 2;
  if (!snake && !title) return null;
  const current = seats.find(seat => seat.id === currentId);
  if (!current) return null;
  const used = state.turnPicks ?? 0;
  const total = Math.min(2, used + 11 - current.count);
  const reverse = state.draftDirection === -1;
  const order = reverse ? [...seats].reverse() : seats;
  return <section aria-label="Draft turn order" className="mb-4 overflow-hidden rounded-xl border border-neutral/15 bg-panel">
    <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
      <div className="flex items-center gap-2.5"><span aria-hidden="true" className="size-2 shrink-0 rounded-full bg-success"/><h2 className="text-base font-semibold">{title ?? (current.name === 'You' ? 'Your turn' : `${current.name} is picking`)}</h2></div>
      {snake && <p role="status" className="rounded-full bg-amber/10 px-3 py-1 text-xs font-semibold text-amber">Chance {used + 1} of {total}</p>}
    </div>
    {snake && <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-neutral/10 px-4 py-2.5">
      <p className="shrink-0 text-xs text-muted">Round {state.draftRound ?? 1}/6 <span aria-hidden="true">·</span> {reverse ? 'Reverse order' : 'Forward order'}</p>
      <ol className="flex min-w-0 flex-wrap items-center gap-1.5 text-xs" aria-label="This round’s order">
        {order.map((seat, index) => <li key={seat.id} className="flex min-w-0 max-w-full items-center gap-1.5">
          {index > 0 && <span aria-hidden="true" className="text-muted/50">›</span>}
          <span aria-current={seat.id === currentId ? 'step' : undefined} className={`truncate ${seat.id === currentId ? 'font-semibold text-amber' : 'text-muted'}`}>{seat.name}{seat.count === 11 ? ' ✓' : ''}</span>
        </li>)}
      </ol>
    </div>}
    {activity && <p className="border-t border-neutral/10 px-4 py-2.5 text-xs leading-5 text-muted">{activity}</p>}
  </section>;
}
