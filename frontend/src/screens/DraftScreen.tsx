import { PlayerRating } from '../components/PlayerRating';
import { Dice } from '../components/Dice';
import { useState } from 'react';
import { TeamFormation } from '../components/TeamFormation';
import { TeamBar } from '../components/TeamBar';
import { PracticeExit } from '../components/PracticeExit';
import { CountryFlag } from '../components/CountryFlag';
import { ThemeToggle } from '../theme/ThemeProvider';
import { Brand, Eyebrow, Panel, ActionButton } from '../components/ui';
import { ROLE_LABELS, SLOTS } from '../game/data';
import { useGame } from '../game/useGame';

type Game = ReturnType<typeof useGame>;

export function DraftScreen({ game }: { game: Game }) {
  const { state, actions, rerollsLeft, noFit, isPickable } = game;
  const [previewId, setPreview] = useState<string | null>(null);
  const preview = previewId ?? (state.turn === 'opp' ? 'ai' : 'you');
  const selected = state.rolled?.players.find((player) => player.id === state.selectedId);
  const yourTurn = state.turn === 'you';
  return <main className="mx-auto min-h-dvh w-full max-w-7xl px-5 pb-10 pt-6 sm:px-8 lg:px-12 lg:pt-9">
    <header className="flex flex-wrap gap-y-3 items-center justify-between border-b border-neutral/10 pb-5"><Brand /><div className="flex max-w-full flex-wrap items-center justify-end gap-3"><Eyebrow>Pick {Math.min(state.pickNumber, 22)} / 22</Eyebrow><PracticeExit busy={game.busy} onExit={actions.exitMatch}/><ThemeToggle /></div></header>
    <TeamBar members={[{id:'you',name:'You',xi:state.yourXI},{id:'ai',name:'AI',xi:state.opponentXI,is_ai:true}]} currentId={state.turn==='done'?undefined:state.turn==='opp'?'ai':'you'} selectedId={preview} yourId="you" onPreview={setPreview}/>

    <div className="grid gap-8 pt-7 lg:grid-cols-[minmax(0,1fr)_minmax(340px,.83fr)] lg:gap-12">
      <section className="min-w-0">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <span className={`size-2.5 rounded-full ${yourTurn ? 'animate-pulse bg-amber' : state.turn === 'done' ? 'bg-amber' : 'bg-neutral/40'}`} />
          <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl" aria-live="polite">{state.turn === 'done' ? 'BOTH XIs LOCKED' : yourTurn ? 'YOUR PICK' : `${state.opponentName} PICKING`}</h1>
          <div className="ml-auto flex items-center gap-2"><Eyebrow>Rerolls</Eyebrow>{Array.from({ length: 3 }, (_, i) => <span key={i} className={`size-2 rounded-full ${i < rerollsLeft ? 'bg-amber' : 'bg-neutral/15'}`} />)}</div>
        </div>
        <p className="mt-3 max-w-lg text-sm leading-6 text-muted">Roll a World Cup squad, choose one player, then place them in a compatible XI slot.</p>

        <div className="mt-7 min-h-28">
          {yourTurn && (!state.rolled || state.rolling) && <button disabled={game.busy} onClick={() => actions.rollSquad()} aria-live="polite" className="flex min-h-32 w-full items-center justify-center gap-6 rounded-2xl border border-amber/50 bg-amber/5 text-xl font-black tracking-widest text-amber transition hover:bg-amber/10 focus-visible:outline-2 focus-visible:outline-amber disabled:cursor-wait"><Dice rolling={state.rolling}/>{state.rolling ? 'ROLLING…' : 'ROLL SQUAD'}</button>}
          {state.rolled && yourTurn && !state.rolling && <Panel className="overflow-hidden">
            <div className="flex flex-wrap items-center gap-2 border-b border-neutral/10 p-4 sm:p-5"><h2 className="text-xl font-black sm:text-2xl"><CountryFlag country={state.rolled.country}/> {state.rolled.country}</h2><span className="font-mono text-xs tracking-wider text-amber">{state.rolled.tournament}</span><button onClick={() => actions.rollSquad(true)} disabled={rerollsLeft === 0 && !noFit} className="ml-auto rounded-lg border border-amber/50 px-3 py-2 font-mono text-[10px] tracking-wider text-amber transition hover:bg-amber/10 disabled:cursor-not-allowed disabled:border-neutral/10 disabled:text-muted/50">{noFit ? 'NO FITS · FREE REROLL' : 'REROLL'}</button></div>
            <div className="max-h-80 overflow-y-auto">
              {state.rolled.players.map((player) => {
                const available = isPickable(player);
                return <button key={player.id} onClick={() => { setPreview('you'); actions.selectPlayer(player); }} disabled={!available} aria-pressed={state.selectedId === player.id} className={`flex w-full items-center gap-3 border-b border-neutral/5 px-4 py-3 text-left last:border-0 sm:px-5 ${state.selectedId === player.id ? 'bg-amber/15' : 'hover:bg-neutral/5'} disabled:cursor-not-allowed disabled:opacity-30`}>
                  <span className={`min-w-0 flex-1 truncate text-sm font-bold sm:text-base text-cream`}>{player.name}</span>
                  <span className="rounded-full border border-neutral/15 px-2 py-1 font-mono text-[10px] tracking-wider text-cream/60">{ROLE_LABELS[player.role]}{state.taken[player.id] ? ' · TAKEN' : ''}</span>
                  <PlayerRating value={player.rating}/>
                </button>;
              })}
            </div>
          </Panel>}
          {state.opponentThinking && <Panel className="flex min-h-32 items-center justify-center gap-3 border-dashed"><span className="size-2 animate-pulse rounded-full bg-neutral/40" /><span className="text-sm text-muted">{state.opponentName} is on the clock…</span></Panel>}
          {state.turn === 'done' && <Panel className="border-amber/40 bg-amber/5 p-6 text-center"><p className="text-2xl font-black">BOTH XIs LOCKED</p><ActionButton onClick={actions.startMatch} className="mt-5 w-full">Simulate match</ActionButton></Panel>}
        </div>
        {selected && <p className="mt-3 text-center font-mono text-[11px] tracking-wide text-cream" role="status">SELECT A GLOWING SLOT TO PLACE {selected.name.toUpperCase()}</p>}
        {state.toast && <p className="mt-4 rounded-xl border border-neutral/10 bg-panel px-4 py-3 font-mono text-xs leading-5 text-cream/75" role="status">{state.toast}</p>}
      </section>

      <aside className="min-w-0 lg:sticky lg:top-7 lg:self-start">
        <div className="mb-4 flex flex-wrap gap-4 text-sm"><button className="text-amber" onClick={()=>setPreview(null)}>Follow turn</button><button className="text-amber" onClick={()=>setPreview('you')}>My team</button><button className="text-amber" onClick={()=>setPreview('ai')}>Preview AI team</button></div>
        <TeamFormation key={preview} name={preview==='you'?'You':'AI'} xi={preview==='you'?state.yourXI:state.opponentXI} order={preview==='you'?state.order:undefined} editable={preview==='you'} busy={game.busy} onOrder={actions.setOrder} selectedPlayer={preview==='you'?selected:undefined} onPlace={preview==='you'?id=>{setPreview(null);actions.placePlayer(SLOTS.find(s=>s.id===id)!)}:undefined}/>
      </aside>
    </div>
  </main>;
}
