import type { RoomMatch } from './types';

type Performance = { id: string; team: string; name: string; runs: number; balls: number; fours: number; sixes: number; wickets: number; conceded: number; bowled: number };
export function tournamentStats(matches: RoomMatch[]) {
  const players = new Map<string, Performance>();
  const row = (team: string, id: string, name: string) => {
    const key = `${team}:${id}`;
    if (!players.has(key)) players.set(key, {id,team,name,runs:0,balls:0,fours:0,sixes:0,wickets:0,conceded:0,bowled:0});
    return players.get(key)!;
  };
  let runs = 0, wickets = 0, sixes = 0, fours = 0;
  const completed = matches.filter(match => match.status === 'complete');
  for (const match of completed) {
    if (match.forfeit) continue;
    for (const card of match.scorecards ?? []) {
      const battingTeam = card.side === 'you' ? match.a : match.b;
      const bowlingTeam = card.side === 'you' ? match.b : match.a;
      if (!battingTeam || !bowlingTeam) continue;
      for (const batter of card.batting) {
        const p = row(battingTeam,batter.id,batter.name);
        p.runs+=batter.runs; p.balls+=batter.balls; p.fours+=batter.fours; p.sixes+=batter.sixes;
        runs+=batter.runs; fours+=batter.fours; sixes+=batter.sixes;
      }
      for (const bowler of card.bowling) {
        const p = row(bowlingTeam,bowler.id,bowler.name);
        p.wickets+=bowler.wickets; p.conceded+=bowler.runs; p.bowled+=bowler.balls; wickets+=bowler.wickets;
      }
    }
  }
  const batters = [...players.values()].filter(p=>p.balls>0 || p.runs>0).sort((a,b)=>b.runs-a.runs || a.balls-b.balls);
  const bowlers = [...players.values()].filter(p=>p.bowled>0).sort((a,b)=>b.wickets-a.wickets || (a.conceded/a.bowled)-(b.conceded/b.bowled));
  return {runs,wickets,sixes,fours,completed:completed.length,batters,bowlers};
}
