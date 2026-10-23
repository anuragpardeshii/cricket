import { useState } from 'react';
import { ActionButton, Eyebrow, Panel } from '../components/ui';
import { Select } from '../components/Select';
import { PublicRooms } from './PublicRooms';

type Props = { ready: boolean; busy: boolean; send: (path: string, body: unknown) => Promise<void> };
const numbered = (values: number[], unit: string) => values.map(value => ({ value: String(value), label: `${value} ${unit}` }));

export function RoomEntry({ ready, busy, send }: Props) {
  const [view, setView] = useState<'choose' | 'create' | 'join'>('choose');
  const [visibility, setVisibility] = useState('private');
  const [format, setFormat] = useState('knockout');
  const [capacity, setCapacity] = useState('4');
  const [seconds, setSeconds] = useState('30');
  const [minutes, setMinutes] = useState('5');
  const [code, setCode] = useState('');
  return <section className="mx-auto max-w-4xl pb-12 pt-12">
    {view !== 'choose' && <button className="mb-8 text-sm text-muted hover:text-amber disabled:opacity-40" disabled={busy} onClick={() => setView('choose')}>← Back to rooms</button>}
    <Eyebrow className="block text-amber">ONLINE CRICKET</Eyebrow>
    <h1 className="mb-3 mt-3 text-4xl font-black tracking-tight sm:text-5xl">{view === 'create' ? 'Your room. Your rules.' : view === 'join' ? 'Find your match.' : 'Play together.'}</h1>
    <p className="mb-9 max-w-xl leading-7 text-muted">{view === 'create' ? 'Set up your tournament, then share the code with your friends. AI teams will fill any empty seats when you start.' : view === 'join' ? 'Enter an invitation code or find an open public room below. New players can enter until the draft starts.' : 'Draft your dream XI and watch the tournament unfold. Play with friends or meet your next rival. No account required.'}</p>
    {view === 'choose' && <div className="grid gap-5 sm:grid-cols-2">
      {[{ key: 'create' as const, number: '01', title: 'Create a room', text: 'Choose your format, set the pace, and invite your rivals.', action: 'Set up a tournament' }, { key: 'join' as const, number: '02', title: 'Enter a room', text: 'Have a code? Join your friends or discover a public room.', action: 'Find a room' }].map(item => <button key={item.key} onClick={() => setView(item.key)} className="group rounded-2xl border border-neutral/15 bg-panel p-7 text-left transition hover:-translate-y-1 hover:border-amber/60 focus-visible:outline-2 focus-visible:outline-amber">
        <span className="font-mono text-xs text-amber">{item.number}</span><h2 className="mb-3 mt-7 text-2xl font-bold">{item.title}</h2><p className="min-h-14 text-sm leading-6 text-muted">{item.text}</p><span className="mt-8 flex items-center justify-between text-sm font-bold text-amber">{item.action}<span aria-hidden="true">↗</span></span>
      </button>)}
    </div>}
    {view === 'create' && <Panel className="p-6 sm:p-8"><form className="space-y-7" onSubmit={event => { event.preventDefault(); void send('/rooms', { visibility, format, capacity: Number(capacity), pick_seconds: Number(seconds), lobby_minutes: Number(minutes) }); }}>
      <div className="grid gap-6 sm:grid-cols-2">
        <Select label="Room visibility" value={visibility} onChange={setVisibility} options={[{ value: 'private', label: 'Private room', description: 'Only players with your invitation code can enter.' }, { value: 'public', label: 'Public room', description: 'Anyone can discover your room and join.' }]}/>
        <Select label="Tournament format" value={format} onChange={value => { setFormat(value); setCapacity('4'); }} options={[{ value: 'knockout', label: 'Knockout', description: 'Win to advance. One team takes the trophy.' }, { value: 'league', label: 'League', description: 'Everyone plays everyone. Lead the table to win.' }]}/>
        <Select label="Players in room" value={capacity} onChange={setCapacity} options={numbered(format === 'knockout' ? [2, 4, 8] : [2, 3, 4, 5, 6, 7, 8], 'players')}/>
        <Select label="Time per pick" value={seconds} onChange={setSeconds} options={numbered([10, 20, 30, 60, 90, 120], 'seconds')}/>
        <Select label="Time to join" value={minutes} onChange={setMinutes} options={numbered([1, 5, 10, 15, 30], 'minutes')}/>
      </div>
      <div className="rounded-xl border border-amber/15 bg-amber/5 p-4 text-sm leading-6 text-muted"><strong className="text-cream">Ready when you are.</strong> Start at any time, or let the join timer start your tournament. Empty seats become AI teams. A missed pick receives a random compatible player.</div>
      <ActionButton type="submit" disabled={!ready || busy} className="w-full sm:w-auto">{busy ? 'Creating…' : 'Create room'} <span aria-hidden="true" className="ml-4">↗</span></ActionButton>
    </form></Panel>}
    {view === 'join' && <><Panel className="p-6 sm:p-8"><h2 className="mb-5 text-xl font-bold">Enter with a room code</h2><form className="flex flex-wrap items-end gap-4" onSubmit={event => { event.preventDefault(); void send('/rooms/join', { code }); }}>
      <label className="min-w-0 flex-1 text-sm text-muted">Room code<input aria-label="Room code" autoComplete="off" spellCheck={false} value={code} maxLength={4} onChange={event => setCode(event.target.value.toUpperCase().replace(/[^A-Z2-9]/g, ''))} placeholder="ROOM CODE" className="mt-2 min-h-13 w-full rounded-xl border border-neutral/15 bg-input px-4 py-3 font-mono text-cream uppercase tracking-widest focus:border-amber focus:outline-none"/></label>
      <ActionButton type="submit" disabled={!ready || busy || code.length !== 4}>Enter room</ActionButton>
    </form><p className="mt-5 text-xs leading-6 text-muted">Already playing? Use the same account or browser to reconnect. Eliminated players can keep watching through the final.</p></Panel><PublicRooms ready={ready} busy={busy} onJoin={roomCode => { void send('/rooms/join', { code: roomCode }); }}/></>}
  </section>;
}
