export type Analysis = {
  collapses?: {side:string;lines:string[]}[];
  cricketFact?: {title:string;lines:string[];source:string}|null;
  decisive: string; method: string; conditions: string;
  venue: { name: string; city: string; fact: string; source: string; condition: string };
  teams: { side: string; name: string; outcome: string; summary?: string; notes: string[]; details?: string[];
    players: { name: string; squad: string; rating: number; note?: string; source?: string | null }[] }[];
};

export function MatchReview({ analysis }: { analysis?: Analysis }) {
  if (!analysis) return null;
  return <section aria-label="Match analysis" className="my-5 rounded-2xl border border-amber/25 bg-panel p-5">
    <p className="text-xs uppercase tracking-wider text-amber">Inside the result</p>
    <h3 className="mt-2 text-xl font-bold">Match breakdown</h3>
    <p className="mt-3 text-sm leading-7">{analysis.decisive}</p>
    {!!analysis.collapses?.length && <div className="mt-4 space-y-3">{analysis.collapses.map(fact => <div key={fact.side} className="rounded-xl border-l-2 border-amber bg-amber/5 px-4 py-3"><p className="mb-1 text-xs font-semibold text-amber">The collapse</p>{fact.lines.map(line => <p key={line} className="text-sm leading-6">{line}</p>)}</div>)}</div>}
    <div className="mt-5 grid gap-4 md:grid-cols-2">{analysis.teams.map(team => {
      const details = [...team.notes.slice(2), ...(team.details ?? [])];
      return <article key={team.side} className="rounded-xl border border-neutral/15 p-4">
        <h4 className="font-bold">{team.name} · {team.outcome}</h4>
        {team.summary && <p className="mt-3 text-sm leading-6">{team.summary}</p>}
        {team.notes.slice(0, 2).map(note => <p key={note} className="mt-3 text-sm leading-6 text-muted">{note}</p>)}
        {details.length > 0 && <details className="mt-4">
          <summary className="cursor-pointer text-sm text-amber">Scorecard details & team composition</summary>
          {details.map((note, i) => <p key={i} className="mt-3 text-xs leading-6 text-muted">{note}</p>)}
        </details>}
      </article>;
    })}</div>
    <div className="mt-5 border-t border-neutral/15 pt-4">
      <h4 className="font-bold">{analysis.venue.name}, {analysis.venue.city}</h4>
      <p className="mt-2 text-sm text-muted">{analysis.venue.fact} <a href={analysis.venue.source} target="_blank" rel="noreferrer" className="text-amber underline">Venue source ↗</a></p>
      {analysis.cricketFact && <details className="mt-3"><summary className="cursor-pointer text-xs text-amber">From real cricket · {analysis.cricketFact.title}</summary>
        {analysis.cricketFact.lines.map(line => <p key={line} className="mt-2 text-xs leading-6 text-muted">{line}</p>)}
        <a href={analysis.cricketFact.source} target="_blank" rel="noreferrer" className="text-xs text-amber underline">ICC match report ↗</a>
        <p className="mt-2 text-xs text-muted">Historical context, not evidence for this simulated result.</p>
      </details>}
      <details className="mt-3"><summary className="cursor-pointer text-xs text-muted">How this review was produced</summary>
        <p className="mt-2 text-xs leading-6 text-muted">{analysis.method}</p>
        <p className="mt-2 text-xs leading-6 text-muted">{analysis.conditions}</p>
      </details>
    </div>
  </section>;
}
