import { useState } from 'react';
import { api, ApiError, type BrowserSession } from '../api';
import { Brand } from '../components/ui';
import { ThemeToggle } from '../theme/ThemeProvider';

export async function ensureSession() {
  try { return await api<BrowserSession>('/auth/me'); }
  catch (error) { if (!(error instanceof ApiError) || error.status !== 401) throw error; return api<BrowserSession>('/auth/guest', {}); }
}
export function returnPath() {
  const path = new URLSearchParams(location.search).get('returnTo') ?? '/';
  try {
    const target = new URL(path, location.origin);
    return path.startsWith('/') && target.origin === location.origin ? target.pathname + target.search + target.hash : '/';
  } catch { return '/'; }
}
export function CommunityHeader() {
  return <header className="mb-8 flex flex-wrap items-center justify-between gap-4 border-b border-neutral/10 pb-5"><a href="/" aria-label="OUT. home"><Brand /></a><nav aria-label="Player navigation" className="flex flex-wrap items-center gap-4 text-sm"><a href="/groups">Groups</a><a href="/achievements">Trophy cabinet</a><a href="/rooms">Play</a><ThemeToggle /></nav></header>;
}
export function ShareButton({ text, url, getUrl, label = 'Share' }: { text: string; url?: string; getUrl?: () => Promise<string>; label?: string }) {
  const [busy, setBusy] = useState(false); const [message, setMessage] = useState(''); const [manual, setManual] = useState('');
  const share = async () => {
    setBusy(true); setMessage(''); setManual('');
    try {
      const target = getUrl ? await getUrl() : url;
      const content = `${text}${target ? `\n${target}` : ''}`;
      if (navigator.share) {
        try { await navigator.share({ title: 'OUT. Cricket Draft', text, ...(target ? { url: target } : {}) }); setMessage('Shared.'); return; }
        catch (error) { if (error instanceof DOMException && error.name === 'AbortError') return; }
      }
      try { await navigator.clipboard.writeText(content); setMessage('Copied to clipboard.'); }
      catch { setManual(content); setMessage('Copy the details below to share.'); }
    } catch (error) { setMessage((error as Error).message); }
    finally { setBusy(false); }
  };
  return <div><button type="button" className="rounded-xl border border-amber/40 px-4 py-2 text-sm font-semibold text-amber disabled:opacity-50" disabled={busy} onClick={() => { void share(); }}>{busy ? 'Preparing…' : label}</button>{message && <p role="status" className="mt-2 text-xs text-muted">{message}</p>}{manual && <textarea aria-label="Details to share" readOnly value={manual} onFocus={e => e.currentTarget.select()} className="mt-2 min-h-28 w-full rounded-lg bg-input p-3 text-sm" />}</div>;
}
export const presetOptions = [{ value: 'open-ipl', label: 'Open IPL', description: 'Every IPL edition. Every rating.' }, { value: 'under-85', label: 'IPL Under 85', description: 'Only cards rated below 85. Discover hidden gems.' }];
export const presetName = (id?: string) => presetOptions.find(p => p.value === id)?.label ?? 'Classic draft';
export const dateLabel = (value: string) => new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
