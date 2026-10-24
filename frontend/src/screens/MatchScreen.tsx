import { Scorecard } from '../components/Scorecard';
import { FeedbackToggle } from '../components/GameFeedback';
import { useState } from 'react';
import { TeamBar } from '../components/TeamBar';
import { TeamFormation } from '../components/TeamFormation';
import { PracticeExit } from '../components/PracticeExit';
import { ThemeToggle } from '../theme/ThemeProvider';
import { ActionButton, Brand, Eyebrow, Panel } from '../components/ui';
import { useGame } from '../game/useGame';
import { CommentaryFeed } from '../rooms/CommentaryFeed';

type Game = ReturnType<typeof useGame>;

export function MatchScreen({ game }: { game: Game }) {
  const [preview,setPreview]=useState<string|null>(null);
  const { state, actions } = game;
  const [cards,setCards]=useState(false);
  const visibleCards=state.match?.timeline[state.timelineIndex-1]?.scorecards??[];
  const phase = state.matchDone ? 'FULL TIME' : `INNINGS ${state.innings}`;
  return <main className="relative mx-auto flex min-h-dvh w-full max-w-5xl flex-col px-5 pb-8 pt-6 sm:px-8 lg:px-12 lg:pt-9">
    {state.wicketPulse && <div className="wicket-flash pointer-events-none absolute inset-0 z-20" aria-hidden="true" />}
    <header className="flex flex-wrap gap-y-3 items-center justify-between border-b border-neutral/10 pb-5"><Brand /><div className="flex max-w-full flex-wrap items-center justify-end gap-3"><Eyebrow>{phase}</Eyebrow>{!state.matchDone&&<PracticeExit busy={game.busy} onExit={actions.exitMatch}/>}<FeedbackToggle/><ThemeToggle /></div></header>
    <TeamBar members={[{id:'you',name:'You',xi:state.yourXI},{id:'ai',name:'AI',xi:state.opponentXI,is_ai:true}]} selectedId={preview??undefined} yourId="you" onPreview={id=>setPreview(id===preview?null:id)}/>
    {preview&&<Panel className="mb-5 p-5"><button className="mb-4 text-sm text-amber" onClick={()=>setPreview(null)}>Close team preview</button><TeamFormation name={preview==='you'?'You':'AI'} xi={preview==='you'?state.yourXI:state.opponentXI} order={preview==='you'?state.order:undefined}/></Panel>}
    <div className="mt-3 flex gap-2" aria-label="Match views">{[false,true].map(show=><button key={String(show)} aria-pressed={cards===show} onClick={()=>setCards(show)} className={`rounded-lg border px-3 py-2 text-xs ${cards===show?'border-amber text-amber':'border-neutral/15 text-muted'}`}>{show?'Scorecard':'Highlights'}</button>)}</div>
    {cards?<div className="mt-4">{visibleCards.length?<Scorecard cards={visibleCards} live={!state.matchDone}/>:<p className="text-sm text-muted">Waiting for the first over…</p>}</div>:<div className="grid flex-1 gap-6 pt-4 lg:grid-cols-[minmax(0,.9fr)_minmax(0,1fr)]">
      <section>
        <Eyebrow>Match centre · T20</Eyebrow>
        <h1 className="mt-2 text-3xl font-black tracking-tight">LIVE SIMULATION</h1>
        <Panel className="mt-6 overflow-hidden">
          {([['you', 'YOU', state.yourScore], ['opp', state.opponentName, state.opponentScore]] as const).map(([side, name, score], index) => <div key={side} className={`flex items-center gap-3 p-5 ${index === 0 ? 'border-b border-neutral/10' : ''}`}>
            <span className={`size-2 shrink-0 rounded-full ${state.batting === side && !state.matchDone ? 'animate-pulse bg-amber' : 'border border-neutral/25'}`} />
            <span className="text-lg font-extrabold">{name}</span>
            <span className={`ml-auto text-right font-mono text-lg font-semibold sm:text-xl ${state.batting === side || state.matchDone ? 'text-cream' : 'text-cream/50'}`} aria-live="polite">{score}</span>
          </div>)}
        </Panel>
        <div className="mt-7"><div className="flex items-center justify-between"><Eyebrow>Momentum</Eyebrow><Eyebrow className="text-amber">{state.matchDone ? 'FINAL' : state.batting === 'you' ? 'YOU BATTING' : `${state.opponentName} BATTING`}</Eyebrow></div>
          <div className="mt-3 flex h-20 items-end gap-1 overflow-hidden border-b border-neutral/10" aria-label="Runs per over chart">
            {state.bars.map((bar, index) => <span key={index} className={`max-w-5 min-w-1 flex-1 rounded-t-sm transition-all duration-300 ${bar.wicket ? 'bg-wicket' : bar.runs >= 12 ? 'bg-amber' : 'bg-cream/30'}`} style={{ height: `${Math.max(6, Math.min(75, bar.runs * 3.5 + 6))}px` }} title={`Over ${index + 1}: ${bar.runs} runs${bar.wicket ? ', wicket' : ''}`} />)}
          </div>
        </div>
      </section>
      <CommentaryFeed entries={state.match?.timeline.slice(0,state.timelineIndex)??[]} live={!state.matchDone} showScores={false}/>
    </div>}
    <div className="mt-8 flex justify-end">{state.matchDone ? <ActionButton onClick={actions.showResult} className="w-full sm:w-auto sm:min-w-64">View result</ActionButton> : <ActionButton onClick={actions.skipMatch} variant="outline" className="w-full sm:w-auto sm:min-w-64">Skip to result</ActionButton>}</div>
  </main>;
}
