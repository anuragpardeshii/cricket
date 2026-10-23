import { SLOTS } from './data';
import type { CommentaryLine, Innings, MatchPlan, MatchResult, Player, Side, TimelineEntry, XI } from './types';

const team = (xi: XI): Player[] => SLOTS.map((slot) => xi[slot.id]).filter((p): p is Player => Boolean(p));
const bowlers = (xi: XI): Player[] => ['ar', 'b1', 'b2', 'b3', 'b4'].map((id) => xi[id]).filter((p): p is Player => Boolean(p));

export function simulateInnings(battingXI: XI, bowlingXI: XI, target?: number): Innings {
  const batters = team(battingXI);
  const bowling = bowlers(bowlingXI);
  const bowlingAverage = bowling.reduce((total, p) => total + p.rating, 0) / bowling.length;
  const battingCard = batters.map((player) => ({ player, runs: 0, balls: 0 }));
  const bowlingCard = bowling.map((player) => ({ player, wickets: 0 }));
  let runs = 0;
  let wickets = 0;
  let balls = 0;
  let striker = 0;
  let nonStriker = 1;
  let nextIn = 2;
  const overs: Innings['overs'] = [];

  for (let over = 0; over < 20; over += 1) {
    const bowler = bowlingCard[over % bowlingCard.length];
    const lines: CommentaryLine[] = [];
    let overRuns = 0;
    let wicket = false;

    for (let ball = 0; ball < 6; ball += 1) {
      if (wickets >= 10 || (target !== undefined && runs > target)) break;
      const batter = battingCard[striker];
      batter.balls += 1;
      balls += 1;
      const wicketChance = Math.min(0.095, Math.max(0.02, 0.048 + (bowlingAverage - batter.player.rating) * 0.0018));

      if (Math.random() < wicketChance) {
        wickets += 1;
        wicket = true;
        bowler.wickets += 1;
        lines.push({ kind: 'wicket', text: `OUT — ${batter.player.name.toUpperCase()} falls for ${batter.runs}. ${bowler.player.name} strikes.` });
        if (nextIn < battingCard.length) striker = nextIn++;
        continue;
      }

      const fourWeight = Math.max(2, 13 + (batter.player.rating - 85) * 0.5);
      const sixWeight = Math.max(1, 5 + (batter.player.rating - 85) * 0.35);
      const choices: [number, number][] = [[0, 30], [1, 36], [2, 9], [4, fourWeight], [6, sixWeight]];
      let draw = Math.random() * choices.reduce((total, [, weight]) => total + weight, 0);
      let scored = 0;
      for (const [value, weight] of choices) {
        draw -= weight;
        if (draw <= 0) { scored = value; break; }
      }
      runs += scored;
      overRuns += scored;
      batter.runs += scored;
      if (scored === 6) lines.push({ kind: 'six', text: `SIX. ${batter.player.name} goes big — ${batter.runs} off ${batter.balls}.` });
      if (scored === 4 && Math.random() < 0.6) lines.push({ kind: 'four', text: `FOUR. ${batter.player.name} finds the rope.` });
      if (scored % 2 === 1) [striker, nonStriker] = [nonStriker, striker];
    }

    [striker, nonStriker] = [nonStriker, striker];
    overs.push({ number: over + 1, runs: overRuns, wicket, lines, score: `${runs}/${wickets}`, balls });
    if (wickets >= 10 || (target !== undefined && runs > target)) break;
  }

  const overText = `${Math.floor(balls / 6)}.${balls % 6}`;
  return { runs, wickets, balls, overs, battingCard, bowlingCard, scoreText: `${runs}/${wickets} (${overText})` };
}

export function createMatch(yourXI: XI, opponentXI: XI, opponentName: string): MatchPlan {
  const firstBatting: Side = Math.random() < 0.5 ? 'you' : 'opp';
  const secondBatting: Side = firstBatting === 'you' ? 'opp' : 'you';
  const battingXI = (side: Side) => side === 'you' ? yourXI : opponentXI;
  const bowlingXI = (side: Side) => side === 'you' ? opponentXI : yourXI;
  const first = simulateInnings(battingXI(firstBatting), bowlingXI(firstBatting));
  const second = simulateInnings(battingXI(secondBatting), bowlingXI(secondBatting), first.runs);
  const name = (side: Side) => side === 'you' ? 'YOU' : opponentName;
  const timeline: TimelineEntry[] = [{
    over: '—', kind: 'info', text: `TOSS — ${name(firstBatting)} bat first. 20 overs a side.`,
    batting: firstBatting, innings: 1,
    youScore: firstBatting === 'you' ? '0/0' : '—',
    oppScore: firstBatting === 'opp' ? '0/0' : '—',
  }];

  const addInnings = (innings: Innings, side: Side, number: number, otherScore: string, target?: number) => {
    innings.overs.forEach((over) => {
      const score = `${over.score} (${Math.floor(over.balls / 6)}.${over.balls % 6})`;
      timeline.push({
        over: `OV ${over.number}`, kind: 'over', lines: over.lines, wicket: over.wicket,
        bar: { runs: over.runs, wicket: over.wicket, innings: number },
        batting: side, innings: number,
        youScore: side === 'you' ? score : otherScore,
        oppScore: side === 'opp' ? score : otherScore,
        text: over.lines.length ? undefined : `${over.runs} off the over. ${name(side)} ${over.score}${target === undefined ? '' : ` · need ${Math.max(0, target + 1 - parseInt(over.score, 10))}`}`,
      });
    });
  };

  addInnings(first, firstBatting, 1, '—');
  timeline.push({
    over: '—', kind: 'info', text: `INNINGS BREAK — ${name(firstBatting)} post ${first.scoreText}. Target ${first.runs + 1}.`,
    batting: secondBatting, innings: 2,
    youScore: firstBatting === 'you' ? first.scoreText : '0/0',
    oppScore: firstBatting === 'opp' ? first.scoreText : '0/0',
  });
  addInnings(second, secondBatting, 2, first.scoreText, first.runs);

  let winner: MatchResult['winner'];
  let margin: string;
  if (second.runs > first.runs) {
    winner = secondBatting;
    margin = `by ${10 - second.wickets} wickets, ${120 - second.balls} balls to spare`;
  } else if (first.runs > second.runs) {
    winner = firstBatting;
    margin = `by ${first.runs - second.runs} runs`;
  } else {
    winner = 'tie';
    margin = 'scores level';
  }

  const candidates = ([first, second] as const).flatMap((innings, index) => {
    const side = index === 0 ? firstBatting : secondBatting;
    return [
      ...innings.battingCard.map((entry) => ({ name: entry.player.name, line: `${entry.runs} (${entry.balls})`, side, value: entry.runs })),
      ...innings.bowlingCard.map((entry) => ({ name: entry.player.name, line: `${entry.wickets} wickets`, side, value: entry.wickets * 24 })),
    ];
  });
  const best = candidates.reduce((a, b) => b.value > a.value ? b : a);
  const result: MatchResult = {
    winner, margin,
    mvp: { name: best.name, line: best.line, side: best.side },
    yourScore: firstBatting === 'you' ? first.scoreText : second.scoreText,
    opponentScore: firstBatting === 'opp' ? first.scoreText : second.scoreText,
  };
  timeline.push({
    over: '—', kind: 'result', text: winner === 'tie' ? 'MATCH TIED.' : `${name(winner)} WIN ${margin.toUpperCase()}.`,
    innings: 2, youScore: result.yourScore, oppScore: result.opponentScore,
  });
  return { timeline, result, firstBatting };
}
