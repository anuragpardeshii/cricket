import { Dice } from '../components/Dice';
import { CountryFlag } from '../components/CountryFlag';
import { PlayerRating } from '../components/PlayerRating';
import { ConfirmExit } from '../components/ConfirmExit';
import { TeamBar } from '../components/TeamBar';
import { TeamFormation } from '../components/TeamFormation';
import { ThemeToggle } from '../theme/ThemeProvider';
import { RoomEntry } from './RoomEntry';
import { useEffect, useRef, useState } from 'react';
import { api, ApiError, type BrowserSession } from '../api';
import { ActionButton, Brand, Panel } from '../components/ui';
import { TournamentView } from './TournamentView';
import type { Room } from './types';
const input='w-full rounded-xl border border-neutral/15 bg-input p-3 text-cream';
export function RoomsPage(){
 const [room,setRoom]=useState<Room|null>(null); const [ready,setReady]=useState(false); const [error,setError]=useState(''); const [busy,setBusy]=useState(false); const [name,setName]=useState('');
 const [previewId,setPreviewId]=useState<string|null>(null); const [exitOpen,setExitOpen]=useState(false); const [exitHome,setExitHome]=useState(false);
 const [editingName,setEditingName]=useState(false);
 const [rolling,setRolling]=useState(false); const [selected,setSelected]=useState<string|null>(null); const [clock,setClock]=useState(Date.now()/1000); const offset=useRef(0); const pending=useRef(false);
 const ignoredRooms=useRef(new Set<string>());
 const clearRoom=()=>{if(room)ignoredRooms.current.add(room.id);setExitOpen(false);setEditingName(false);setSelected(null);setRoom(null);setPreviewId(null);sessionStorage.removeItem('out-online-room')};
 const handleError=(e:unknown)=>{setError((e as Error).message);if(e instanceof ApiError && (e.status===403||e.status===404))clearRoom()};
 const load=(r:Room)=>{if(ignoredRooms.current.has(r.id))return;offset.current=r.serverTime-Date.now()/1000;setRoom(current=>current?.id===r.id&&current.version>r.version?current:r);sessionStorage.setItem('out-online-room',r.id)};
 useEffect(()=>{let active=true;(async()=>{try{let identity:BrowserSession;try{identity=await api<BrowserSession>('/auth/me')}catch{identity=await api<BrowserSession>('/auth/guest',{})}if(!active)return;setName(current=>current||identity.user?.username||'');const id=sessionStorage.getItem('out-online-room');if(id){try{const r=await api<Room>(`/rooms/${id}`);if(active)load(r)}catch{sessionStorage.removeItem('out-online-room')}}}catch(e){if(active)setError((e as Error).message)}finally{if(active)setReady(true)}})();return()=>{active=false}},[]);
 useEffect(()=>{if(!room)return;let active=true;let timer:ReturnType<typeof setTimeout>;const poll=async()=>{if(!active)return;try{if(!pending.current){const r=await api<Room>(`/rooms/${room.id}`);if(active)load(r)}}catch(e){if(active)handleError(e)}finally{if(active)timer=setTimeout(poll,2000)}};timer=setTimeout(poll,2000);return()=>{active=false;clearTimeout(timer)}},[room?.id]);
 useEffect(()=>{const timer=setInterval(()=>setClock(Date.now()/1000+offset.current),500);return()=>clearInterval(timer)},[]);
 const send=async(path:string,body:unknown,delay=0)=>{if(pending.current)return;pending.current=true;setBusy(true);setError('');try{const [response]=await Promise.all([api<Room>(path,body),new Promise(resolve=>setTimeout(resolve,delay))]);load(response);setSelected(null)}catch(e){handleError(e);if(room){try{load(await api<Room>(`/rooms/${room.id}`))}catch{ /* Keep the actionable original error. */ }}}finally{pending.current=false;setBusy(false)}};
 const act=(action:string,extra={})=>room&&send(`/rooms/${room.id}/actions`,{action,version:room.version,...extra});
 const rollSquad=async()=>{if(!room||pending.current)return;setRolling(true);setSelected(null);try{await send(`/rooms/${room.id}/actions`,{action:'roll',version:room.version},window.matchMedia('(prefers-reduced-motion: reduce)').matches?100:1400)}finally{setRolling(false)}};
 const exitRoom=async()=>{if(!room||pending.current)return;pending.current=true;setBusy(true);try{if(room.state.phase!=='complete')await api(`/rooms/${room.id}/exit`,{});clearRoom();setExitOpen(false);if(exitHome||room.state.phase==='complete')window.location.assign('/')}catch(e){handleError(e)}finally{pending.current=false;setBusy(false)}};
 const playAgain=async()=>{
  if(!room||room.state.phase!=='complete'||pending.current)return;
  pending.current=true;setBusy(true);setError('');
  try{
   const next=await api<Room>('/rooms',{visibility:room.visibility,format:room.state.format,capacity:room.state.capacity,pick_seconds:room.state.seconds,lobby_minutes:5});
   ignoredRooms.current.add(room.id);setPreviewId(null);setSelected(null);setEditingName(false);load(next);
   window.scrollTo({top:0,behavior:'instant'});
  }catch(e){setError((e as Error).message)}finally{pending.current=false;setBusy(false)}
 };
 const state=room?.state; const turn=state?.members[state.turn]; const yours=room&&turn?.id===room.you; const player=state?.rolled?.players.find(p=>p.id===selected); const who=(id:string|null|undefined)=>state?.members.find(m=>m.id===id)?.name??'TBD';
 const preview=state?.members.find(m=>m.id===(previewId??turn?.id))??turn;

 const rerollsLeft=Math.max(0,3-(turn?.rerollsUsed??0));
 useEffect(()=>{setSelected(null)},[room?.id,state?.turn,state?.taken.length]);
 const left=Math.max(0,Math.ceil((state?.phase==='lobby'?state.lobbyDeadline:state?.deadline??clock)-clock));
 return <main className="mx-auto max-w-7xl px-5 py-8 sm:px-8"><header className="flex flex-wrap items-center justify-between gap-4"><a href="/" onClick={e=>{if(room){e.preventDefault();setExitHome(true);setExitOpen(true)}}}><Brand/></a><div className="flex flex-wrap items-center gap-4 text-sm"><ThemeToggle/>{room?<button className="text-danger" onClick={()=>{setExitHome(false);setExitOpen(true)}}>Exit match</button>:<a href="/">Home</a>}</div></header>{error&&<p role="alert" className="my-5 rounded-xl border border-red-400/30 p-4 text-danger">{error}</p>}
 <ConfirmExit open={exitOpen} busy={busy} cancelLabel={state?.phase==='complete'?'Back to result':'Keep playing'} description={state?.phase==='complete'?'Return to the home screen? Your completed tournament results will be preserved.':['lobby','draft'].includes(state?.phase??'')?'AI will take over your drafted players and remaining turns. You will leave this room and cannot rejoin it.':'Your unfinished matches will be forfeited. Other players can continue the tournament. You cannot rejoin this room.'} onCancel={()=>setExitOpen(false)} onConfirm={()=>{void exitRoom()}}/>
 {!room?<RoomEntry ready={ready} busy={busy} send={send}/>:state&&<>
 <div className="my-8 flex flex-wrap items-center justify-between gap-4"><div><p className="text-sm uppercase text-amber">{room.visibility} · {state.format} · {state.phase}</p><h1 className="mt-2 font-mono text-4xl font-bold tracking-widest">{room.code}</h1></div><div className="text-right"><p>{state.members.length}/{state.capacity} players</p>{['lobby','draft'].includes(state.phase)&&<p className="mt-2 text-2xl font-bold text-amber" role="timer">{left}s {state.phase==='lobby'?'to join':'to pick'}</p>}</div></div>
 {['lobby','draft'].includes(state.phase)&&<TeamBar members={state.members} currentId={state.phase==='draft'?turn?.id:undefined} selectedId={preview?.id} yourId={room.you} onPreview={setPreviewId} onVote={['lobby','draft','live'].includes(state.phase)?id=>{void send(`/rooms/${room.id}/kick-vote`,{target_id:id})}:undefined} required={state.kickRequired} busy={busy}/>}
 {state.lastRemoval&&<p role="status" className="mb-4 text-sm text-muted">{state.lastRemoval.name} {state.lastRemoval.reason==='kicked'?'was removed by vote':'exited'}. {state.members.some(m=>m.name===state.lastRemoval?.name&&m.is_ai)?'AI has taken over their team.':'Their unfinished matches are forfeited.'}</p>}
 {state.phase==='lobby'&&<Panel className="mb-6 p-4">{editingName?<form className="flex flex-wrap gap-3" onSubmit={async e=>{e.preventDefault();await send(`/rooms/${room.id}/name`,{name:name.trim()});setEditingName(false)}}><label className="sr-only" htmlFor="room-name">Your name</label><input id="room-name" className={`${input} max-w-xs`} maxLength={24} value={name} onChange={e=>setName(e.target.value)} autoFocus/><ActionButton disabled={busy||!name.trim()} type="submit">Save name</ActionButton><button type="button" onClick={()=>setEditingName(false)}>Cancel</button></form>:<div className="flex items-center gap-4"><span>You are <strong>{who(room.you)}</strong></span><button className="text-sm text-amber" onClick={()=>{setName(who(room.you));setEditingName(true)}}>Edit name</button></div>}</Panel>}
 {state.phase==='lobby'&&<Panel className="p-6"><h2 className="mb-4 text-2xl font-bold">Waiting room</h2>{state.members.map(m=><p key={m.id} className="border-t border-neutral/10 py-4">🟢 {m.name} {m.id===room.you?'(you)':''}</p>)}<p className="my-5 text-muted">Share code {room.code}. Each pick has {state.seconds} seconds. {state.capacity-state.members.length} empty seat(s) will be filled by AI when the host or join timer starts the draft.</p>{room.host?<ActionButton disabled={busy} onClick={()=>act('start')}>Start match</ActionButton>:<p>Waiting for the host to start.</p>}</Panel>}
 {state.phase==='expired'&&<Panel className="p-6">This room has expired. Create a new room to play.</Panel>}
 {state.phase==='draft'&&<><h2 className="mb-4 text-2xl font-bold">{yours?'Your turn':`${turn?.name} is picking`}</h2>{state.lastPick&&<p className="mb-5 text-muted">{state.lastPick.name} picked {state.lastPick.player}{state.lastPick.is_ai?' (AI pick)':state.lastPick.automatic?' automatically (timer expired)':''}.</p>}<div className="grid items-start gap-6 lg:grid-cols-2"><div>
 <p className="mb-4 text-sm text-muted">{yours?'Roll a squad, choose a player, then select a glowing XI position.':`${turn?.name} is rolling and choosing a player.`}</p>
 {yours&&(!state.rolled||rolling)&&<button type="button" disabled={busy} onClick={()=>{void rollSquad()}} aria-live="polite" className="flex min-h-32 w-full items-center justify-center gap-6 rounded-2xl border border-amber/50 bg-amber/5 text-xl font-black tracking-widest text-amber hover:bg-amber/10 focus-visible:outline-2 focus-visible:outline-amber disabled:cursor-wait"><Dice rolling={rolling}/>{rolling?'ROLLING…':'ROLL SQUAD'}</button>}
 {!yours&&!state.rolled&&<Panel className="flex min-h-32 items-center justify-center gap-4 p-5"><Dice rolling={Boolean(turn?.is_ai)}/><p className="text-sm text-muted">{turn?.is_ai?'AI is choosing a squad…':'Waiting for the squad roll…'}</p></Panel>}
 {state.rolled&&!rolling&&<Panel className="overflow-hidden"><div className="flex flex-wrap items-center gap-3 border-b border-neutral/10 p-4"><h3 className="text-xl font-bold"><CountryFlag country={state.rolled.country}/> {state.rolled.country}</h3><span className="font-mono text-xs text-amber">{state.rolled.tournament}</span>{yours&&<button type="button" disabled={busy||rerollsLeft===0} onClick={()=>{void rollSquad()}} className="ml-auto rounded-lg border border-amber/40 px-3 py-2 text-xs text-amber hover:bg-amber/10 disabled:opacity-40">Reroll · {rerollsLeft} left</button>}</div><div className="max-h-96 overflow-y-auto">{state.rolled.players.map(p=>{
 const taken=state.taken.includes(p.id);
 const canPick=!taken&&Boolean(state.rolled?.allowedSlots[p.id]?.length);
 const reason=taken?'Taken':!canPick?'No eligible slot':null;
 return <button disabled={!yours||busy||!canPick} aria-pressed={selected===p.id} key={p.id} onClick={()=>{setSelected(p.id);setPreviewId(null)}} className={`flex w-full items-center justify-between gap-3 border-b border-neutral/10 p-3 text-left last:border-0 disabled:cursor-not-allowed ${!canPick?'opacity-45':selected===p.id?'bg-amber/15':'enabled:hover:bg-neutral/5'}`}><span className="min-w-0 flex-1"><span className={`block truncate text-sm font-bold text-cream`}>{p.name}</span>{reason&&<span className="mt-1 block text-[10px] text-muted">{reason}</span>}</span><span className="text-xs text-muted">{p.role}</span><PlayerRating value={p.rating}/></button>;
 })}</div></Panel>}
 {yours&&<p className="mt-3 text-xs text-muted">{rerollsLeft} rerolls left for your draft. Each reroll restarts your turn timer.</p>}
 </div><div><div className="mb-4 flex flex-wrap gap-4 text-sm"><button className="text-amber" aria-pressed={previewId===null} onClick={()=>setPreviewId(null)}>Follow current turn</button><button className="text-amber" aria-pressed={previewId===room.you} onClick={()=>setPreviewId(room.you)}>My team</button></div>{preview&&<TeamFormation key={preview.id} name={preview.name} xi={preview.xi} order={preview.order} editable={preview.id===room.you} busy={busy} onOrder={order=>act('formation',{order})} selectedPlayer={yours&&preview.id===room.you?player:undefined} allowedSlotIds={player?state.rolled?.allowedSlots[player.id]:undefined} onPlace={yours&&preview.id===room.you?id=>act('pick',{player_id:selected,slot_id:id}):undefined}/>}</div></div></>}
 {state.phase==='lobby'&&previewId&&preview&&<Panel className="mb-6 p-5"><button className="mb-4 text-sm text-amber" onClick={()=>setPreviewId(null)}>Close team preview</button><TeamFormation name={preview.name} xi={preview.xi} order={preview.order}/></Panel>}
 {['live','complete'].includes(state.phase)&&<TournamentView key={room.id} room={room} busy={busy} onExit={()=>{setExitHome(true);setExitOpen(true)}} onPlayAgain={()=>{void playAgain()}}/>}
 </>}
 </main>
}
