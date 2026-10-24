import type { Role, Slot } from './types';

export const SLOTS: Slot[] = [
  { id: 'op1', label: 'OPENER', accepts: ['OP'] },
  { id: 'op2', label: 'OPENER', accepts: ['OP'] },
  { id: 'n3', label: 'NO. 3', accepts: ['BAT', 'OP'] },
  { id: 'n4', label: 'NO. 4', accepts: ['BAT', 'OP'] },
  { id: 'n5', label: 'NO. 5', accepts: ['BAT', 'OP'] },
  { id: 'ar', label: 'ALL-ROUNDER', accepts: ['AR'] },
  { id: 'wk', label: 'KEEPER', accepts: ['WK'] },
  { id: 'b1', label: 'BOWLER', accepts: ['PACE', 'SPIN'] },
  { id: 'b2', label: 'BOWLER', accepts: ['PACE', 'SPIN'] },
  { id: 'b3', label: 'BOWLER', accepts: ['PACE', 'SPIN'] },
  { id: 'b4', label: 'BOWLER', accepts: ['PACE', 'SPIN'] },
];

export const ROLE_LABELS: Record<Role, string> = {
  OP: 'OPEN', BAT: 'BAT', AR: 'ALL', WK: 'WK', PACE: 'PACE', SPIN: 'SPIN',
};
