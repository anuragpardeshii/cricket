import { ThemeToggle } from '../theme/ThemeProvider';
import { CricketGround } from '../components/CricketGround';
import { useGame } from '../game/useGame';
import { ActionButton, Brand, Eyebrow } from '../components/ui';

type Game = ReturnType<typeof useGame>;

const steps = [
  ['01', 'Roll a historic squad each turn'],
  ['02', 'Pick one player into your XI'],
  ['03', 'Full XIs face off. One winner.'],
];

export function LandingScreen({ game }: { game: Game }) {
  const { actions } = game;
  return <main className="mx-auto flex min-h-dvh w-full max-w-7xl flex-col px-5 pb-7 pt-6 sm:px-8 lg:px-12 lg:pt-9">
    <header className="flex flex-wrap gap-y-3 items-center justify-between gap-4 border-b border-neutral/10 pb-5">
      <span className="hidden font-mono text-[11px] tracking-[.22em] text-muted sm:inline">CRICKET SQUAD DRAFT</span>
      <span className="sm:hidden"><Brand /></span>
      <nav aria-label="Main navigation" className="flex items-center gap-2 sm:gap-3">
        <ThemeToggle />
        {game.account?.user.is_admin && <a href="/dashboard" className="inline-flex min-h-10 items-center justify-center rounded-lg border border-neutral/20 px-3 font-mono text-[10px] font-semibold tracking-wider text-cream transition hover:border-amber hover:text-amber focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber">DASHBOARD</a>}
        {game.ready && !game.account && <a href="/register" className="inline-flex min-h-10 items-center justify-center rounded-lg bg-accent-fill px-3 font-mono text-[10px] font-semibold tracking-wider text-on-accent transition hover:bg-accent-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber">REGISTER</a>}
      </nav>
    </header>

    <div className="grid flex-1 items-center gap-12 py-12 lg:grid-cols-[minmax(0,1fr)_minmax(400px,.9fr)] lg:gap-16 lg:py-16">
      <section>
        <Eyebrow className="text-amber">SQUAD DRAFT · 1 V 1</Eyebrow>
        <h1 className="mt-6"><Brand large /></h1>
        <p className="landing-intro mt-7 max-w-xl text-pretty text-[clamp(1.15rem,2.2vw,1.7rem)] leading-[1.4] text-cream/70">
          Draft an XI from cricket&apos;s greatest squads. Then settle it — twenty overs, over by over.
        </p>
        <div className="mt-10 flex max-w-md flex-col gap-3 sm:flex-row lg:mt-12">
          <a href="/rooms" className="flex flex-1 items-center justify-center rounded-xl bg-accent-fill px-5 py-4 font-bold text-on-accent">Room</a>
          <ActionButton onClick={actions.startPractice} disabled={!game.ready || game.busy} className="flex-1">Practice vs AI <span aria-hidden="true" className="ml-2">↗</span></ActionButton>
        </div>
        <p className="mt-4 max-w-md text-xs leading-5 text-muted">Play against AI without signing in. Guest games stay available in this browser for 12 hours.</p>
      </section>

      <CricketGround />
    </div>

    <div className="mb-6 flex gap-5 text-sm text-amber">{game.account ? <><span className="text-cream">{game.account.user.username}</span><button className="text-danger" onClick={actions.logout}>Sign out</button></> : <a href="/login">Sign in</a>}</div>
    <footer className="grid gap-3 border-t border-neutral/10 pt-6 sm:grid-cols-3 sm:gap-6">
      {steps.map(([number, label]) => <div key={number} className="flex gap-3 font-mono text-[11px] leading-5 text-muted"><span>{number}</span><span>{label}</span></div>)}
    </footer>
  </main>;
}
