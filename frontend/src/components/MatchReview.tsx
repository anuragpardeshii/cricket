export type Analysis = {
  sentences?: string[];
  collapses?: {side:string;lines:string[]}[];
  cricketFact?: {title:string;lines:string[];source:string}|null;
  decisive: string; method: string; conditions: string;
  venue: { name: string; city: string; fact: string; source: string; condition: string };
  teams: { side: string; name: string; outcome: string; summary?: string; notes: string[]; details?: string[];
    players: { name: string; squad: string; rating: number; note?: string; source?: string | null }[] }[];
};

export function MatchReview({ analysis }: { analysis?: Analysis }) {
  if (!analysis) return null;
  const sentences = analysis.sentences?.length === 3 ? analysis.sentences : [
    analysis.teams.find(t => t.outcome === 'Lost')?.summary ?? analysis.decisive,
    analysis.teams.find(t => t.outcome === 'Won')?.notes[0] ?? analysis.teams[0]?.notes[0] ?? '',
    analysis.venue.fact,
  ].filter(Boolean);
  return <section aria-label="Match analysis" className="my-5 rounded-2xl border border-amber/25 bg-panel p-5">
    <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="text-xs font-bold uppercase tracking-wider text-amber">Inside the result</h3><a href={analysis.venue.source} target="_blank" rel="noreferrer" className="text-xs text-muted underline underline-offset-4">{analysis.venue.name} ↗</a></div>
    <div className="mt-3 space-y-2">{sentences.map((sentence,i)=><p key={i} className="text-sm leading-7">{sentence}</p>)}</div>
  </section>;
}
