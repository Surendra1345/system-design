import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

interface Group { lesson: string; title: string; items: string[] }

export function Handbook() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [q, setQ] = useState("");
  useEffect(() => { api<Group[]>("GET", "/api/breaks").then(setGroups); }, []);
  const needle = q.toLowerCase();
  const rows = groups.flatMap(g => g.items.map(text => ({ g, text })))
    .filter(r => !needle || (r.text.replace(/<[^>]+>/g, "") + " " + r.g.title).toLowerCase().includes(needle));
  return (
    <>
      <h1>Edge-case handbook</h1>
      <p className="sub">Every "what breaks" note from every lesson in one list. Use it as a checklist when you design or review a system.</p>
      <input className="search" type="search" style={{ maxWidth: 480 }} placeholder="Filter, for example retry, cache, lock, duplicate" aria-label="Filter edge cases" value={q} onChange={e => setQ(e.target.value)} />
      <p className="lead" style={{ marginTop: 14 }}>{rows.length ? `${rows.length} edge cases` : "No edge cases match. Try a different word."}</p>
      {rows.map((r, i) => (
        <div className="bk-item" key={i}><Link to={`/lesson/${r.g.lesson}`}>{r.g.title}</Link><p dangerouslySetInnerHTML={{ __html: r.text }} /></div>
      ))}
    </>
  );
}
