import type { XI } from '../game/types';
export type TeamMember = { id: string; name: string; xi: XI; order?: string[]; is_ai?: boolean; departed?: boolean; forfeited?: boolean; kickVotes?: number; voted?: boolean };
export function TeamBar({ members, currentId, selectedId, yourId, onPreview, onVote, required = 0, busy = false }: {
  members: TeamMember[]; currentId?: string; selectedId?: string; yourId: string; onPreview: (id: string) => void; onVote?: (id: string) => void; required?: number; busy?: boolean;
}) {
  return <section aria-label="Teams in this game" className="my-4">
    <div className="flex gap-2 overflow-x-auto py-1">{members.map(member => <div key={member.id} className={`relative flex min-w-32 shrink-0 items-center gap-3 rounded-xl border bg-panel px-3 py-2 ${selectedId === member.id ? 'border-amber bg-amber/5' : 'border-neutral/15'}`}>
      <button type="button" aria-pressed={selectedId === member.id} aria-label={`Preview ${member.name} team`} onClick={() => onPreview(member.id)} className="min-w-0 flex-1 pr-3 text-left">
        <span className="block max-w-48 truncate text-sm font-bold">{member.name} {member.id === yourId && member.name !== 'You' ? '(you)' : ''}</span>
        <span className="mt-1 block text-xs text-muted">{member.forfeited ? 'Forfeited' : member.is_ai ? 'AI team' : 'Player'} · {Object.keys(member.xi).length}/11</span>
        {member.id === currentId && <span role="img" aria-label={`${member.name}’s turn`} title={`${member.name}’s turn`} className="absolute right-2 top-2 size-2 rounded-full bg-success ring-2 ring-panel"/>}
      </button>
      {onVote && !member.is_ai && !member.departed && member.id !== yourId && <div className="text-center"><button type="button" aria-label={`Vote to kick ${member.name}`} title={member.voted ? 'Your vote is recorded' : 'Vote to remove this player'} disabled={busy || member.voted} onClick={() => onVote(member.id)} className="rounded-lg border border-danger/30 px-2 py-1 text-lg text-danger hover:bg-danger/10 disabled:opacity-40">×</button><span className="mt-1 block whitespace-nowrap text-[10px] text-muted">{member.kickVotes ?? 0}/{required} votes</span></div>}
      {member.id === yourId && onVote && <span className="text-[10px] text-muted">{member.kickVotes ?? 0}/{required} votes</span>}
    </div>)}</div>
    {onVote && <p className="mt-2 text-[11px] text-muted">Kick threshold: 50% of active human players, rounded up, or 3 votes—whichever is fewer. Each person gets one vote per target.</p>}
  </section>;
}
