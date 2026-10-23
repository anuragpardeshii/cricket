import { RoomsPage } from './rooms/RoomsPage';
import { LoginPage } from './registration/LoginPage';
import { useGame } from './game/useGame';
import { LandingScreen } from './screens/LandingScreen';
import { DraftScreen } from './screens/DraftScreen';
import { MatchScreen } from './screens/MatchScreen';
import { ResultScreen } from './screens/ResultScreen';
import { DashboardPage } from './dashboard/DashboardPage';
import { RegisterPage } from './registration/RegisterPage';

function GameApp() {
  const game = useGame();
  return <div className="min-h-dvh bg-background text-cream">
    {game.busy && !game.state.rolling && <div role="status" className="fixed bottom-5 right-5 z-50 rounded-xl bg-panel px-5 py-3 text-amber">Saving…</div>}
    {game.state.toast && game.state.screen !== 'draft' && game.state.screen !== 'result' && <p role="alert" className="mx-auto max-w-2xl p-4 text-danger">{game.state.toast}</p>}
    {game.state.screen === 'landing' && <LandingScreen game={game} />}
        {game.state.screen === 'draft' && <DraftScreen game={game} />}
    {game.state.screen === 'match' && <MatchScreen game={game} />}
    {game.state.screen === 'result' && <ResultScreen game={game} />}
  </div>;
}

export default function App() {
  const path = window.location.pathname.replace(/\/+$/, '');
  if (path === '/rooms') return <RoomsPage />;
  if (path === '/dashboard') return <DashboardPage />;
  if (path === '/login') return <LoginPage />;
  if (path === '/register') return <RegisterPage />;
  return <GameApp />;
}
