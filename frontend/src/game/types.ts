import type { ScorecardData } from '../components/Scorecard';
export type Role = 'OP' | 'BAT' | 'AR' | 'WK' | 'PACE' | 'SPIN';
export type Side = 'you' | 'opp';
export type Screen = 'landing' | 'lobby' | 'draft' | 'match' | 'result';

export interface Player {
  id: string;
  name: string;
  role: Role;
  rating: number;
  squad: string;
}

export interface Squad {
  country: string;
  tournament: string;
  players: Player[];
}

export interface Slot {
  id: string;
  label: string;
  accepts: Role[];
}

export type XI = Partial<Record<string, Player>>;

export interface CommentaryLine {
  kind: 'wicket' | 'six' | 'four' | 'info' | 'result' | 'over';
  text: string;
}

export interface OverSummary {
  number: number;
  runs: number;
  wicket: boolean;
  lines: CommentaryLine[];
  score: string;
  balls: number;
}

export interface Innings {
  runs: number;
  wickets: number;
  balls: number;
  scoreText: string;
  overs: OverSummary[];
  battingCard: { player: Player; runs: number; balls: number }[];
  bowlingCard: { player: Player; wickets: number }[];
}

export interface MomentumBar {
  runs: number;
  wicket: boolean;
  innings: number;
}

export interface TimelineEntry {
  scorecards?: ScorecardData[];
  deliveries?: string[];
  over: string;
  kind: CommentaryLine['kind'];
  text?: string;
  lines?: CommentaryLine[];
  wicket?: boolean;
  bar?: MomentumBar;
  batting?: Side;
  innings: number;
  youScore: string;
  oppScore: string;
}

export interface FeedEntry extends CommentaryLine {
  over: string;
}

export interface MatchResult {
  winner: Side | 'tie';
  margin: string;
  highestScorer?: { name: string; line: string; side: Side };
  bestBowler?: { name: string; line: string; side: Side };
  mvp: { name: string; line: string; side: Side };
  yourScore: string;
  opponentScore: string;
}

export interface MatchPlan {
  scorecards?: ScorecardData[];
  timeline: TimelineEntry[];
  result: MatchResult;
  firstBatting: Side;
}
