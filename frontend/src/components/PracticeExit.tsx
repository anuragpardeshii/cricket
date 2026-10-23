import { useState } from 'react';
import { ConfirmExit } from './ConfirmExit';
export function PracticeExit({ busy, onExit }: { busy: boolean; onExit: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  return <><button type="button" className="text-xs text-danger" onClick={() => setOpen(true)}>Exit match</button><ConfirmExit open={open} busy={busy} description="Your practice game will end. If the match has started, you forfeit to AI. You cannot return to this game after exiting." onCancel={() => setOpen(false)} onConfirm={() => { void onExit().then(() => setOpen(false)); }}/></>;
}
