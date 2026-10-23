import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react';

export function Brand({ large = false }: { large?: boolean }) {
  return <span className={large ? 'font-sans font-black text-[clamp(5.5rem,15vw,10.5rem)] leading-[.8] tracking-[-.075em]' : 'font-sans font-black text-2xl tracking-[-.06em]'}>OUT<span className="text-amber">.</span></span>;
}

export function Eyebrow({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <span className={`font-mono text-[10px] font-medium uppercase tracking-[.24em] text-muted ${className}`}>{children}</span>;
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'outline'; children: ReactNode };

export function ActionButton({ variant = 'primary', className = '', children, ...props }: ButtonProps) {
  const base = 'inline-flex min-h-13 items-center justify-center rounded-xl px-5 text-sm font-extrabold uppercase tracking-[.08em] transition duration-150 focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-amber disabled:cursor-not-allowed disabled:opacity-40 sm:text-base';
  const color = variant === 'primary'
    ? 'bg-accent-fill text-on-accent hover:bg-accent-hover active:translate-y-px'
    : 'border border-neutral/15 bg-transparent text-cream hover:border-amber/60 hover:text-amber';
  return <button {...props} className={`${base} ${color} ${className}`}>{children}</button>;
}

export function Panel({ children, className = '', ...props }: HTMLAttributes<HTMLDivElement> & { children: ReactNode }) {
  return <div {...props} className={`rounded-2xl border border-neutral/10 bg-panel ${className}`}>{children}</div>;
}
