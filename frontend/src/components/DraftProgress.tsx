export type DraftRules = {
  draftRulesVersion?: number;
  draftRound?: number;
  draftDirection?: number;
  turnPicks?: number;
};

type Seat = { id: string; name: string; count: number };

export function DraftProgress({ state, seats, currentId }: { state: DraftRules; seats: Seat[]; currentId: string }) {
  if ((state.draftRulesVersion ?? 1) < 2) return null;
  const current = seats.find(seat => seat.id === currentId);
  if (!current) return null;
  const used = state.turnPicks ?? 0;
  const total = Math.min(2, used + 11 - current.count);
  const reverse = state.draftDirection === -1;
  const order = reverse ? [...seats].reverse() : seats;
  return <section aria-label="Draft turn order" className="mb-4 rounded-xl border border-amber/25 bg-amber/5 p-4">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="text-xs font-bold text-amber">Snake draft · Round {state.draftRound ?? 1} of 6 · {reverse ? 'Last to first' : 'First to last'}</p>
      <p role="status" className="text-sm font-semibold">Chance {used + 1} of {total}{total === 1 ? ' · Final XI pick' : ''}</p>
    </div>
    <ol className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-2 text-xs" aria-label="This round’s order">
      {order.map((seat, index) => <li key={seat.id} className="flex min-w-0 max-w-full items-center gap-2">
        {index > 0 && <span aria-hidden="true" className="text-muted">→</span>}
        <span aria-current={seat.id === currentId ? 'step' : undefined} className={`truncate rounded-lg px-2 py-1 ${seat.id === currentId ? 'bg-amber/15 font-bold text-amber' : 'text-muted'}`}>{seat.name}{seat.count === 11 ? ' ✓' : ''}</span>
      </li>)}
    </ol>
    <p className="mt-3 text-xs leading-5 text-muted">Each chance starts with a fresh dice roll, then one pick. Take two chances, then pass. At each end, that player starts the next round. Your last visit needs just one pick.</p>
  </section>;
}
