import { ThemeToggle } from '../theme/ThemeProvider';
import { CricketGround } from '../components/CricketGround';
import { useGame } from '../game/useGame';
import { ActionButton, Brand, Eyebrow } from '../components/ui';
import { useState } from 'react';
import { Select } from '../components/Select';
import { presetOptions } from '../community/common';

type Game = ReturnType<typeof useGame>;

const steps = [
  ['01', 'Fresh dice roll for every chance'],
  ['02', 'First to last. Then last to first.'],
  ['03', 'Full XIs face off. One winner.'],
];

export function LandingScreen({ game }: { game: Game }) {
  const { actions } = game;
  const [preset, setPreset] = useState(() => { const value = new URLSearchParams(location.search).get('practice'); return presetOptions.some(p => p.value === value) ? value! : ''; });
  const practiceRules = new URLSearchParams(location.search).get('draftRules') === '1' ? 1 : 2;
  return <main className="mx-auto flex min-h-dvh w-full max-w-7xl flex-col px-5 pb-7 pt-6 sm:px-8 lg:px-12 lg:pt-9">
    <header className="flex flex-wrap gap-y-3 items-center justify-between gap-4 border-b border-neutral/10 pb-5">
      <span className="hidden font-mono text-[11px] tracking-[.22em] text-muted sm:inline">CRICKET SQUAD DRAFT</span>
      <span className="sm:hidden"><Brand /></span>
      <nav aria-label="Main navigation" className="flex items-center gap-2 sm:gap-3">
        <a href="/groups" className="px-2 text-xs text-amber">Groups</a><a href="/achievements" className="px-2 text-xs text-amber">Trophies</a>
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
          Your friends. Your XI. A new cup to win.
        </p>
        <p className="mt-7 max-w-md text-sm leading-6 text-muted">Draft from cricket’s historic squads, build a rivalry with friends, and keep the trophies you earn. A fresh XI makes every rematch a new story.</p>
        <div className="mt-5 flex max-w-md flex-col gap-3 sm:flex-row lg:mt-12">
          <a href="/rooms" className="flex flex-1 items-center justify-center rounded-xl bg-accent-fill px-5 py-4 font-bold text-on-accent">Challenge a friend</a>
          <a href="/groups" className="flex flex-1 items-center justify-center rounded-xl border border-amber/40 px-5 py-4 font-bold text-amber">Your group cup ↗</a>
        </div>
        <div className="mt-6 max-w-md"><Select label="Practice while your friends are away" value={preset} onChange={setPreset} options={[{value:'',label:'Classic T20',description:'Every historical T20 World Cup squad.'},...presetOptions]}/><ActionButton onClick={()=>{void actions.startPractice(preset,practiceRules)}} disabled={!game.ready || game.busy} className="mt-3 w-full">Practice vs AI ↗</ActionButton>{practiceRules===1&&<p className="mt-2 text-xs text-muted">Practising an existing cup’s original rules: one pick per turn.</p>}</div>
        <p className="mt-4 max-w-md text-xs leading-5 text-muted">Play as a guest. Save your progress by registering before your 12-hour browser session expires.</p>
      </section>

      <CricketGround />
    </div>

    <div className="mb-6 flex gap-5 text-sm text-amber">{game.account ? <><span className="text-cream">{game.account.user.username}</span><button className="text-danger" onClick={actions.logout}>Sign out</button></> : <a href="/login">Sign in</a>}</div>
    <footer className="grid gap-3 border-t border-neutral/10 pt-6 sm:grid-cols-3 sm:gap-6">
      {steps.map(([number, label]) => <div key={number} className="flex gap-3 font-mono text-[11px] leading-5 text-muted"><span>{number}</span><span>{label}</span></div>)}
    </footer>
  </main>;
}
