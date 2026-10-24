import { Trophy } from '../components/Trophy';
export { Trophy } from '../components/Trophy';
import { useEffect, useId, useRef, useState } from 'react';
import { ActionButton } from '../components/ui';
import type { Room } from './types';
import { tournamentStats } from './tournamentStats';

export function TournamentSummary({ room, who, onScorecards }: { room: Room; who: (id:string|null|undefined)=>string; onScorecards:()=>void }) {
  const { state } = room;
  const stats = tournamentStats(state.matches);
  const champion = room.standings.find(row=>row.id===state.champion);
  const final = state.format==='knockout' ? state.matches.at(-1) : undefined;
  const won = state.champion===room.you;
  const [open,setOpen] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null); const heading=useId(); const description=useId();
  const seen = useRef(false);
  useEffect(()=>{
    if (!won || state.phase!=='complete' || seen.current) return;
    seen.current=true;
    try { if(sessionStorage.getItem(`out-celebrated-${room.id}`))return; sessionStorage.setItem(`out-celebrated-${room.id}`,'1'); } catch { /* Still celebrate once in this visit. */ }
    setOpen(true);
  },[won,state.phase,room.id]);
  useEffect(()=>{
    if(!open)return;
    const previous=document.activeElement as HTMLElement|null;
    dialog.current?.showModal();
    return()=>{dialog.current?.close();previous?.focus()};
  },[open]);
  const award = state.award;
  return <>
    <section aria-label="Tournament results" className="tournament-reveal mb-7 overflow-hidden rounded-2xl border border-amber/30 bg-panel">
      <div className="flex flex-wrap items-center gap-5 bg-amber/5 px-5 py-6 sm:px-7"><div className="rounded-full border border-amber/30 bg-amber/10 p-3 text-amber"><Trophy/></div><div className="min-w-40 flex-1"><p className="mb-1 text-[10px] font-semibold uppercase tracking-[.22em] text-amber">{state.champion?'Tournament champion':'Tournament complete'}</p><h2 className="break-words text-2xl font-black sm:text-3xl">{state.champion?who(state.champion):'No champion'}</h2><p className="mt-2 text-xs text-muted">{champion?`${champion.won} wins · ${champion.played} matches`:`${stats.completed} completed matches`}{final?.result?` · Final won ${final.result.margin}`:''}</p></div>{won&&<button onClick={()=>setOpen(true)} className="w-full rounded-full border border-amber/40 px-4 py-2 text-xs font-semibold text-amber sm:w-auto">Celebrate your win</button>}</div>
      <div className="grid grid-cols-2 divide-x divide-neutral/10 border-y border-neutral/10 sm:grid-cols-4">{[['Matches',stats.completed],['Runs',stats.runs],['Wickets',stats.wickets],['Sixes',stats.sixes]].map(([label,value])=><div key={label} className="px-5 py-4"><p className="text-[10px] uppercase tracking-wider text-muted">{label}</p><p className="mt-1 font-mono text-xl font-semibold">{value}</p></div>)}</div>
      <div className="grid divide-y divide-neutral/10 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        <Award title="Player of the tournament" name={award?.name} team={award?who(award.team):undefined} line={award?`${award.runs} runs · ${award.wickets} wickets`:undefined}/>
        <Award title="Most runs" name={stats.batters[0]?.name} team={stats.batters[0]?who(stats.batters[0].team):undefined} line={stats.batters[0]?`${stats.batters[0].runs} runs · ${stats.batters[0].sixes} sixes`:undefined}/>
        <Award title="Most wickets" name={stats.bowlers[0]?.name} team={stats.bowlers[0]?who(stats.bowlers[0].team):undefined} line={stats.bowlers[0]?`${stats.bowlers[0].wickets} wickets · ${(stats.bowlers[0].conceded/stats.bowlers[0].bowled*6).toFixed(2)} economy`:undefined}/>
      </div>
      {state.matches.some(m=>m.forfeit)&&<p className="border-t border-neutral/10 px-5 py-2 text-[10px] text-muted">Forfeited matches count toward results; their performances are excluded from tournament totals and awards.</p>}
    </section>
    <dialog ref={dialog} aria-labelledby={heading} aria-describedby={description} onCancel={e=>{e.preventDefault();setOpen(false)}} className="victory-dialog m-auto w-[calc(100%_-_2rem)] max-h-[calc(100dvh_-_2rem)] max-w-lg overflow-y-auto rounded-3xl border border-amber/40 bg-panel p-0 text-cream shadow-2xl backdrop:bg-black/65">
      <div className="victory-halo relative px-6 pb-7 pt-6 text-center sm:px-10">
        {open&&<div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">{Array.from({length:36},(_,i)=><span key={i} className="victory-confetti absolute top-0 h-3 w-1.5 rounded-sm" style={{left:`${5+(i*37)%90}%`,animationDelay:`${i*.07}s`,opacity:.5+(i%3)*.2,background:['#ffd768','#fff1b8','#e79b28','#75a469'][i%4]}}/>)}</div>}
        <div className="victory-trophy relative mx-auto mb-4 flex h-56 items-center justify-center"><Trophy className="h-56 w-40"/></div>
        <p className="text-[10px] font-bold uppercase tracking-[.3em] text-amber">Tournament champion</p>
        <h2 id={heading} className="mt-3 text-3xl font-black sm:text-4xl">Congratulations!</h2>
        <p id={description} className="mt-3 text-sm leading-6 text-muted">{who(room.you)}, you won the {state.format} tournament.{champion?` ${champion.won} wins in ${champion.played} matches.`:''}</p>
        {final?.result&&<p className="mt-2 text-sm font-semibold">Final won {final.result.margin}</p>}
        <div className="relative my-5 rounded-xl border border-neutral/10 bg-background/50 p-3"><Trophy variant="player" className="float-left h-20 w-14"/><p className="text-[10px] uppercase tracking-wider text-amber">Player of the tournament</p><p className="mt-2 text-lg font-bold">{award?.name??'No award recorded'}</p>{award&&<p className="mt-1 text-xs text-muted">{who(award.team)} · {award.runs} runs · {award.wickets} wickets</p>}</div>
        <ActionButton autoFocus className="relative w-full" onClick={()=>{setOpen(false);onScorecards()}}>View tournament scorecards</ActionButton><button onClick={()=>setOpen(false)} className="relative mt-4 text-xs text-muted">Back to tournament</button>
      </div>
    </dialog>
  </>;
}
function Award({title,name,team,line}:{title:string;name?:string;team?:string;line?:string}) {
  return <div className="px-5 py-4"><p className="text-[10px] uppercase tracking-wider text-amber">{title}</p><p className="mt-2 text-sm font-bold">{name??'No performance recorded'}</p>{team&&<p className="mt-1 truncate text-[11px] text-muted">{team}</p>}{line&&<p className="mt-2 font-mono text-xs">{line}</p>}</div>;
}
