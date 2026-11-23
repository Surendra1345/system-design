import type { DeepDive as DeepData } from "../types";

const KIND: Record<string, string> = { paper: "Paper", book: "Book", docs: "Docs", blog: "Blog", talk: "Talk" };

/** Researched detail: how it works step by step, a worked example with numbers, a real case, a decision guide, mistakes and sources. */
export function DeepDive({ d }: { d?: DeepData | null }) {
  if (!d) return null;
  return (
    <section className="deep" aria-label="Go deeper">
      <h2>Go deeper</h2>

      <h3>How it works</h3>
      {d.how.map((x, i) => <div className="deep-step" key={i}><h4>{x.h}</h4><p>{x.p}</p></div>)}

      <div className="worked">
        <h3>Worked example: {d.worked.title}</h3>
        <ol>{d.worked.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
        <p className="worked-result"><b>Result.</b> {d.worked.result}</p>
      </div>

      <div className="case">
        <h3>In the real world: {d.case.who}</h3>
        <h4>{d.case.title}</h4>
        <p>{d.case.text}</p>
        {d.case.source && <small className="muted">Source: {d.case.source.url
          ? <a href={d.case.source.url} target="_blank" rel="noopener noreferrer">{d.case.source.title}</a> : d.case.source.title}</small>}
      </div>

      {d.choose.length > 1 && (
        <>
          <h3>Which one should I choose?</h3>
          <div className="tw"><table>
            <thead><tr>{d.choose[0].map((h, i) => <th key={i}>{h}</th>)}</tr></thead>
            <tbody>{d.choose.slice(1).map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody>
          </table></div>
        </>
      )}

      <h3>Common mistakes</h3>
      <ul>{d.mistakes.map((m, i) => <li key={i}>{m}</li>)}</ul>

      <h3>Keep reading</h3>
      <ul className="reading">
        {d.reading.map((r, i) => (
          <li key={i}>
            <span className="pill blue">{KIND[r.kind] ?? r.kind}</span>{" "}
            {r.url ? <a href={r.url} target="_blank" rel="noopener noreferrer">{r.title}</a> : <span>{r.title}</span>}
            <small className="muted"> by {r.by}</small>
          </li>
        ))}
      </ul>
    </section>
  );
}
