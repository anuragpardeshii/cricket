export type Competition = 'odi' | 't20' | 'ipl';
export const COMPETITIONS = [{value:'odi',label:'ODI World Cup'}, {value:'t20',label:'T20 World Cup'}, {value:'ipl',label:'IPL'}] as const;
export const competitionName = (value?: string) => COMPETITIONS.find(c=>c.value===value)?.label ?? 'Classic squads';
export const EDITIONS: Record<Competition, {value: string; label: string}[]> = {
  odi: [{value:'2023',label:'2023 · 10 teams'}, {value:'2019',label:'2019 · 10 teams'}, {value:'2015',label:'2015 · 14 teams'}, {value:'2011',label:'2011 · 14 teams'}, {value:'2007',label:'2007 · 16 teams'}, {value:'2003',label:'2003 · 14 teams'}, {value:'1999',label:'1999 · 12 teams'}, {value:'1996',label:'1996 · 12 teams'}, {value:'1992',label:'1992 · 9 teams'}],
  t20: [{value:'2026',label:'2026 · 20 teams'}, {value:'2024',label:'2024 · 20 teams'}, {value:'2022',label:'2022 · 16 teams'}, {value:'2021',label:'2021 · 16 teams'}, {value:'2016',label:'2016 · 16 teams'}, {value:'2014',label:'2014 · 16 teams'}, {value:'2012',label:'2012 · 12 teams'}, {value:'2010',label:'2010 · 12 teams'}, {value:'2009',label:'2009 · 12 teams'}, {value:'2007',label:'2007 · 12 teams'}],
  ipl: [{value:'2026',label:'2026 · 10 teams'}, {value:'2025',label:'2025 · 10 teams'}, {value:'2024',label:'2024 · 10 teams'}, {value:'2023',label:'2023 · 10 teams'}, {value:'2022',label:'2022 · 10 teams'}, {value:'2021',label:'2021 · 8 teams'}, {value:'2020',label:'2020 · 8 teams'}, {value:'2019',label:'2019 · 8 teams'}, {value:'2018',label:'2018 · 8 teams'}, {value:'2017',label:'2017 · 8 teams'}, {value:'2016',label:'2016 · 8 teams'}, {value:'2015',label:'2015 · 8 teams'}, {value:'2014',label:'2014 · 8 teams'}, {value:'2013',label:'2013 · 9 teams'}, {value:'2012',label:'2012 · 9 teams'}, {value:'2011',label:'2011 · 10 teams'}, {value:'2010',label:'2010 · 8 teams'}, {value:'2009',label:'2009 · 8 teams'}, {value:'2008',label:'2008 · 8 teams'}],
};
export const editionOptions = (competition: Competition) => [...EDITIONS[competition], {value:'all',label:'All historical editions'}];
export const poolName = (competition?: string, edition?: number | null) => `${competitionName(competition)}${edition ? ` ${edition}` : ' · All years'}`;
import type { ScorecardData } from '../components/Scorecard';
export type Role = 'OP' | 'BAT' | 'AR' | 'WK' | 'PACE' | 'SPIN';
export type Side = 'you' | 'opp';
export type Screen = 'landing' | 'lobby' | 'draft' | 'match' | 'result';

export interface Player {
  id: string;
  personId?: string;
  competition?: Competition;
  edition?: number;
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
  headline?: string;
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
