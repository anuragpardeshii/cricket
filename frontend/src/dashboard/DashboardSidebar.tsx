import { useEffect, useState } from 'react';
import { Brand, Eyebrow } from '../components/ui';

const navigation = [
  { href: '#overview', label: 'Overview' },
  { href: '#activity', label: 'Activity' },
  { href: '#audience', label: 'Audience' },
  { href: '#engagement', label: 'Engagement' },
];

export function DashboardSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const [active, setActive] = useState(window.location.hash || '#overview');
  useEffect(() => {
    const syncActive = () => setActive(window.location.hash || '#overview');
    window.addEventListener('hashchange', syncActive);
    return () => window.removeEventListener('hashchange', syncActive);
  }, []);
  return <div className="flex h-full min-h-0 w-full flex-col px-5 py-8">
    <a href="/" className="w-fit" aria-label="OUT. home"><Brand /></a>
    <div className="mt-12"><Eyebrow>Workspace</Eyebrow><nav className="mt-5 space-y-1" aria-label="Dashboard sections">{navigation.map((item) => <a key={item.href} href={item.href} onClick={() => { setActive(item.href); onNavigate?.(); }} className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${active === item.href ? 'bg-neutral/7 font-semibold text-cream' : 'text-muted hover:bg-neutral/5 hover:text-cream'}`}><span className={`size-1.5 rounded-full ${active === item.href ? 'bg-amber' : 'bg-neutral/25'}`} />{item.label}</a>)}</nav></div>
    <div className="mt-auto rounded-xl border border-neutral/10 bg-raised p-4"><Eyebrow className="text-amber">OUT. Insights</Eyebrow><p className="mt-3 text-xs leading-5 text-muted">A clear view of how cricket fans play.</p><a href="/" className="mt-4 inline-flex text-xs font-semibold text-cream hover:text-amber">Open game <span className="ml-2" aria-hidden="true">↗</span></a></div>
  </div>;
}
