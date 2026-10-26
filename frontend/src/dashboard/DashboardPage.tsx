import { ThemeToggle } from '../theme/ThemeProvider';
import { Select } from '../components/Select';
import { UserManagement } from './UserManagement';
import { useEffect, useState } from 'react';
import { api, ApiError, type BrowserSession } from '../api';
import { Brand, Panel } from '../components/ui';
import { ActivityBars, DonutChart } from './charts';
import type { TrendPoint, Segment } from './data';
type Stats={community?:{returningPlayers:number;practiceResultsViewed:number;groupsCreated:number;groupJoins:number;cupsStarted:number;cupsCompleted:number;achievementShares:number;rematchesCompleted:number};totalRegistered:number;newRegistrations:number;activePlayers:number;sessions:number;draftStarts:number;matchesFinished:number;rooms:number;liveRooms:number;trend:TrendPoint[];devices:Segment[];audience:Segment[];popular:{name:string;picks:number}[]};
export function DashboardPage(){
 const [days,setDays]=useState('30'); const [stats,setStats]=useState<Stats|null>(null); const [error,setError]=useState('');
 const [authorized,setAuthorized]=useState(false);
 useEffect(()=>{
  let active=true;setStats(null);setError('');
  const load=async()=>{
   try {
    const account=await api<BrowserSession>('/auth/me');
    if(!active)return;
    if(!account.user?.is_admin){setAuthorized(false);window.location.replace('/');return;}
    setAuthorized(true);
    const data=await api<Stats>(`/admin/analytics?days=${days}`);
    if(active)setStats(data);
   } catch(e) {
    if(!active)return;
    if(e instanceof ApiError && (e.status===401 || e.status===403)){
     setAuthorized(false);window.location.replace('/');return;
    }
    setError((e as Error).message);
   }
  };
  void load();return()=>{active=false};
 },[days]);
 if(!authorized)return <main className="mx-auto max-w-7xl p-6 sm:p-12"><p role={error?'alert':'status'} className="text-muted">{error||'Loading…'}</p>{error&&<a href="/" className="mt-4 inline-block text-amber">Home</a>}</main>;
 return <main className="mx-auto max-w-7xl p-6 sm:p-12"><header className="flex items-center justify-between gap-4"><a href="/"><Brand/></a><ThemeToggle/></header><div className="my-10 flex flex-wrap justify-between gap-4"><div><p className="text-amber">ADMIN / ANALYTICS</p><h1 className="text-4xl font-black">Overview.</h1></div><Select label="Time period" hideLabel className="w-44 self-end" value={days} onChange={setDays} options={['7','30','90'].map(d=>({value:d,label:`${d} days`}))}/></div>
 {error?<Panel className="p-8"><p role="alert">{error}</p><a href="/login" className="text-amber">Sign in with an administrator account</a></Panel>:!stats?<p>Loading analytics…</p>:<>
 <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">{[['Registered players',stats.totalRegistered],['New registrations',stats.newRegistrations],['Active participants',stats.activePlayers],['Sessions started',stats.sessions],['Drafts started',stats.draftStarts],['Matches completed',stats.matchesFinished],['Online rooms',stats.rooms],['Live tournaments',stats.liveRooms]].map(([label,value])=><Panel key={label} className="p-5"><p className="text-sm text-muted">{label}</p><p className="mt-4 text-4xl font-bold text-amber">{value}</p></Panel>)}</div>
 {stats.community&&<Panel className="mt-6 p-6"><h2 className="text-xl font-bold">Reasons to return</h2><div className="mt-5 grid grid-cols-2 gap-5 lg:grid-cols-4">{[['Players completing matches on 2+ UTC days',stats.community.returningPlayers],['Completed rematch games',stats.community.rematchesCompleted],['Practice results viewed',stats.community.practiceResultsViewed],['Groups created',stats.community.groupsCreated],['Invitation joins',stats.community.groupJoins],['Cups started',stats.community.cupsStarted],['Cups completed',stats.community.cupsCompleted],['Achievement share links requested',stats.community.achievementShares]].map(([label,value])=><div key={label}><p className="text-2xl font-bold text-amber">{value}</p><p className="mt-2 text-xs text-muted">{label}</p></div>)}</div><p className="mt-5 text-xs leading-6 text-muted">Completed play excludes forfeits and survives room cleanup. Practice counts after the result is viewed. Return play counts separate UTC dates within this window, not a retention percentage. These measures begin with durable match tracking; historical deleted rooms cannot be reconstructed.</p></Panel>}
 <div className="mt-6"><ActivityBars points={stats.trend} periodLabel={`Last ${days} days · UTC`}/></div><div className="mt-6 grid gap-6 md:grid-cols-2"><DonutChart title="Devices" subtitle="Recorded sessions" segments={stats.devices} totalLabel={String(stats.sessions)}/><DonutChart title="Player audience" subtitle="Guest and registered sessions" segments={stats.audience} totalLabel={String(stats.sessions)}/></div>
 <div className="mt-6 grid gap-6 md:grid-cols-2"><Panel className="p-6"><h2 className="text-xl font-bold">Popular squads</h2>{stats.popular.length?stats.popular.map(s=><div key={s.name} className="mt-4"><div className="flex justify-between"><span>{s.name}</span><span>{s.picks} picks</span></div><div className="mt-2 h-2 rounded bg-amber" style={{width:`${s.picks/Math.max(...stats.popular.map(p=>p.picks))*100}%`}}/></div>):<p className="mt-4 text-muted">No picks in this period.</p>}</Panel><Panel className="p-6"><h2 className="text-xl font-bold">Activity funnel</h2>{[['Sessions',stats.sessions],['Drafts',stats.draftStarts],['Completed matches',stats.matchesFinished]].map(([name,value])=><div className="mt-6 flex justify-between" key={name}><span>{name}</span><strong>{value}</strong></div>)}<p className="mt-6 text-xs text-muted">Tournaments can generate several matches per draft. Session/device tracking begins with this release. Referral acquisition is not collected. Recent-event analysis is capped at 50,000 events.</p></Panel></div><UserManagement/></>}
 </main>
}
