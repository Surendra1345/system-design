import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";

interface Dim { id: string; name: string; pct: number; detail: string; hint: string }
interface M { dimensions: Dim[]; weakest: Dim; challenges: { id: string; title: string; best: number }[]; attempts: number; next: { id: string; title: string }[] }

export function Mastery() {
  const { loggedIn } = useAuth();
  const [m, setM] = useState<M | null>(null);
  useEffect(() => { if (loggedIn) api<M>("GET", "/api/mastery").then(setM).catch(() => setM(null)); }, [loggedIn]);
  if (!loggedIn) return <><h1>Mastery</h1><p className="sub">Stars show you played. Mastery shows you understand.</p><p className="banner info">Log in to see your mastery. <Link to="/account">Log in or create an account</Link>.</p></>;
  if (!m) return <p className="muted">Loading...</p>;
  return (
    <>
      <h1>Your mastery</h1>
      <p className="sub">Stars show you played. Mastery shows you can explain, vary, diagnose and design.</p>
      <div className="card">
        {m.dimensions.map(d => (
          <div key={d.id} className="mrow">
            <div className="mhead"><b>{d.name}</b><span>{d.pct}%</span></div>
            <div className="bar"><i style={{ width: `${d.pct}%` }} /></div>
            <small className="muted">{d.detail}</small>
          </div>
        ))}
      </div>
      <div className="card" style={{ marginTop: 14 }}>
        <b>Needs the most work: {m.weakest.name}</b>
        <p className="muted" style={{ margin: "4px 0 0" }}>{m.weakest.hint}</p>
        {m.next.length > 0 && <p style={{ marginBottom: 0 }}>Try next: {m.next.map((n, i) => <span key={n.id}>{i ? ", " : ""}<Link to={`/lesson/${n.id}`}>{n.title}</Link></span>)}</p>}
      </div>
      <h2>Unknown problem challenges</h2>
      <div className="grid">
        {m.challenges.map(c => <Link key={c.id} to={`/challenge/${c.id}`} className="card pathpick"><b>{c.title}</b><small>{c.best ? <span className="stars">{"★".repeat(c.best)}<span className="off">{"★".repeat(3 - c.best)}</span></span> : "Not tried yet"}</small></Link>)}
      </div>
      <p className="lead">{m.attempts} challenge attempt(s) so far. Each new variation counts toward "Problem variations".</p>
    </>
  );
}
