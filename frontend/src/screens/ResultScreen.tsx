import { useState } from 'react';
import { ThemeToggle } from '../theme/ThemeProvider';
import { Scorecard } from '../components/Scorecard';
import { ConfirmExit } from '../components/ConfirmExit';
import { ResultActions } from '../components/ResultActions';
import { Brand, Eyebrow, Panel } from '../components/ui';
import { useGame } from '../game/useGame';

type Game = ReturnType<typeof useGame>;

export function ResultScreen({ game }: { game: Game }) {
  const { state, actions } = game;
  const [exitOpen, setExitOpen] = useState(false);
  const result = state.match?.result;
  if (!result) return null;
  const headline = result.winner === 'tie' ? 'MATCH TIED' : result.winner === 'you' ? 'YOU WIN' : `${state.opponentName} WINS`;
  const shareText = `OUT. — ${result.winner === 'tie' ? 'Match tied' : `${result.winner === 'you' ? 'I' : state.opponentName} won ${result.margin}`}\nYOU ${result.yourScore} vs ${state.opponentName} ${result.opponentScore}\nPlayer of the match: ${result.mvp.name} (${result.mvp.line})`;
  return <main className="mx-auto min-h-dvh w-full max-w-4xl px-4 pb-6 pt-5 sm:px-8">
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-neutral/10 pb-4"><Brand /><div className="flex items-center gap-4"><Eyebrow>Match result</Eyebrow><button type="button" className="text-sm text-muted hover:text-cream" onClick={() => setExitOpen(true)}>Exit</button><ThemeToggle /></div></header>
    <ConfirmExit open={exitOpen} busy={game.busy} description="Return to the home screen? Your completed match result will be preserved." cancelLabel="Back to result" onCancel={() => setExitOpen(false)} onConfirm={actions.reset}/>
    <Panel className="my-4 overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-4"><h1 className="text-2xl font-black tracking-tight sm:text-3xl">{headline}</h1><p className="text-xs text-muted sm:text-sm">{result.winner === 'tie' ? 'Scores level' : `Won ${result.margin}`}</p></div>
      <div className="grid divide-y divide-neutral/10 border-t border-neutral/10 sm:grid-cols-3 sm:divide-x sm:divide-y-0">{[['Player of the match', result.mvp], ['Highest scorer', result.highestScorer], ['Best bowler', result.bestBowler]].map(([label, award]) => typeof award === 'object' && award && <div key={String(label)} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-3 sm:block"><p className="text-[10px] uppercase tracking-wide text-amber">{String(label)}</p><p className="text-sm font-bold sm:mt-1">{award.name}</p><p className="text-xs text-muted sm:mt-1">{award.line}</p></div>)}</div>
    </Panel>
    <ResultActions text={shareText} busy={game.busy} onExit={() => setExitOpen(true)} onPlayAgain={() => { void actions.startPractice(); }}/>
    {state.match?.scorecards && <Scorecard cards={state.match.scorecards} names={{you:'YOU',opp:state.opponentName}}/>}
    {state.toast && <p className="mt-3 text-sm text-danger" role="status">{state.toast}</p>}
  </main>;
}
