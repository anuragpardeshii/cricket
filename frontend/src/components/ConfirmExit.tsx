import { useEffect, useId, useRef } from 'react';

export function ConfirmExit({ open, busy, description, cancelLabel = 'Keep playing', onCancel, onConfirm }: { open: boolean; busy: boolean; description: string; cancelLabel?: string; onCancel: () => void; onConfirm: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null); const title = useId(); const detail = useId();
  const button = 'inline-flex min-h-11 items-center justify-center rounded-lg px-3 text-xs font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber disabled:cursor-not-allowed disabled:opacity-40';
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.showModal();
    return () => { dialog.current?.close(); previous?.focus(); };
  }, [open]);
  return <dialog ref={dialog} aria-labelledby={title} aria-describedby={detail} onCancel={event => { event.preventDefault(); if (!busy) onCancel(); }} className="m-auto w-[calc(100%_-_2rem)] max-w-sm rounded-2xl border border-neutral/15 bg-panel p-5 text-cream shadow-2xl backdrop:bg-black/60">
    <h2 id={title} className="text-lg font-semibold">Exit match?</h2><p id={detail} className="mt-2 text-[13px] leading-5 text-muted">{description}</p>
    <div className="mt-5 grid grid-cols-2 gap-2"><button type="button" autoFocus className={`${button} border border-neutral/15 hover:bg-neutral/5`} disabled={busy} onClick={onCancel}>{cancelLabel}</button><button type="button" className={`${button} bg-accent-fill text-on-accent hover:bg-accent-hover`} disabled={busy} onClick={onConfirm}>{busy ? 'Exiting…' : 'Confirm exit'}</button></div>
  </dialog>;
}
