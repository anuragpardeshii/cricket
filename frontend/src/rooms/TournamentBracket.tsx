import type { RoomMatch } from './types';

export function roundLabel(round: number, final: number) {
  return round === final ? 'Final' : round === final - 1 ? 'Semi-finals' : round === final - 2 ? 'Quarter-finals' : `Round ${round}`;
}
export function TournamentBracket({ matches, league, selected, who, onSelect, compact = false }: {
  matches: RoomMatch[]; league: boolean; compact?: boolean; selected?: string; who: (id: string | null | undefined) => string; onSelect: (id: string) => void;
}) {
  const rounds = [...new Set(matches.map(m => m.round))].sort((a,b) => a-b);
  const final = rounds.at(-1) ?? 1;
  const firstCount = matches.filter(m => m.round === rounds[0]).length;
  return <section aria-label={league ? 'League fixtures' : 'Knockout bracket'} className="tournament-bracket mb-7 overflow-x-auto rounded-2xl border border-neutral/10 bg-panel/40 p-4 sm:p-6">
    <div className={league ? 'grid gap-3 sm:grid-cols-2 lg:grid-cols-3' : 'flex min-w-max justify-center gap-12'}>{(league ? [0] : rounds).map(round => <div key={round} className={league ? 'contents' : compact ? 'w-56 shrink-0' : 'w-64 shrink-0 sm:w-72'}>
      {!league && <div className="mb-3 flex items-center gap-2"><span className="size-1.5 rounded-full bg-amber"/><h3 className="text-xs font-semibold uppercase tracking-[.18em]">{roundLabel(round,final)}</h3></div>}
      <div className={league ? 'contents' : 'grid'} style={league ? undefined : {gridTemplateRows:`repeat(${firstCount * 2}, 68px)`}}>
      {matches.filter(m => league || m.round === round).map((match,index) => {
        const span = 2 ** (round - rounds[0] + 1);
        return <div key={match.id} style={league ? undefined : {gridRow:`${index * span + 1} / span ${span}`}} className={`bracket-slot relative flex items-center ${!league && round < final ? `bracket-outgoing ${index%2===0?'bracket-upper':'bracket-lower'}` : ''}`}>
          {!league && round > rounds[0] && <span aria-hidden="true" className="absolute -left-6 top-1/2 w-6 border-t border-amber/35"/>}
          <button type="button" aria-label={`${who(match.a)} versus ${who(match.b)}, ${match.status}`} aria-pressed={selected === match.id} onClick={() => onSelect(match.id)} className={`bracket-card relative w-full overflow-hidden rounded-xl border bg-panel text-left transition hover:-translate-y-0.5 hover:border-amber/60 focus-visible:outline-2 focus-visible:outline-amber ${selected===match.id?'border-amber shadow-[0_0_0_1px_var(--color-amber)]':'border-neutral/15'}`}>
            <div className="flex items-center justify-between border-b border-neutral/10 px-3 py-2 text-[10px] uppercase tracking-wider text-muted"><span className="flex items-center gap-1.5">{['live','simulating'].includes(match.status)&&<span className="size-1.5 animate-pulse rounded-full bg-success"/>}{match.status==='complete'?'Full time':match.status==='live'?'Live':match.status==='simulating'?'Preparing':'Upcoming'}</span><span>{match.forfeit?'Forfeit':league?`Match ${index+1}`:round===final?'Championship':`Match ${index+1}`}</span></div>
            {[['a','youScore'],['b','oppScore']].map(([key,score]) => {
              const id = match[key as 'a'|'b']; const won = match.status==='complete' && Boolean(id) && match.winner===id;
              return <div key={key} className={`flex items-center gap-2 px-3 py-2.5 text-xs ${won?'bg-amber/7':'text-muted'}`}>
                <span className={`inline-flex size-5 shrink-0 items-center justify-center rounded text-[10px] font-extrabold ${won?'winner-mark bg-accent-fill text-on-accent':'border border-neutral/10'}`} aria-label={won?'Winner':undefined}>{won?'W':id?'·':'?'}</span>
                <span className={`min-w-0 flex-1 truncate ${id?'font-semibold text-cream':''}`}>{who(id)}</span>
                <span key={match.scores?.[score as 'youScore'|'oppScore']} className="score-tick whitespace-nowrap font-mono text-[11px] tabular-nums text-cream">{match.scores?.[score as 'youScore'|'oppScore'] ?? '—'}</span>
              </div>;
            })}
          </button>
        </div>;
      })}</div>
    </div>)}</div>
  </section>;
}
