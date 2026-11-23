import { useState } from "react";
import { Html } from "./Html";
import type { Stage } from "../types";

interface Props { stages: Stage[]; tutorPrompts: string[]; onOpenLab: () => void }

/** The 10-stage path: analogy to proof, one stage at a time. Practice only, so nothing here awards XP. */
export function GuidedPath({ stages, tutorPrompts, onOpenLab }: Props) {
  const [i, setI] = useState(0);
  const [picks, setPicks] = useState<Record<number, number>>({});
  const [draft, setDraft] = useState("");
  const [shown, setShown] = useState(false);
  const st = stages[i];
  const go = (n: number) => { setI(n); setShown(false); window.scrollTo({ top: 0 }); };

  return (
    <section className="guided card" aria-label="Guided path">
      <ol className="gsteps" aria-label="Stages">
        {stages.map((s, n) => (
          <li key={s.id}><button className={"gdot" + (n === i ? " on" : n < i ? " done" : "")} aria-current={n === i ? "step" : undefined} aria-label={s.title} onClick={() => go(n)}>{n + 1}</button></li>
        ))}
      </ol>
      <h2 className="gtitle">{st.title}</h2>

      {st.body && <Html html={st.body} />}
      {st.id === "visualise" && <button className="btn pri" onClick={onOpenLab}>Open the lab</button>}

      {st.id === "math" && (
        <>
          <Html html={st.intro ?? ""} />
          <ol className="gmath">{st.steps?.map((m, n) => <li key={n}><Html html={m} /></li>)}</ol>
          <p className="gtake"><b>Remember:</b> {st.takeaway}</p>
        </>
      )}

      {(st.id === "variations" || st.id === "failures") && <ul className="notes">{st.items?.map((m, n) => <li key={n}><Html html={m} /></li>)}</ul>}

      {st.id === "alternatives" && (
        <div className="tw"><table>
          <thead><tr><th>Option</th><th>Good at</th><th>Cost</th></tr></thead>
          <tbody>{st.rows?.map((r, n) => <tr key={n}>{r.map((c, k) => <td key={k}>{c}</td>)}</tr>)}</tbody>
        </table></div>
      )}

      {st.id === "design" && (
        <>
          <p>{st.prompt}</p>
          <textarea className="gdraft" value={draft} aria-label="Your design" placeholder="Write your design here, then check it against the list." onChange={e => setDraft(e.target.value)} />
          {shown
            ? <><p><b>Did your design include these?</b></p><ul className="notes">{st.checks?.map((c, n) => <li key={n}>{c}</li>)}</ul></>
            : <button className="btn" onClick={() => setShown(true)}>Check my design</button>}
        </>
      )}

      {st.id === "proof" && (
        <>
          {st.questions?.map((q, n) => {
            const pick = picks[n];
            return (
              <div className="quiz" key={n}>
                <p style={{ margin: "0 0 6px" }}>{q.q}</p>
                {q.options.map((o, k) => (
                  <button key={k} disabled={pick !== undefined} className={"opt" + (pick !== undefined ? (k === q.answer ? " right" : k === pick ? " wrong" : "") : "")} onClick={() => setPicks(p => ({ ...p, [n]: k }))}>{o}</button>
                ))}
                {pick !== undefined && <p className="why">{pick === q.answer ? "Correct. " : "Not quite. "}{q.why}</p>}
              </div>
            );
          })}
          <p className="muted"><b>Ask the tutor:</b></p>
          <ul className="notes">{tutorPrompts.map((t, n) => <li key={n}>{t}</li>)}</ul>
        </>
      )}

      <div className="gnav">
        <button className="btn" disabled={i === 0} onClick={() => go(i - 1)}>Back</button>
        <span className="muted">Stage {i + 1} of {stages.length}</span>
        <button className="btn pri" disabled={i === stages.length - 1} onClick={() => go(i + 1)}>Next</button>
      </div>
    </section>
  );
}
