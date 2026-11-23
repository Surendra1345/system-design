import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import { Stars } from "../components/Stars";

interface Cause { id: string; text: string }
interface Symptom { id: string; text: string; value: number; threshold: number; unit: string; causes: Cause[] }
interface Measure { id: string; name: string; text: string; cost: number }
interface Pub { id: string; title: string; seed: number; story: string; budget: number; users: string; symptoms: Symptom[]; measures: Measure[]; defend: string[] }
interface Row { id: string; text: string; before: number; after: number; threshold: number; unit: string; resolved: boolean; worse: boolean }
interface Result {
  rows: Row[]; diagnosis: { id: string; correct: boolean; answer: string; explain: string }[]; cost: number; budget: number; over_budget: boolean; resolved: number; total: number; diag_right: number; score: number; stars: number;
  notes: { measure: string; note: string }[]; harms: string[];
  defense?: { stars: number; score: number; points: { id: string; point: string; hit: boolean }[]; feedback?: string } | null; xpGained?: number;
}
interface Item { id: string; title: string; blurb: string; level: string; best: number }

export function ChallengeList() {
  const [items, setItems] = useState<Item[]>([]);
  useEffect(() => { api<Item[]>("GET", "/api/challenges").then(setItems).catch(() => setItems([])); }, []);
  return (
    <>
      <h1>Unknown Problem Challenge</h1>
      <p className="sub">Can you solve what you have never seen?</p>
      <p>A system is in trouble and nobody tells you which lesson it belongs to. Work out what is really wrong, choose fixes within a budget, and see what your choices do. Every fix has a side effect, and the best answer changes with the business, so memorising one example will not be enough.</p>
      <div className="grid">
        {items.map(i => (
          <Link key={i.id} to={`/challenge/${i.id}`} className="card pathpick">
            <span className="pill blue">{i.level}</span><b>{i.title}</b><span className="muted">{i.blurb}</span>
            <small>{i.best ? <span className="stars">{"★".repeat(i.best)}<span className="off">{"★".repeat(3 - i.best)}</span></span> : "Not tried yet"}</small>
          </Link>
        ))}
      </div>
      <p className="lead">Each challenge has endless variations: the numbers, the budget and sometimes the best answer change. <Link to="/mastery">See your mastery dashboard</Link>.</p>
    </>
  );
}

export function ChallengePlay() {
  const { id = "" } = useParams();
  const [qs, setQs] = useSearchParams();
  const nav = useNavigate();
  const { loggedIn, refresh } = useAuth();
  const seed = Number(qs.get("seed") ?? 0) || 0;
  const [pub, setPub] = useState<Pub | null>(null);
  const [diag, setDiag] = useState<Record<string, string>>({});
  const [chosen, setChosen] = useState<string[]>([]);
  const [res, setRes] = useState<Result | null>(null);
  const [defense, setDefense] = useState("");
  const [saved, setSaved] = useState<Result | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    setPub(null); setDiag({}); setChosen([]); setRes(null); setSaved(null); setDefense(""); setErr("");
    api<Pub>("GET", `/api/challenges/${id}?seed=${seed}`).then(setPub).catch(() => nav("/challenge"));
  }, [id, seed]); // eslint-disable-line react-hooks/exhaustive-deps

  const cost = useMemo(() => (pub ? pub.measures.filter(m => chosen.includes(m.id)).reduce((a, m) => a + m.cost, 0) : 0), [pub, chosen]);
  if (!pub) return <p className="muted">Loading the challenge...</p>;
  const body = { seed, diagnosis: diag, measures: chosen };
  const run = async () => { setErr(""); try { setRes(await api<Result>("POST", `/api/challenges/${id}/simulate`, body)); setSaved(null); } catch (e) { setErr(e instanceof ApiError ? e.message : "Could not run it."); } };
  const submit = async () => { setErr(""); try { setSaved(await api<Result>("POST", `/api/challenges/${id}/submit`, { ...body, defense })); void refresh(); } catch (e) { setErr(e instanceof ApiError ? e.message : "Could not save."); } };
  const fresh = () => setQs({ seed: String(1 + Math.floor(Math.random() * 9000)) });
  const toggle = (mid: string) => { setChosen(c => c.includes(mid) ? c.filter(x => x !== mid) : [...c, mid]); setRes(null); };
  const ready = pub.symptoms.every(s => diag[s.id]);

  return (
    <>
      <div className="crumb"><Link to="/challenge">Unknown Problem Challenge</Link></div>
      <h1>{pub.title}</h1>
      <p className="sub">{pub.story}</p>
      <div className="row2"><span className="pill">Variation {seed}</span><button className="btn sm" onClick={fresh}>New variation</button><Link className="btn sm" to="/mastery">Mastery</Link></div>

      <h2>1. What is going wrong</h2>
      <div className="card"><ul className="notes" style={{ margin: 0 }}>{pub.symptoms.map(s => <li key={s.id}>{s.text}. <span className="muted">Target: {s.threshold}{s.unit} or better.</span></li>)}</ul></div>

      <h2>2. Diagnose each problem</h2>
      <p className="lead">Pick the most likely underlying cause. Nobody tells you which part of the system to look at.</p>
      <div className="card chdiag">
        {pub.symptoms.map(s => (
          <label key={s.id} className="labfield"><span><b>{s.text}</b></span>
            <select value={diag[s.id] ?? ""} onChange={e => { setDiag({ ...diag, [s.id]: e.target.value }); setRes(null); }}>
              <option value="">Choose the most likely cause…</option>
              {s.causes.map(c => <option key={c.id} value={c.id}>{c.text}</option>)}
            </select>
          </label>
        ))}
      </div>

      <h2>3. Choose your fixes</h2>
      <p className="lead">Every fix costs money and has a side effect. Your budget is <b>{pub.budget}</b>.</p>
      <div className={"budget" + (cost > pub.budget ? " over" : "")}><div style={{ width: `${Math.min(100, cost / pub.budget * 100)}%` }} /><span>spent {cost} of {pub.budget}{cost > pub.budget ? ": over budget" : ""}</span></div>
      <div className="grid">
        {pub.measures.map(m => (
          <label key={m.id} className={"card chfix" + (chosen.includes(m.id) ? " on" : "")}>
            <span><input type="checkbox" checked={chosen.includes(m.id)} onChange={() => toggle(m.id)} /> <b>{m.name}</b> <span className="pill">cost {m.cost}</span></span>
            <span className="muted">{m.text}</span>
          </label>
        ))}
      </div>
      <div className="row2" style={{ marginTop: 14 }}>
        <button className="btn pri" onClick={run} disabled={!ready}>{ready ? "Run the simulation" : "Diagnose every problem first"}</button>
      </div>
      {err && <p className="banner warn">{err}</p>}

      {res && (
        <section className="card result" style={{ marginTop: 18 }}>
          <h2 style={{ marginTop: 0 }}>What happened</h2>
          <Stars n={res.stars} big />
          <p>{res.resolved} of {res.total} problems fixed · diagnosed {res.diag_right} of {res.total} correctly · spent {res.cost} of {res.budget}{res.over_budget ? " (over budget)" : ""}</p>
          <div className="chrows">
            {res.rows.map(r => {
              const mx = Math.max(r.before, r.after, r.threshold) * 1.1;
              return (
                <div key={r.id} className="chrow">
                  <div><b>{r.text}</b> <span className={"pill " + (r.resolved ? "ok" : "bad")}>{r.resolved ? "fixed" : r.worse ? "worse" : "still a problem"}</span></div>
                  <div className="chbar"><i className="before" style={{ width: `${r.before / mx * 100}%` }} /><i className={"after " + (r.resolved ? "good" : "bad")} style={{ width: `${r.after / mx * 100}%` }} /><em style={{ left: `${r.threshold / mx * 100}%` }} /></div>
                  <small className="muted">before {r.before}{r.unit} → after {r.after}{r.unit} (target {r.threshold}{r.unit})</small>
                </div>
              );
            })}
          </div>
          {res.notes.length > 0 && <><h3>What each fix does</h3><ul className="notes">{res.notes.map(n => <li key={n.measure}><b>{n.measure}.</b> {n.note}</li>)}</ul></>}
          {res.harms.length > 0 && <p className="banner warn">A fix made this worse: {res.harms.join("; ")}. Every fix has a side effect.</p>}
          <h3>Your diagnosis</h3>
          <ul className="notes">{res.diagnosis.map(d => <li key={d.id} className={d.correct ? "" : "band"}><b>{d.correct ? "Right." : "Not quite."}</b> {d.answer}. <span className="muted">{d.explain}</span></li>)}</ul>
        </section>
      )}

      {res && (
        <section style={{ marginTop: 18 }}>
          <h2>4. Defend your design</h2>
          <p className="lead">In a few sentences: what did you choose, what does each fix cost or risk, and why not the others? A good answer names a trade-off. It is checked against: {pub.defend.join("; ")}.</p>
          <textarea className="search" style={{ minHeight: 120 }} placeholder="I chose … because … The risk is … I did not choose … because …" value={defense} onChange={e => setDefense(e.target.value)} />
          <div className="row2"><button className="btn pri" onClick={submit} disabled={!loggedIn}>{loggedIn ? "Save my result" : "Log in to save"}</button></div>
          {saved && (
            <div className="card result" style={{ marginTop: 12 }}>
              <b>Saved.</b> {saved.xpGained ? `+${saved.xpGained} XP.` : "No new stars this time."}
              {saved.defense && <><p className="muted" style={{ marginBottom: 4 }}>Your explanation hit {saved.defense.points.filter(p => p.hit).length} of {saved.defense.points.length} points{saved.defense.feedback ? `: ${saved.defense.feedback}` : "."}</p>
                <ul className="notes">{saved.defense.points.map(p => <li key={p.id}>{p.hit ? "✓" : "✗"} {p.point}</li>)}</ul></>}
              <div className="row2"><button className="btn" onClick={fresh}>Try a new variation</button><Link className="btn" to="/mastery">See my mastery</Link></div>
            </div>
          )}
        </section>
      )}
    </>
  );
}
