import { PlayerRating, SquadValue } from './PlayerRating';
import { useEffect, useId, useRef, useState, type PointerEvent } from 'react';
import { SLOTS } from '../game/data';
import type { Player, XI } from '../game/types';

export const defaultOrder = SLOTS.map(slot => slot.id);
export function TeamFormation({ name, xi, order = defaultOrder, editable = false, busy = false, onOrder, selectedPlayer, allowedSlotIds, onPlace }: {
  name: string; xi: XI; order?: string[]; editable?: boolean; busy?: boolean;
  onOrder?: (order: string[]) => void; selectedPlayer?: Player; allowedSlotIds?: string[]; onPlace?: (slotId: string) => void;
}) {
  const list = useRef<HTMLOListElement>(null); const instructions = useId();
  const drag = useRef<{ from: number; to: number; keyboard: boolean } | null>(null);
  const [moving, setMoving] = useState<number | null>(null); const [over, setOver] = useState<number | null>(null);
  const [announcement, setAnnouncement] = useState('');
  const clear = () => { drag.current = null; setMoving(null); setOver(null); };
  const signature = order.join(',');
  useEffect(() => { clear(); }, [signature, busy, editable]);
  const begin = (index: number, keyboard = false) => {
    if (!editable || busy || !xi[order[index]]) return;
    drag.current = { from: index, to: index, keyboard }; setMoving(index); setOver(index);
    setAnnouncement(`${xi[order[index]]?.name} picked up at position ${index + 1}.`);
  };
  const target = (index: number) => {
    if (!drag.current) return;
    drag.current.to = index; setOver(index);
  };
  const finish = () => {
    const active = drag.current; clear();
    if (!active || !editable || busy || active.from === active.to) return;
    const next = [...order]; const [slot] = next.splice(active.from, 1); next.splice(active.to, 0, slot);
    setAnnouncement(`${xi[slot]?.name} moved to position ${active.to + 1}.`); onOrder?.(next);
  };
  const touchMove = (event: PointerEvent<HTMLButtonElement>) => {
    if (event.pointerType === 'mouse' || !drag.current) return;
    if (event.clientY < 70) window.scrollBy(0, -12);
    else if (event.clientY > window.innerHeight - 70) window.scrollBy(0, 12);
    const row = document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLElement>('[data-batting-position]');
    if (row && list.current?.contains(row)) target(Number(row.dataset.battingPosition));
  };
  return <section aria-label={`${name} team`}>
    <div className="mb-2 flex flex-wrap items-center justify-between gap-2"><h3 className="text-lg font-bold">{name === 'You' ? 'Your XI' : `${name}’s XI`}</h3><span className="font-mono text-xs text-muted">{Object.values(xi).filter(Boolean).length}/11</span></div>
    <div className="mb-3"><SquadValue xi={xi}/></div>
    {editable && <p className="mb-3 text-xs text-muted">Drag players to arrange your batting order.</p>}
    <p id={instructions} className="sr-only">Press Space to pick up a player, arrow keys to choose a position, and Space to drop. Escape cancels.</p>
    <span role="status" className="sr-only">{announcement}</span>
    <ol ref={list} className="overflow-hidden rounded-xl border border-neutral/10 bg-panel divide-y divide-neutral/10">{order.map((id, index) => {
      const slot = SLOTS.find(s => s.id === id)!; const player = xi[id];
      const canPlace = Boolean(selectedPlayer && !player && slot.accepts.includes(selectedPlayer.role) && (!allowedSlotIds || allowedSlotIds.includes(id)) && onPlace);
      return <li key={id} data-batting-position={index} draggable={editable && !busy && Boolean(player)}
        onDragStart={event => { if (!editable || busy || !player) { event.preventDefault(); return; } begin(index); event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', id); }}
        onDragOver={event => { if (drag.current) { event.preventDefault(); event.dataTransfer.dropEffect = 'move'; target(index); } }}
        onDrop={event => { if (drag.current) { event.preventDefault(); target(index); finish(); } }} onDragEnd={clear}
        className={`relative flex min-h-11 items-center gap-2 px-3 ${moving === index ? 'opacity-40' : ''} ${over === index && moving !== index ? 'bg-amber/10 ring-2 ring-inset ring-amber' : canPlace ? 'bg-amber/10' : ''}`}>
        <span className="w-5 shrink-0 text-center font-mono text-[10px] text-muted">{index + 1}</span>
        {canPlace ? <button className="min-w-0 flex-1 py-3 text-left text-sm font-semibold text-amber" aria-label={`Place ${selectedPlayer?.name} at position ${index + 1}`} disabled={busy} onClick={() => onPlace?.(id)}>Place here <span className="text-[10px] text-muted">{slot.accepts.join(' / ')}</span></button> : <span className={`min-w-0 flex-1 truncate text-sm ${player ? 'font-semibold text-cream' : 'text-muted/60'}`}>{player?.name ?? '—'}</span>}
        <span className="shrink-0 text-[10px] text-muted">{player?.role ?? (!canPlace ? slot.accepts.join('/') : '')}</span>
        {player && <PlayerRating value={player.rating}/>}
        {editable && player && <button type="button" disabled={busy} aria-label={`Drag ${player.name} to reorder`} aria-describedby={instructions} aria-pressed={moving === index} className="touch-none cursor-grab rounded p-2 text-muted hover:text-amber active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-amber disabled:opacity-30"
          onPointerDown={event => { if (event.pointerType !== 'mouse') { begin(index); event.currentTarget.setPointerCapture(event.pointerId); } }} onPointerMove={touchMove}
          onPointerUp={event => { if (event.pointerType !== 'mouse') finish(); }} onPointerCancel={clear}
          onKeyDown={event => {
            if (event.key === 'Escape') { event.preventDefault(); clear(); setAnnouncement('Move cancelled.'); }
            else if (event.key === ' ' || event.key === 'Enter') { event.preventDefault(); if (drag.current?.keyboard) finish(); else begin(index, true); }
            else if (drag.current?.keyboard && ['ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) {
              event.preventDefault(); const next = event.key === 'Home' ? 0 : event.key === 'End' ? 10 : Math.max(0, Math.min(10, drag.current.to + (event.key === 'ArrowUp' ? -1 : 1)));
              target(next); setAnnouncement(`Position ${next + 1}. Press Space to drop.`);
            }
          }}><svg aria-hidden="true" width="10" height="16" viewBox="0 0 10 16" fill="currentColor">{[3,8,13].flatMap(y=>[2,8].map(x=><circle key={`${x}-${y}`} cx={x} cy={y} r="1.2"/>))}</svg></button>}
      </li>;
    })}</ol>
  </section>;
}
