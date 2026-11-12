export type Analysis = {
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
      <details className="mt-3"><summary className="cursor-pointer text-xs text-muted">How this review was produced</summary>
        <p className="mt-2 text-xs leading-6 text-muted">{analysis.method}</p>
        <p className="mt-2 text-xs leading-6 text-muted">{analysis.conditions}</p>
      </details>
    </div>
  </section>;
}
