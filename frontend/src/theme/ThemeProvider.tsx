import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';

type Theme = 'dark' | 'light';
const key = 'out-theme';
const ThemeContext = createContext<{ theme: Theme; toggle: () => void } | null>(null);

function savedTheme(): Theme {
  try { return localStorage.getItem(key) === 'light' ? 'light' : 'dark'; }
  catch { return 'dark'; }
}
function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'light' ? '#f5f2e9' : '#08090b');
}
// Apply the saved choice before React's first render, including direct page visits.
export function initializeTheme() { applyTheme(savedTheme()); }

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(savedTheme);
  const transitionTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const changeTheme = (next: Theme) => {
    const root = document.documentElement;
    if (transitionTimer.current) clearTimeout(transitionTimer.current);
    if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      root.classList.add('theme-transition');
      // Establish the transition before changing the theme variables.
      void root.offsetWidth;
      transitionTimer.current = setTimeout(() => root.classList.remove('theme-transition'), 450);
    }
    applyTheme(next); setTheme(next);
  };
  useEffect(() => {
    const sync = (event: StorageEvent) => {
      if (event.key === key || event.key === null) {
        changeTheme(savedTheme());
      }
    };
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener('storage', sync);
      if (transitionTimer.current) clearTimeout(transitionTimer.current);
      document.documentElement.classList.remove('theme-transition');
    };
  }, []);
  const toggle = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    changeTheme(next);
    try { localStorage.setItem(key, next); } catch { /* The current tab still works without storage. */ }
  };
  return <ThemeContext.Provider value={{ theme, toggle }}>{children}</ThemeContext.Provider>;
}

export function ThemeToggle() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('ThemeToggle requires ThemeProvider');
  const light = context.theme === 'light';
  return <button type="button" role="switch" aria-checked={light} aria-label="Test match light theme" onClick={context.toggle} className="theme-toggle relative inline-flex size-11 shrink-0 items-center justify-center overflow-hidden rounded-full border border-neutral/20 bg-panel text-theme-icon transition hover:border-neutral/40 focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-theme-icon">
    <svg aria-hidden="true" className={`theme-icon absolute size-5 ${light ? 'theme-icon-visible' : 'theme-icon-hidden'}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.4 1.4m11.2 11.2L19 19M5 19l1.4-1.4M17.6 6.4 19 5"/></svg>
    <svg aria-hidden="true" className={`theme-icon absolute size-5 ${light ? 'theme-icon-hidden' : 'theme-icon-visible'}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20.8 13.1A9 9 0 0 1 10.9 3.2a9 9 0 1 0 9.9 9.9Z"/></svg>
  </button>;
}
