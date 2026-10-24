import { useEffect, useState } from 'react';
import { api, ApiError } from '../api';
import type { Competition, Squad } from '../game/types';
import { CountryFlag } from './CountryFlag';

export function SquadLibrary({ competition, edition, ready }: { competition: Competition; edition: string; ready: boolean }) {
  const [open,setOpen]=useState(false);
  const [squads,setSquads]=useState<Squad[]>([]);
  const [selected,setSelected]=useState('');
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(false);
  const [retry,setRetry]=useState(0);
  useEffect(()=>{
    if(!open || !ready) return;
    let cancelled=false;
    setLoading(true); setError(''); setSquads([]); setSelected('');
    const path=`/catalog?competition=${competition}${edition==='all'?'':`&edition=${edition}`}`;
    const fetchSquads=async()=>{
      try {return await api<{squads:Squad[]}>(path);}
      catch(error) {
        if(!(error instanceof ApiError)||error.status!==401||cancelled) throw error;
        await api('/auth/guest',{});
        return api<{squads:Squad[]}>(path);
      }
    };
    void fetchSquads().then(data=>{
      if(!cancelled) {setSquads(data.squads); setSelected(data.squads[0]?.players[0]?.squad??'');}
    }).catch(reason=>{if(!cancelled) setError(reason instanceof Error ? reason.message : 'Could not load squads.');})
      .finally(()=>{if(!cancelled) setLoading(false);});
    return ()=>{cancelled=true;};
  },[open,ready,competition,edition,retry]);
  const squad=squads.find(s=>s.players[0]?.squad===selected);
  return <div className="text-sm">
    <button type="button" disabled={!ready} aria-expanded={open} aria-controls="squad-library" onClick={()=>setOpen(v=>!v)} className="text-amber disabled:opacity-40">{open?'Hide squads':'Browse teams and players'} <span aria-hidden="true">{open?'−':'+'}</span></button>
    {open&&<div id="squad-library" className="mt-3 rounded-xl border border-neutral/15 bg-panel p-4">
      {loading&&<p role="status" className="text-muted">Loading squads…</p>}
      {error&&<p role="alert" className="text-danger">{error} <button type="button" onClick={()=>setRetry(v=>v+1)} className="text-amber">Try again</button></p>}
      {!loading&&squads.length>0&&<><label className="flex flex-wrap items-center gap-3 text-muted">View squad<select aria-label="View squad" value={selected} onChange={e=>setSelected(e.target.value)} className="min-w-0 max-w-full rounded-lg border border-neutral/20 bg-input p-2 text-cream">{squads.map(s=><option key={s.players[0].squad} value={s.players[0].squad}>{s.country} · {s.tournament.slice(-4)} · {s.players.length} players</option>)}</select></label>
      {squad&&<><p className="mb-2 mt-4 font-semibold"><CountryFlag country={squad.country}/> {squad.country} <span className="text-muted">{squad.tournament.slice(-4)}</span></p><ul className="grid max-h-56 grid-cols-1 gap-x-5 overflow-y-auto sm:grid-cols-2">{squad.players.map(p=><li key={p.id} className="flex items-center justify-between gap-3 border-b border-neutral/10 py-2"><span>{p.name}</span><span className="font-mono text-[10px] text-muted">{p.role}</span></li>)}</ul></>}
      <p className="mt-3 text-xs leading-5 text-muted">{squads.length} historical squads in this pool. Roll to draft their players. Season rosters may include replacement players. World Cups use published squad lists. Ratings are game values.</p></>}
    </div>}
  </div>;
}
