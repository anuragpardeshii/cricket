import { Trophy } from '../components/Trophy';
import { useRef, useState } from 'react';
import { Scorecard } from '../components/Scorecard';
import { ResultActions } from '../components/ResultActions';
import { Panel } from '../components/ui';
import { CommentaryFeed } from './CommentaryFeed';
import { TournamentBracket, roundLabel } from './TournamentBracket';
import { TournamentSummary } from './TournamentSummary';
import type { Room, RoomMatch } from './types';

export function TournamentView({room,busy,onExit,onPlayAgain}:{room:Room;busy:boolean;onExit:()=>void;onPlayAgain:()=>void}) {
  const {state}=room;
  const who=(id:string|null|undefined)=>state.members.find(m=>m.id===id)?.name??'TBD';
  const final=state.format==='knockout'?state.matches.at(-1):undefined;
  const shareText=[`OUT. — ${state.format} tournament`,state.champion?`Champion: ${who(state.champion)}`:'Tournament complete',final?.scores?`Final: ${who(final.a)} ${final.scores.youScore} vs ${who(final.b)} ${final.scores.oppScore}`:null,final?.result?`Won ${final.result.margin}`:null,state.award?`Player of the tournament: ${state.award.name} · ${state.award.runs} runs · ${state.award.wickets} wickets`:null].filter(Boolean).join('\n');
  const [selected,setSelected]=useState<string|null>(null);
  const [scorecardsOnly,setScorecardsOnly]=useState(()=>{try{return sessionStorage.getItem(`out-scorecards-${room.id}`)==='1'}catch{return false}});
  const matchPanel=useRef<HTMLElement>(null);
  const completed=state.matches.filter(m=>m.status==='complete');
  const available=state.matches.filter(m=>m.status!=='pending');
  const ownCompleted=completed.filter(m=>m.a===room.you||m.b===room.you);
  const lost=ownCompleted.find(m=>m.winner!==room.you);
  const selectedMatch=state.matches.find(m=>m.id===selected);
  const current=(selectedMatch&&(!scorecardsOnly||selectedMatch.status!=='pending')?selectedMatch:undefined)??state.matches.find(m=>['live','simulating'].includes(m.status)&&(m.a===room.you||m.b===room.you))??state.matches.find(m=>['live','simulating'].includes(m.status))??completed.at(-1)??state.matches[0];
  const sideBySide=!scorecardsOnly&&current?.status==='live';
  const setMode=(cards:boolean)=>{setScorecardsOnly(cards);try{sessionStorage.setItem(`out-scorecards-${room.id}`,cards?'1':'0')}catch{/* Current visit still works. */}};
  const selectMatch=(id:string)=>{setSelected(id);if(window.innerWidth<768)requestAnimationFrame(()=>matchPanel.current?.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'}))};
  const showCards=(final=false)=>{setMode(true);setSelected(final?completed.at(-1)?.id??null:ownCompleted.at(-1)?.id??completed.at(-1)?.id??null)};
  return <div className="tournament-reveal">
    {state.phase==='complete'&&<TournamentSummary room={room} who={who} onScorecards={()=>showCards(true)}/>}
    {state.phase==='complete'&&<ResultActions text={shareText} busy={busy} onExit={onExit} onPlayAgain={onPlayAgain}/>}
    {lost&&state.phase==='live'&&<div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-neutral/15 bg-panel px-4 py-3"><div><p className="text-sm font-semibold">{state.format==='knockout'?'Your tournament run is over':'Your match result is ready'}</p><p className="mt-1 text-xs leading-5 text-muted">{scorecardsOnly?'Scorecards update live as each over finishes.':'Keep spectating, or skip the live commentary and review live scorecards.'}</p></div><button onClick={()=>scorecardsOnly?setMode(false):showCards()} className="rounded-lg border border-amber/40 px-4 py-2 text-xs font-semibold text-amber">{scorecardsOnly?'Watch live tournament':'Skip to scorecards'}</button></div>}
    <div className="mb-3 flex flex-wrap items-center justify-between gap-2"><div className="flex flex-wrap items-baseline gap-x-3 gap-y-1"><h2 className="text-base font-bold">{scorecardsOnly?'Tournament scorecards':state.format==='knockout'?'Road to the trophy':'League matches'}</h2><p className="text-[11px] text-muted">{completed.length} of {state.matches.length} matches complete{state.phase==='live'?' · Live scores update automatically':''}</p></div><div className="flex rounded-lg border border-neutral/15 bg-panel p-1"><button aria-pressed={!scorecardsOnly} onClick={()=>setMode(false)} className={`rounded-md px-3 py-1.5 text-xs ${!scorecardsOnly?'bg-amber/10 font-semibold text-amber':'text-muted'}`}>{state.format==='knockout'?'Bracket':'Fixtures'}</button><button aria-pressed={scorecardsOnly} onClick={()=>setMode(true)} className={`rounded-md px-3 py-1.5 text-xs ${scorecardsOnly?'bg-amber/10 font-semibold text-amber':'text-muted'}`}>Scorecards</button></div></div>
    <div className={sideBySide?'grid items-start gap-6 lg:grid-cols-[minmax(0,1.55fr)_minmax(300px,1fr)]':undefined}>
    <div className="min-w-0">
    {!scorecardsOnly&&<>
      {state.format==='league'&&<div className="mb-5 overflow-x-auto rounded-xl border border-neutral/10 bg-panel"><table aria-label="League standings" className="w-full text-left text-xs"><thead className="bg-neutral/5 text-muted"><tr>{['Team','P','W','Pts','NRR'].map(h=><th scope="col" className="px-4 py-3" key={h}>{h}</th>)}</tr></thead><tbody>{room.standings.map((row,i)=><tr key={row.id} className="border-t border-neutral/10"><th scope="row" className="px-4 py-3 font-semibold"><span className="mr-3 text-muted">{i+1}</span>{row.name}</th><td className="px-4">{row.played}</td><td className="px-4">{row.won}</td><td className="px-4 font-bold text-amber">{row.points}</td><td className="px-4 font-mono">{row.nrr}</td></tr>)}</tbody></table></div>}
      <TournamentBracket compact={sideBySide} matches={state.matches} league={state.format==='league'} selected={current?.id} who={who} onSelect={selectMatch}/>
    </>}
    {scorecardsOnly&&<div className="mb-5 flex gap-2 overflow-x-auto pb-2" aria-label="Live and completed matches">{available.length?available.map(match=><button key={match.id} aria-pressed={current?.id===match.id} onClick={()=>selectMatch(match.id)} className={`min-w-44 shrink-0 rounded-xl border px-4 py-3 text-left text-xs ${current?.id===match.id?'border-amber bg-amber/5':'border-neutral/15 bg-panel'}`}><span className="block text-[10px] uppercase tracking-wide text-muted">{state.format==='knockout'?roundLabel(match.round,Math.max(...state.matches.map(m=>m.round))):'League match'}</span><span className="mt-2 block font-semibold">{who(match.a)} vs {who(match.b)}</span><span className="mt-1 block text-muted">{match.status==='live'?'● Live':match.status==='simulating'?'Preparing match':match.result?.margin??'Match complete'}</span></button>):<p className="rounded-xl border border-dashed border-neutral/20 p-5 text-sm text-muted">Scorecards appear after the first over and update throughout each match.</p>}</div>}
    </div>
    {current&&<section ref={matchPanel} className={`min-w-0 scroll-mt-5 ${sideBySide?'lg:sticky lg:top-5':''}`} aria-label="Selected match"><MatchDetail key={current.id} match={current} who={who} scorecardsOnly={scorecardsOnly}/></section>}
    </div>
  </div>;
}

function MatchDetail({match,who,scorecardsOnly}:{match:RoomMatch;who:(id:string|null|undefined)=>string;scorecardsOnly:boolean}) {
  const live=match.status==='live';
  const complete=match.status==='complete';
  const names={you:who(match.a),opp:who(match.b)};
  const awards=[['Player of the match',match.result?.mvp],['Highest scorer',match.result?.highestScorer],['Best bowler',match.result?.bestBowler]] as const;
  return <div className="tournament-reveal">
    {!live&&<Panel className="mb-5 overflow-hidden">
      <div className="flex items-center justify-between border-b border-neutral/10 px-4 py-3"><h3 className="text-xs font-bold uppercase tracking-wider">{live?'Live match':complete?'Match result':'Next match'}</h3><span className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted">{live&&<span className="size-1.5 animate-pulse rounded-full bg-success"/>}{match.forfeit?'Forfeit':match.status}</span></div>
      <div className="grid grid-cols-2 divide-x divide-neutral/10">{[['a','youScore'],['b','oppScore']].map(([side,score])=>{
        const id=match[side as 'a'|'b'];const won=complete&&Boolean(id)&&match.winner===id;
        return <div key={side} className="min-w-0 p-4 sm:p-5"><div className="flex items-center gap-2">{won&&<span aria-label="Winner" className="winner-mark inline-flex size-5 shrink-0 items-center justify-center rounded bg-accent-fill text-[10px] font-black text-on-accent">W</span>}<p className="truncate text-sm font-semibold">{who(id)}</p></div><p key={match.scores?.[score as 'youScore'|'oppScore']} className="score-tick mt-2 font-mono text-lg font-bold sm:text-2xl">{match.scores?.[score as 'youScore'|'oppScore']??'—'}</p></div>;
      })}</div>
      {match.result&&<p className="border-t border-neutral/10 bg-amber/5 px-4 py-3 text-xs font-semibold text-cream">{match.winner?`${who(match.winner)} won ${match.result.margin}`:match.result.margin}</p>}
      {complete&&awards.some(([,award])=>award)&&<div className="grid divide-y divide-neutral/10 border-t border-neutral/10 sm:grid-cols-3 sm:divide-x sm:divide-y-0">{awards.map(([label,award])=>award&&<div className="relative px-4 py-3" key={label}>{label==='Player of the match'&&<Trophy variant="player" className="float-right ml-2 h-20 w-12"/>}<p className="text-[10px] uppercase tracking-wide text-muted">{label}</p><p className="mt-1 text-sm font-semibold">{award.name}</p><p className="mt-1 font-mono text-[11px] text-amber">{award.line}</p></div>)}</div>}
    </Panel>}
    {scorecardsOnly&&(live||complete)&&<div className="mb-5"><div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-bold">The scorebook</h3><button onClick={()=>window.print()} className="text-xs text-amber">Print / save</button></div>{match.scorecards?.length?<Scorecard cards={match.scorecards} names={names} live={live}/>:<p className="rounded-xl border border-neutral/10 bg-panel p-5 text-sm text-muted">{live?'Waiting for the first over. The scorecard updates live.':match.forfeit?'Match forfeited before a scorecard was recorded.':'No scorecard recorded.'}</p>}</div>}
    {live&&!scorecardsOnly&&<><p className="mb-3 text-sm font-semibold text-cream">{names.you} <span className="font-normal text-muted">vs</span> {names.opp}</p><CommentaryFeed entries={match.timeline??[]} names={names} live/></>}
    {complete&&!scorecardsOnly&&Boolean(match.timeline?.length)&&<details className="mb-6 rounded-xl border border-neutral/10 bg-panel p-4"><summary className="cursor-pointer text-sm font-semibold">Replay the match highlights</summary><div className="mt-5"><CommentaryFeed entries={match.timeline??[]} names={names} live={false}/></div></details>}
    {match.status==='pending'&&<div className="rounded-xl border border-dashed border-neutral/20 p-6 text-sm text-muted">The next chapter awaits. Teams will be confirmed when the preceding matches finish.</div>}
    {match.status==='simulating'&&<div role="status" className="rounded-xl border border-dashed border-amber/30 p-6 text-sm text-muted"><span className="mr-2 inline-block size-2 animate-pulse rounded-full bg-amber"/>Preparing the full match. Live scores will begin automatically.</div>}
  </div>;
}
