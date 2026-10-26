import type { TeamMember } from '../components/TeamBar';
import type { ScorecardData } from '../components/Scorecard';
import type { MatchResult, TimelineEntry, Squad } from '../game/types';
import type { DraftRules } from '../components/DraftProgress';

export type Member = TeamMember & { rerollsUsed?: number; ready?: boolean };
export type RoomMatch = {
  id: string; round: number; a: string | null; b: string | null; status: string;
  sources?: string[]; winner?: string | null; forfeit?: boolean;
  result?: MatchResult; scores?: { youScore: string; oppScore: string };
  scorecards?: ScorecardData[]; timeline?: TimelineEntry[];
};
export type Room = {
  visibility: 'public' | 'private'; id: string; code: string; version: number; serverTime: number; you: string; host: boolean;
  state: DraftRules & {
    preset?: string | null; groupId?: string | null; cupId?: string | null; rematchCode?: string;
    rolled?: Squad & { allowedSlots: Record<string, string[]>; unavailableIds?: string[] } | null;
    phase: string; format: string; capacity: number; competition?: string; edition?: number | null; seconds: number; deadline: number;
    members: Member[]; turn: number; draftRevision?: number; taken: string[]; matches: RoomMatch[]; champion: string | null; kickRequired: number;
    lastRemoval?: { name: string; reason: string };
    award?: { name: string; team: string; runs: number; wickets: number } | null;
    lastPick?: { name: string; player: string; automatic: boolean; is_ai?: boolean };
  };
  standings: { id: string; name: string; played: number; won: number; points: number; nrr: number }[];
};
