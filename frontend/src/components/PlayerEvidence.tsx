import type { Player } from '../game/types';
export function PlayerEvidence({player}:{player?:Player}){
 if(!player)return null;
 return <div className="my-3 rounded-xl border border-neutral/15 bg-panel p-3 text-xs leading-6"><strong>{player.name} · {player.squad} · Rating {player.rating}</strong><p className="text-muted">{player.ratingEvidence?.note??'Existing game estimate; no verified season statistics are attached to this card.'}</p>{player.ratingEvidence?.source&&<a className="text-amber underline" target="_blank" rel="noreferrer" href={player.ratingEvidence.source}>View season evidence ↗</a>}</div>
}
