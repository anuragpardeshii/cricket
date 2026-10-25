import { useTurnFeedback, useWinFeedback } from '../components/GameFeedback';
import type { Competition } from './types';
import { useEffect, useRef, useState } from 'react';
import { SLOTS } from './data';
import { api, type Account, type BrowserSession } from '../api';
import type { FeedEntry, MatchPlan, MomentumBar, Player, Screen, Side, Slot, Squad, XI } from './types';

interface GameState {
  competition?: Competition;
  edition?: number | null;
  screen: Screen;
  opponentName: string;
  opponentJoined: boolean;
  turn: Side | 'done';
  pickNumber: number;
  rerollsUsed: number;
  rolling: boolean;
  rollName: string;
  rolled: Squad | null;
  selectedId: string | null;
  order?: string[];
  abandoned?: boolean;
  yourXI: XI;
  opponentXI: XI;
  taken: Record<string, boolean>;
  recentSquads: string[];
  opponentThinking: boolean;
  toast: string | null;
  match: MatchPlan | null;
  timelineIndex: number;
  feed: FeedEntry[];
  bars: MomentumBar[];
  innings: number;
  yourScore: string;
  opponentScore: string;
  batting: Side | null;
  wicketPulse: boolean;
  matchDone: boolean;
}

const freshState = (): GameState => ({
  competition: 't20', edition: null, screen: 'landing', opponentName: 'AI', opponentJoined: false,
  turn: 'you', pickNumber: 1, rerollsUsed: 0,
  rolling: false, rollName: '', rolled: null, selectedId: null,
  yourXI: {}, opponentXI: {}, taken: {}, recentSquads: [], opponentThinking: false,
  toast: null, match: null, timelineIndex: 0, feed: [], bars: [], innings: 1,
  yourScore: '—', opponentScore: '—', batting: null, wicketPulse: false,
  matchDone: false,
});

const countXI = (xi: XI) => SLOTS.filter((slot) => Boolean(xi[slot.id])).length;
const fits = (xi: XI, role: Player['role']) => SLOTS.some((slot) => !xi[slot.id] && slot.accepts.includes(role));
const pickable = (state: GameState, player: Player) => !state.taken[player.id] && fits(state.yourXI, player.role);

export function useGame() {
  const [state, setState] = useState<GameState>(freshState);
  const current = useRef(state);
  const timeouts = useRef<Set<ReturnType<typeof setTimeout>>>(new Set());
  const rollInterval = useRef<ReturnType<typeof setInterval> | null>(null);

  const update = (patch: Partial<GameState>) => {
    current.current = { ...current.current, ...patch };
    setState(current.current);
  };
  const schedule = (fn: () => void, delay: number) => {
    const id = setTimeout(() => { timeouts.current.delete(id); fn(); }, delay);
    timeouts.current.add(id);
  };
  const clearTimers = () => {
    timeouts.current.forEach(clearTimeout);
    timeouts.current.clear();
    if (rollInterval.current) clearInterval(rollInterval.current);
    rollInterval.current = null;
  };

  useEffect(() => () => {
    timeouts.current.forEach(clearTimeout);
    if (rollInterval.current) clearInterval(rollInterval.current);
  }, []);

  const reset = () => { if (pending.current) return; clearTimers(); sessionStorage.removeItem('out-game'); saved.current = null; setOpponentCount(0); update(freshState()); };
  type SavedGame = { id: string; version: number; state: Partial<GameState>; opponentCount: number };
  const saved = useRef<SavedGame | null>(null);
  useTurnFeedback(state.screen==='draft'&&state.turn==='you',saved.current?`${saved.current.id}:${state.pickNumber}`:undefined);
  useWinFeedback(state.matchDone&&state.match?.result.winner==='you'?saved.current?.id:undefined);
  const pending = useRef(false);
  const [busy, setBusy] = useState(false);
  const [account, setAccount] = useState<Account | null>(null);
  const [ready, setReady] = useState(false);
  const [opponentCount, setOpponentCount] = useState(0);
  const load = (game: SavedGame) => {
    saved.current = game; sessionStorage.setItem('out-game', game.id); setOpponentCount(game.opponentCount);
    update({ ...game.state, opponentName: 'AI', opponentJoined: true, selectedId: null,
      opponentXI: game.state.opponentXI ?? {}, opponentThinking: game.state.turn === 'opp', rolling: false });
  };
  useEffect(() => { let active = true;
    api<BrowserSession>('/auth/me').then(async a => {
      if (!active) return;
      setAccount(a.user ? { user: a.user, csrf: a.csrf } : null);
      const id = sessionStorage.getItem('out-game');
      if (id) {
        try { const game = await api<SavedGame>(`/games/${id}`); if (active && !game.state.abandoned) { load(game); if (game.state.match) schedule(applyEntry, 700); } else if (game.state.abandoned) sessionStorage.removeItem('out-game'); }
        catch { sessionStorage.removeItem('out-game'); }
      }
    }).catch(() => {}).finally(() => { if (active) setReady(true); });
    return () => { active = false; };
  }, []);
  const request = async (fn: () => Promise<void>) => {
    if (pending.current) return;
    pending.current = true; setBusy(true); update({ toast: null });
    try { await fn(); } catch (error) { update({ toast: (error as Error).message, rolling: false }); }
    finally { pending.current = false; setBusy(false); }
  };
  useEffect(() => {
    if (state.screen !== 'draft' || state.turn !== 'opp') return;
    let active = true; let checking = false;
    const timer = setInterval(async () => {
      const previous = saved.current;
      if (pending.current || checking || !previous) return;
      checking = true;
      try {
        const game = await api<SavedGame>(`/games/${previous.id}`);
        if (active && !pending.current && saved.current?.id === game.id && game.version > saved.current.version) load(game);
      } catch { /* Keep the persisted turn and retry on the next poll. */ }
      finally { checking = false; }
    }, 750);
    return () => { active = false; clearInterval(timer); };
  }, [state.screen, state.turn]);
  const startPractice = () => request(async () => {
    if (!account) await api<BrowserSession>('/auth/guest', {});
    const game = await api<SavedGame>('/games', {});
    clearTimers();
    update(freshState());
    load(game);
  });
  const mutate = async (action: string, extra = {}, apply = true) => {
    if (!saved.current) throw new Error('Start a practice game first');
    try {
      const game = await api<SavedGame>(`/games/${saved.current.id}/actions`, { action, version: saved.current.version, ...extra });
      if (apply) load(game); return game;
    } catch (error) {
      load(await api<SavedGame>(`/games/${saved.current.id}`));
      throw error;
    }
  };
  const rerollsLeft = Math.max(0, 3 - state.rerollsUsed);
  const noFit = Boolean(state.rolled && !state.rolled.players.some(player => pickable(state, player)));
  const rollSquad = (_reroll = false) => request(async () => {
    update({ rolling: true, selectedId: null });
    const game = await mutate('roll', {}, false);
    load(game);
  });
  const selectPlayer = (player: Player) => { if (!busy && current.current.turn === 'you' && pickable(current.current, player)) update({ selectedId: player.id }); };
  const placePlayer = (slot: Slot) => request(async () => { await mutate('pick', { player_id: current.current.selectedId, slot_id: slot.id }); });

  const applyEntry = () => {
    const now = current.current;
    if (now.screen !== 'match' || !now.match || now.timelineIndex >= now.match.timeline.length) {
      if (now.screen === 'match') update({ matchDone: true, screen: 'result' });
      return;
    }
    const entry = now.match.timeline[now.timelineIndex];
    const additions: FeedEntry[] = [
      ...(entry.text ? [{ over: entry.over, kind: entry.kind, text: entry.text }] : []),
    ];
    const previousBar = now.bars.at(-1);
    update({
      timelineIndex: now.timelineIndex + 1,
      feed: [...additions.reverse(), ...now.feed].slice(0, 60),
      bars: entry.bar ? [...(previousBar && previousBar.innings !== entry.bar.innings ? [] : now.bars), entry.bar] : now.bars,
      batting: entry.batting ?? now.batting,
      innings: entry.innings,
      yourScore: entry.youScore,
      opponentScore: entry.oppScore,
      wicketPulse: Boolean(entry.wicket),
    });
    if (entry.wicket) schedule(() => update({ wicketPulse: false }), 450);
    schedule(applyEntry, 1000);
  };

  const startMatch = () => request(async () => {
    const game = await mutate('match');
    update({ screen: 'match', match: game.state.match, timelineIndex: 0, feed: [], bars: [], innings: 1,
      yourScore: '—', opponentScore: '—', batting: game.state.match?.firstBatting, matchDone: false });
    schedule(applyEntry, 700);
  });

  const skipMatch = () => {
    const now = current.current;
    if (!now.match) return;
    clearTimers();
    const last = now.match.timeline.at(-1)!;
    const feed = now.match.timeline.flatMap((entry) => [
      ...(entry.text ? [{ over: entry.over, kind: entry.kind, text: entry.text }] : []),
    ]).reverse().slice(0, 60);
    const bars = now.match.timeline.map((entry) => entry.bar).filter((bar): bar is MomentumBar => Boolean(bar));
    update({ timelineIndex: now.match.timeline.length, feed, bars: bars.filter((bar) => bar.innings === 2),
      batting: last.batting ?? now.batting, innings: 2, yourScore: last.youScore,
      opponentScore: last.oppScore, matchDone: true, wicketPulse: false, screen: 'result' });
  };

  return {
    state, busy, account, ready,
    rerollsLeft,
    noFit,
    yourCount: countXI(state.yourXI),
    opponentCount,
    isPickable: (player: Player) => pickable(state, player),
    actions: {
      logout: () => request(async () => { await api('/auth/logout', {}); window.location.assign('/login'); }),
      reset, startPractice, rollSquad, selectPlayer, placePlayer, startMatch,
      skipMatch,
      setOrder: (order: string[]) => request(async () => { await mutate('formation', { order }); }),
      exitMatch: () => request(async () => {
        await mutate('exit'); clearTimers(); sessionStorage.removeItem('out-game'); saved.current = null; setOpponentCount(0); update(freshState());
      }),
      showResult: () => update({ screen: 'result' }),
    },
  };
}
