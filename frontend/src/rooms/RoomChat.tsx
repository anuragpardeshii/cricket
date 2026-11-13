import { useEffect, useId, useRef, useState } from 'react';
import { api } from '../api';
import { ActionButton, Eyebrow } from '../components/ui';
import type { Room } from './types';

const emojis = [['😀', 'Smile'], ['😂', 'Laugh'], ['😎', 'Cool'], ['😍', 'Love it'], ['😮', 'Surprised'], ['😭', 'Crying'], ['👏', 'Applause'], ['🙌', 'Celebrate'], ['👍', 'Thumbs up'], ['🤝', 'Handshake'], ['🔥', 'Fire'], ['❤️', 'Heart'], ['🏏', 'Cricket'], ['🏆', 'Trophy'], ['🎯', 'On target'], ['💪', 'Strong'], ['🎉', 'Party'], ['💯', 'Hundred']];

export function RoomChat({ room, onRoom, sidebar = false }: { room: Room; onRoom: (room: Room) => void; sidebar?: boolean }) {
  const [open, setOpen] = useState(sidebar), [text, setText] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const log = useRef<HTMLDivElement>(null), nonce = useRef<string | null>(null);
  const [emojiOpen, setEmojiOpen] = useState(false);
  const input = useRef<HTMLInputElement>(null), emojiToggle = useRef<HTMLButtonElement>(null);
  const pickerId = useId();
  const insertEmoji = (emoji: string) => {
    const start = input.current?.selectionStart ?? text.length;
    const end = input.current?.selectionEnd ?? start;
    const next = text.slice(0, start) + emoji + text.slice(end);
    if (next.length > 300) return;
    setText(next); nonce.current = null; setEmojiOpen(false);
    requestAnimationFrame(() => { input.current?.focus(); input.current?.setSelectionRange(start + emoji.length, start + emoji.length); });
  };
  const messages = room.state.chat ?? [];
  useEffect(() => { if (open && log.current) log.current.scrollTop = log.current.scrollHeight; }, [messages.at(-1)?.id, open]);

  return <aside aria-label="Room chat" className={`${sidebar ? 'flex h-[28rem] flex-col lg:sticky lg:top-4 lg:h-[calc(100dvh-7rem)]' : 'my-5'} min-w-0 overflow-hidden rounded-2xl border border-neutral/10 bg-panel`}>
    <header className="shrink-0 border-b border-neutral/10 px-5 py-4">
      {sidebar ? <><Eyebrow>From the pavilion</Eyebrow><div className="mt-2 flex items-center justify-between gap-3"><h2 className="text-xl font-bold">Room chat</h2><span className="rounded-full border border-amber/20 bg-amber/5 px-2 py-1 font-mono text-[10px] text-amber">{room.state.members.filter(m => !m.is_ai).length} players</span></div></> :
        <button type="button" className="flex w-full items-center justify-between gap-3 text-left focus-visible:outline-2 focus-visible:outline-amber" aria-expanded={open} onClick={() => setOpen(!open)}><span className="text-lg font-bold">Room chat</span><span className="font-mono text-xs text-muted">{messages.length ? `${messages.length} messages` : 'Say hello'} <span className="ml-2 text-amber">{open ? '−' : '+'}</span></span></button>}
    </header>
    {open && <>
      <div ref={log} role="log" aria-label="Room messages" aria-live="polite" aria-relevant="additions" className={`min-h-0 overflow-y-auto overscroll-contain px-4 py-3 ${sidebar ? 'flex-1' : 'max-h-80'}`}>
        {messages.map(m => {
          const yours = m.sender === room.you;
          return <div key={`${m.sender}:${m.id}`} className={`flex min-w-0 gap-3 rounded-xl px-2 py-3 ${yours ? 'bg-amber/5' : ''}`}>
            <span aria-hidden="true" className={`flex size-8 shrink-0 items-center justify-center rounded-full border font-mono text-xs font-semibold ${yours ? 'border-amber/25 text-amber' : 'border-neutral/10 bg-raised text-muted'}`}>{m.name.trim().slice(0, 2).toUpperCase()}</span>
            <div className="min-w-0 flex-1"><div className="flex flex-wrap items-baseline gap-x-2 gap-y-1"><span className={`break-words text-xs font-bold [overflow-wrap:anywhere] ${yours ? 'text-amber' : 'text-cream'}`}>{m.name}{yours ? ' · You' : ''}</span><time dateTime={new Date(m.sentAt * 1000).toISOString()} className="ml-auto shrink-0 font-mono text-[10px] text-muted">{new Date(m.sentAt * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time></div><p className="mt-1 whitespace-pre-wrap text-sm leading-6 [overflow-wrap:anywhere]">{m.text}</p></div>
          </div>;
        })}
        {!messages.length && <div className={`${sidebar ? 'flex h-full flex-col justify-center' : ''} px-3 py-8`}><span aria-hidden="true" className="mb-4 text-3xl font-black tracking-tight text-amber">OUT.</span><p className="font-bold">Your room. Your cricket talk.</p><p className="mt-2 text-sm leading-6 text-muted">Talk picks, celebrate a wicket, or say hello to your rivals.</p></div>}
      </div>
      <form onKeyDown={e => { if (e.key === 'Escape' && emojiOpen) { e.preventDefault(); setEmojiOpen(false); emojiToggle.current?.focus(); } }} className="shrink-0 border-t border-neutral/10 bg-input/40 p-4" onSubmit={async e => {
        e.preventDefault(); if (busy || !text.trim()) return;
        setBusy(true); setError(''); setEmojiOpen(false); nonce.current ??= crypto.randomUUID();
        try { onRoom(await api<Room>(`/rooms/${room.id}/chat`, { text, nonce: nonce.current })); setText(''); nonce.current = null; }
        catch (e) { setError((e as Error).message); }
        finally { setBusy(false); }
      }}>
        {emojiOpen && <div id={pickerId} role="group" aria-label="Choose an emoji" className="mb-3 rounded-xl border border-neutral/10 bg-panel p-2"><div className="grid grid-cols-6 gap-1">{emojis.map(([emoji, label]) => <button key={label} type="button" aria-label={label} title={label} disabled={busy || text.length - ((input.current?.selectionEnd ?? text.length) - (input.current?.selectionStart ?? text.length)) + emoji.length > 300} onClick={() => insertEmoji(emoji)} className="flex min-h-10 items-center justify-center rounded-lg text-xl hover:bg-amber/10 focus-visible:outline-2 focus-visible:outline-amber disabled:opacity-30">{emoji}</button>)}</div></div>}
        <div className="flex items-center gap-2"><div className="flex min-w-0 flex-1 items-center rounded-xl border border-neutral/15 bg-input focus-within:border-amber focus-within:ring-1 focus-within:ring-amber"><button ref={emojiToggle} type="button" aria-label="Add emoji" title="Add emoji" aria-expanded={emojiOpen} aria-controls={pickerId} disabled={busy} onClick={() => setEmojiOpen(!emojiOpen)} className="flex min-h-13 w-10 shrink-0 items-center justify-center rounded-l-xl text-xl text-amber hover:bg-amber/10 focus-visible:outline-2 focus-visible:outline-amber disabled:opacity-40"><span aria-hidden="true">☺</span></button><input ref={input} aria-label="Chat message" maxLength={300} value={text} disabled={busy} onChange={e => { setText(e.target.value); nonce.current = null; }} placeholder="Message the room…" className="min-h-13 min-w-0 flex-1 bg-transparent pr-3 text-sm outline-none"/></div><ActionButton type="submit" disabled={busy || !text.trim()} className="shrink-0 !px-3 !text-xs">{busy ? 'Sending…' : 'Send'}</ActionButton></div>
        {error && <p role="alert" className="mt-2 text-xs text-danger">{error} Your message is kept so you can retry.</p>}
      </form>
    </>}
  </aside>;
}
