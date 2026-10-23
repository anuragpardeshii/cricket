import { ratingColor, squadValue } from '../game/ratings';
import type { XI } from '../game/types';

export function PlayerRating({ value }: { value: number }) {
  return <span aria-label={`Player rating ${value}`} className={`shrink-0 font-mono text-sm font-semibold tabular-nums ${ratingColor(value)}`}>{value}</span>;
}

export function SquadValue({ xi }: { xi: XI }) {
  return <span className="inline-flex flex-wrap items-baseline gap-x-2 text-xs" title="Average rating of selected players"><span className="text-muted">Squad value</span><strong className="font-mono text-sm tabular-nums text-cream">{squadValue(xi) ?? '—'}</strong></span>;
}
