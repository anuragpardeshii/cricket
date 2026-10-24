import type { XI } from '../game/types';
export type TeamMember = { id: string; name: string; xi: XI; order?: string[]; is_ai?: boolean; departed?: boolean; forfeited?: boolean; kickVotes?: number; voted?: boolean };
export function TeamBar({ members, currentId, selectedId, yourId, onPreview, onVote, required = 0, busy = false }: {
  members: TeamMember[]; currentId?: string; selectedId?: string; yourId: string; onPreview: (id: string) => void; onVote?: (id: string) => void; required?: number; busy?: boolean;
}) {
  return <section aria-label="Teams in this game" className="team-switcher my-3 flex w-full gap-1.5">{members.map((member,index) => {
    const current=member.id===currentId;
    const selected=member.id===selectedId;
    return <div key={member.id} data-current={current} data-selected={selected} className={`team-chip relative flex min-w-0 items-center rounded-lg border bg-panel ${current?'border-success':selected?'border-amber/60':'border-neutral/15'}`}>
      <button type="button" aria-pressed={selected} aria-current={current?'step':undefined} aria-label={`Preview ${member.name} team`} title={`${member.name}${member.id===yourId?' (you)':''} · ${Object.keys(member.xi).length}/11${current?' · Picking now':''}`} onClick={() => onPreview(member.id)} className="team-chip-button flex h-10 min-w-0 flex-1 items-center gap-2 px-2 text-left text-xs focus-visible:outline-2 focus-visible:outline-amber">
        {current&&<span aria-label={`${member.name}’s turn`} className="size-1.5 shrink-0 rounded-full bg-success"/>}
        <span className="team-short font-bold" aria-hidden="true">{member.is_ai?'A':member.name.charAt(0)}{member.name.match(/\d+/)?.[0]??index+1}</span>
        <span className="team-full min-w-0 flex-1 truncate font-bold">{member.name}{member.id===yourId?' (you)':''}</span>
        <span className="team-count shrink-0 font-mono text-[10px] text-muted">{member.forfeited?'Out':`${Object.keys(member.xi).length}/11`}</span>
      </button>
      {onVote&&!member.is_ai&&!member.departed&&member.id!==yourId&&<button type="button" aria-label={`Vote to kick ${member.name}`} title={`${member.kickVotes??0}/${required} votes to remove · ${member.voted?'Your vote is recorded':'One vote per person'}`} disabled={busy||member.voted} onClick={()=>onVote(member.id)} className="team-vote mr-1 size-7 shrink-0 rounded text-sm text-danger hover:bg-danger/10 disabled:opacity-40">×</button>}
    </div>;
  })}</section>;
}
