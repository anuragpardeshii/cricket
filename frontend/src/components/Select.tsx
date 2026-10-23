import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';

type Option = { value: string; label: string; selectedLabel?: string; description?: string };
type Props = { label: string; value: string; options: Option[]; onChange: (value: string) => void; className?: string; hideLabel?: boolean };

/** A keyboard accessible, single-choice menu styled to match the game. */
export function Select({ label, value, options, onChange, className = '', hideLabel = false }: Props) {
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const search = useRef({ text: '', time: 0 });
  const [open, setOpen] = useState(false);
  const [above, setAbove] = useState(false);
  const [active, setActive] = useState(0);
  const selected = Math.max(0, options.findIndex(option => option.value === value));
  const show = () => {
    const bounds = button.current?.getBoundingClientRect();
    setAbove(Boolean(bounds && window.innerHeight - bounds.bottom < 290 && bounds.top > 290));
    setActive(selected); setOpen(true);
  };
  const choose = (index: number) => { onChange(options[index].value); setOpen(false); button.current?.focus(); };
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener('pointerdown', outside);
    return () => document.removeEventListener('pointerdown', outside);
  }, [open]);
  useEffect(() => {
    if (open) document.getElementById(`${id}-${active}`)?.scrollIntoView({ block: 'nearest' });
  }, [open, active, id]);
  const keydown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const key = event.key;
    if (key === 'Tab') { setOpen(false); return; }
    if (key === 'Escape') { event.preventDefault(); setOpen(false); return; }
    if (['ArrowDown', 'ArrowUp', 'Home', 'End', 'Enter', ' '].includes(key)) {
      event.preventDefault();
      if (!open) { show(); return; }
      if (key === 'Enter' || key === ' ') { choose(active); return; }
      setActive(index => key === 'Home' ? 0 : key === 'End' ? options.length - 1 : (index + (key === 'ArrowDown' ? 1 : -1) + options.length) % options.length);
    } else if (key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      event.preventDefault();
      search.current = { text: (Date.now() - search.current.time < 700 ? search.current.text : '') + key.toLowerCase(), time: Date.now() };
      const match = options.findIndex(option => option.label.toLowerCase().startsWith(search.current.text));
      if (!open) show();
      if (match >= 0) setActive(match);
    }
  };
  return <div ref={root} className={`relative min-w-0 ${className}`} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); }}>
    <span id={`${id}-label`} className={hideLabel ? 'sr-only' : 'mb-2 block text-sm font-semibold text-cream/80'}>{label}</span>
    <button ref={button} type="button" role="combobox" aria-labelledby={`${id}-label`} aria-controls={`${id}-list`} aria-expanded={open} aria-haspopup="listbox" aria-activedescendant={open ? `${id}-${active}` : undefined} onKeyDown={keydown} onClick={() => open ? setOpen(false) : show()} className={`flex min-h-13 w-full items-center justify-between gap-3 rounded-xl border bg-input px-4 py-3 text-left text-sm text-cream transition hover:border-amber/50 focus-visible:outline-2 focus-visible:outline-amber ${open ? 'border-amber/70 ring-2 ring-amber/10' : 'border-neutral/15'}`}>
      <span className="truncate">{options[selected]?.selectedLabel ?? options[selected]?.label}</span><svg aria-hidden="true" viewBox="0 0 16 16" className={`size-4 shrink-0 text-amber transition-transform ${open ? 'rotate-180' : ''}`} fill="none"><path d="m4 6 4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
    </button>
    {open && <ul id={`${id}-list`} role="listbox" aria-labelledby={`${id}-label`} className={`absolute left-0 z-50 max-h-64 w-full min-w-60 overflow-y-auto rounded-xl border border-neutral/15 bg-raised p-1.5 theme-menu ${above ? 'bottom-full mb-2' : 'top-full mt-2'}`}>
      {options.map((option, index) => <li key={option.value} id={`${id}-${index}`} role="option" aria-selected={value === option.value} onPointerMove={() => setActive(index)} onMouseDown={event => event.preventDefault()} onClick={() => choose(index)} className={`flex cursor-pointer items-center justify-between gap-4 rounded-lg px-3 py-3 text-sm ${index === active ? 'bg-neutral/10' : ''} ${value === option.value ? 'text-amber' : 'text-cream'}`}>
        <span><span className="block font-semibold">{option.label}</span>{option.description && <span className="mt-1 block text-xs leading-5 text-muted">{option.description}</span>}</span>{value === option.value && <span aria-hidden="true">✓</span>}
      </li>)}
    </ul>}
  </div>;
}
