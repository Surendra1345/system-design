import type { Explain as ExplainData } from "../types";

/** Plain-English answers to: what is it, why do we use it, when should I use it, and when should I not. */
export function Explain({ e }: { e?: ExplainData }) {
  if (!e) return null;
  return (
    <section className="explain" aria-label="In plain English">
      <h3>In plain English</h3>
      <div className="ex-grid">
        <div><h4>What it is</h4><p>{e.what}</p></div>
        <div><h4>Why we use it</h4><p>{e.why}</p></div>
        <div className="ex-use"><h4>Use it when</h4><ul>{e.use.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
        {e.avoid.length > 0 && <div className="ex-avoid"><h4>Think twice when</h4><ul>{e.avoid.map((x, i) => <li key={i}>{x}</li>)}</ul></div>}
      </div>
      <p className="ex-example"><b>Real example.</b> {e.example}</p>
    </section>
  );
}

export function Takeaways({ items }: { items?: string[] }) {
  if (!items || !items.length) return null;
  return <div className="takeaways"><h4>What to remember</h4><ul>{items.map((x, i) => <li key={i}>{x}</li>)}</ul></div>;
}
