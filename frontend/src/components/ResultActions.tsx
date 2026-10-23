import { useRef, useState } from 'react';

/** Share only the result text, never a private room code or membership URL. */
export function ResultActions({ text, busy, onExit, onPlayAgain }: {
  text: string; busy: boolean; onExit: () => void; onPlayAgain: () => void;
}) {
  const [sharing, setSharing] = useState(false);
  const [notice, setNotice] = useState('');
  const [manualCopy, setManualCopy] = useState(false);
  const pending = useRef(false);
  const share = async () => {
    if (pending.current) return;
    pending.current = true; setSharing(true); setNotice(''); setManualCopy(false);
    try {
      if (navigator.share) {
        try { await navigator.share({ title: 'OUT. — Match result', text }); return; }
        catch (error) { if (error instanceof DOMException && error.name === 'AbortError') return; }
      }
      await navigator.clipboard.writeText(text);
      setNotice('Result copied. Paste it to share.');
    } catch { setManualCopy(true); setNotice('Select and copy your result below to share it.'); }
    finally { pending.current = false; setSharing(false); }
  };
  const button = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-3 text-xs font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber disabled:opacity-40 sm:px-5 sm:text-sm';
  return <section aria-label="Result actions" className="my-5 print:hidden">
    <div className="grid grid-cols-3 gap-2 sm:flex sm:justify-end sm:gap-3">
      <button type="button" disabled={busy || sharing} onClick={onExit} className={`${button} border border-neutral/15 bg-panel text-cream hover:bg-neutral/5`}><ActionIcon kind="exit"/>Exit game</button>
      <button type="button" disabled={busy || sharing} onClick={() => { void share(); }} className={`${button} border border-neutral/15 bg-panel text-cream hover:bg-neutral/5`}><ActionIcon kind="share"/>{sharing ? 'Sharing…' : 'Share'}</button>
      <button type="button" disabled={busy || sharing} onClick={onPlayAgain} className={`${button} bg-accent-fill text-on-accent hover:bg-accent-hover`}><ActionIcon kind="replay"/>{busy ? 'Please wait…' : 'Play again'}</button>
    </div>
    <p role="status" className="mt-2 text-right text-xs text-muted">{notice}</p>
    {manualCopy && <textarea aria-label="Result to share" readOnly value={text} onFocus={event => event.target.select()} className="mt-2 min-h-32 w-full rounded-xl border border-neutral/15 bg-panel p-3 text-sm text-cream"/>}
  </section>;
}

function ActionIcon({ kind }: { kind: 'exit' | 'share' | 'replay' }) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" className="hidden size-4 shrink-0 min-[380px]:block">
    {kind === 'exit' ? <path d="M9 5H5v14h4M10 12h10m-4-4 4 4-4 4"/> : kind === 'share' ? <><path d="m9 11 6-4m-6 6 6 4"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="5" r="3"/><circle cx="18" cy="19" r="3"/></> : <path d="M4 10a8 8 0 1 1 1 7M4 4v6h6"/>}
  </svg>;
}
