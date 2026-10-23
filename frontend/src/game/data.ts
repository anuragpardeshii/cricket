import type { Player, Role, Slot, Squad } from './types';

type PlayerSeed = Pick<Player, 'name' | 'role' | 'rating'>;
type SquadSeed = { country: string; tournament: string; players: PlayerSeed[] };
const P = (name: string, role: Role, rating: number): PlayerSeed => ({ name, role, rating });

const seeds: SquadSeed[] = [
      { country: 'INDIA', tournament: 'WORLD CUP 2011', players: [P('V Sehwag','OP',88),P('S Tendulkar','OP',96),P('G Gambhir','OP',87),P('V Kohli','BAT',89),P('S Raina','BAT',82),P('Y Singh','AR',92),P('MS Dhoni','WK',93),P('H Singh','SPIN',85),P('Z Khan','PACE',90),P('R Ashwin','SPIN',80),P('M Patel','PACE',78),P('A Nehra','PACE',77)] },
      { country: 'AUSTRALIA', tournament: 'WORLD CUP 2003', players: [P('A Gilchrist','WK',95),P('M Hayden','OP',91),P('R Ponting','BAT',96),P('D Martyn','BAT',86),P('M Bevan','BAT',88),P('D Lehmann','BAT',83),P('A Symonds','AR',87),P('I Harvey','AR',76),P('B Hogg','SPIN',79),P('B Lee','PACE',92),P('G McGrath','PACE',96),P('A Bichel','PACE',80)] },
      { country: 'WEST INDIES', tournament: 'WORLD CUP 1979', players: [P('G Greenidge','OP',90),P('D Haynes','OP',86),P('V Richards','BAT',97),P('A Kallicharran','BAT',85),P('C Lloyd','BAT',93),P('C King','BAT',78),P('D Murray','WK',78),P('B Julien','AR',77),P('A Roberts','PACE',91),P('M Holding','PACE',94),P('J Garner','PACE',93),P('C Croft','PACE',88)] },
      { country: 'SRI LANKA', tournament: 'WORLD CUP 1996', players: [P('S Jayasuriya','OP',93),P('R Mahanama','OP',78),P('A Gurusinha','BAT',80),P('A de Silva','BAT',94),P('A Ranatunga','BAT',87),P('H Tillakaratne','BAT',79),P('R Kaluwitharana','WK',82),P('K Dharmasena','SPIN',78),P('C Vaas','PACE',86),P('M Muralitharan','SPIN',92),P('P Wickramasinghe','PACE',75)] },
      { country: 'PAKISTAN', tournament: 'WORLD CUP 1992', players: [P('A Sohail','OP',84),P('R Raja','OP',82),P('J Miandad','BAT',92),P('Inzamam','BAT',88),P('S Malik','BAT',81),P('I Ahmed','BAT',77),P('Imran Khan','AR',95),P('W Akram','AR',96),P('M Khan','WK',79),P('M Ahmed','SPIN',85),P('A Javed','PACE',78)] },
      { country: 'ENGLAND', tournament: 'WORLD CUP 2019', players: [P('J Roy','OP',89),P('J Bairstow','OP',90),P('J Root','BAT',92),P('E Morgan','BAT',88),P('B Stokes','AR',95),P('C Woakes','AR',86),P('J Buttler','WK',93),P('A Rashid','SPIN',85),P('J Archer','PACE',92),P('L Plunkett','PACE',81),P('M Wood','PACE',84)] },
      { country: 'SOUTH AFRICA', tournament: 'WORLD CUP 1999', players: [P('G Kirsten','OP',85),P('H Gibbs','OP',88),P('D Cullinan','BAT',84),P('J Rhodes','BAT',82),P('H Cronje','AR',83),P('J Kallis','AR',96),P('L Klusener','AR',94),P('M Boucher','WK',81),P('S Pollock','PACE',90),P('A Donald','PACE',93),P('S Elworthy','PACE',74)] },
      { country: 'NEW ZEALAND', tournament: 'WORLD CUP 2015', players: [P('M Guptill','OP',90),P('B McCullum','OP',92),P('K Williamson','BAT',93),P('R Taylor','BAT',88),P('G Elliott','BAT',80),P('C Anderson','AR',84),P('L Ronchi','WK',78),P('D Vettori','SPIN',87),P('T Southee','PACE',88),P('T Boult','PACE',92),P('A Milne','PACE',79)] },
      { country: 'INDIA', tournament: 'WORLD CUP 1983', players: [P('S Gavaskar','OP',91),P('K Srikkanth','OP',83),P('M Amarnath','AR',87),P('Y Sharma','BAT',78),P('S Patil','BAT',80),P('Kapil Dev','AR',95),P('R Shastri','SPIN',78),P('S Kirmani','WK',80),P('R Binny','PACE',79),P('M Lal','PACE',77),P('B Sandhu','PACE',75)] },

];

export const SQUADS: Squad[] = seeds.map((squad, squadIndex) => ({
  country: squad.country,
  tournament: squad.tournament,
  players: squad.players.map((player, playerIndex) => ({
    ...player,
    id: `${squadIndex}-${playerIndex}`,
    squad: `${squad.country} ${squad.tournament.slice(-4)}`,
  })),
}));

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
