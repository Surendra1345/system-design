import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { GLOSSARY } from "../glossary";

export function Glossary() {
  const [q, setQ] = useState("");
  const rows = useMemo(() => {
    const n = q.trim().toLowerCase();
    return GLOSSARY.filter(t => !n || (t.term + " " + t.def).toLowerCase().includes(n)).sort((a, b) => a.term.localeCompare(b.term));
  }, [q]);
  return (
    <>
      <h1>Glossary</h1>
      <p className="sub">Every term in this course, explained in plain words.</p>
      <input className="search" type="search" style={{ maxWidth: 480 }} placeholder="Search, for example cache, queue, shard" aria-label="Search the glossary" value={q} onChange={e => setQ(e.target.value)} />
      <p className="lead">{rows.length ? `${rows.length} terms` : "No terms match. Try a different word."}</p>
      <dl className="gloss">
        {rows.map(t => (
          <div className="bk-item" key={t.term}>
            <dt><b>{t.term}</b></dt>
            <dd>{t.def}{t.lesson && <> <Link to={`/lesson/${t.lesson}`}>Learn more →</Link></>}</dd>
          </div>
        ))}
      </dl>
    </>
  );
}
