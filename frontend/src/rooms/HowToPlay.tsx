import { useEffect, useId, useRef } from 'react';

export function HowToPlay({ open, onClose, snake = true }: { open: boolean; onClose: () => void; snake?: boolean }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const title = useId();
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.showModal();
    return () => { dialog.current?.close(); previous?.focus(); };
  }, [open]);
  return <dialog ref={dialog} aria-labelledby={title} onCancel={event => { event.preventDefault(); onClose(); }} className="m-auto w-[calc(100%_-_2rem)] max-w-lg rounded-2xl border border-neutral/15 bg-panel p-6 text-cream shadow-2xl backdrop:bg-black/70">
    <div className="flex items-start justify-between gap-4"><div><p className="font-mono text-[10px] tracking-[.2em] text-amber">ROOM GUIDE</p><h2 id={title} className="mt-2 text-2xl font-bold">How to play</h2></div><button type="button" aria-label="Close how to play" className="rounded-lg px-3 py-2 text-muted hover:bg-neutral/5 hover:text-cream" onClick={onClose}>×</button></div>
    <ol className="mt-5 space-y-4 text-sm leading-6 text-muted">
      <li><strong className="text-cream">1. Create or join.</strong> Choose ODI World Cup, T20 World Cup, or IPL. Rolls can contain a squad from any historical edition in that competition.</li>
      <li><strong className="text-cream">2. Get ready.</strong> Every human player presses Ready. Only the room host can start, and empty seats become AI teams.</li>
      <li><strong className="text-cream">3. Draft an XI.</strong> Every chance starts with a fresh dice roll. Choose one available player from that squad and place them in a compatible position. {snake ? 'You get two chances per turn. Turns go first to last, then last to first; the endpoint player starts the next round. The final visit needs just one pick.' : 'Each player gets one chance before passing to the next player.'} You also have three optional rerolls across the whole draft. Each chance has its own timer; rerolls restart it, and an expired chance gets an automatic roll and pick.</li>
      <li><strong className="text-cream">4. Play the tournament.</strong> Opening fixtures are drawn randomly. ODI matches use 50 overs; T20 World Cup and IPL matches use 20 overs.</li>
    </ol>
    <button type="button" autoFocus className="mt-6 min-h-11 w-full rounded-xl bg-accent-fill px-4 font-bold text-on-accent hover:bg-accent-hover" onClick={onClose}>Got it</button>
  </dialog>;
}
