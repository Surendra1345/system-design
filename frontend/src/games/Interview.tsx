import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import { Takeaways } from "../components/Explain";
import { Stars } from "../components/Stars";
import type { InterviewResult } from "../types";

interface Prompt { title: string; prompt: string; criteria: string[]; tips: string[]; ai: boolean }

/** An interview round: write your answer, then an AI interviewer (or a simple keyword check) grades it against a rubric. */
export function Interview({ lessonId, level, takeaways }: { lessonId: string; level: number; takeaways?: string[] }) {
  const q = `?level=${level}`;
  const { loggedIn, refresh } = useAuth();
  const [p, setP] = useState<Prompt | null>(null);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<InterviewResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    setP(null); setAnswer(""); setResult(null); setErr("");
    api<Prompt>("GET", `/api/games/${lessonId}/interview${q}`).then(setP);
  }, [lessonId, q]);

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      setResult(await api<InterviewResult>("POST", `/api/games/${lessonId}/interview/submit${q}`, { answer }));
      void refresh();
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Could not grade your answer."); }
    finally { setBusy(false); }
  };

  if (!p) return <p className="muted">Loading the question...</p>;
  return (
    <div className="gm">
      <div className="gm-head"><div><h2>{p.title}</h2><p>{p.prompt}</p></div></div>
      <div className="card">
        <div className="vl">What the interviewer is looking for</div>
        <ul className="crit">{p.criteria.map((c, i) => <li key={i}>{c}</li>)}</ul>
        {p.tips.length > 0 && <small className="muted">Tip: {p.tips.join(" ")}</small>}
      </div>
      <label className="field" style={{ marginTop: 12 }}>
        Your answer
        <textarea value={answer} onChange={e => setAnswer(e.target.value)} maxLength={4000} rows={9} disabled={!!result}
          placeholder="Write it the way you would say it in an interview. Explain your reasoning, not just the names." />
        <small className="muted">{answer.length} / 4000 characters</small>
      </label>
      {err && <div className="err" role="alert">{err}</div>}
      {!loggedIn && <div className="banner info"><Link to="/account">Log in</Link> to submit your answer and earn stars.</div>}
      {!result && (
        <div className="row2">
          <button className="btn pri" onClick={submit} disabled={busy || !loggedIn || answer.trim().length < 20}>{busy ? "Grading..." : "Submit my answer"}</button>
          <small className="muted">{p.ai ? "An AI interviewer will grade this." : "AI grading is off, so a simple keyword check will grade this."}</small>
        </div>
      )}
      {result && (
        <div className="card result" style={{ textAlign: "left" }}>
          <div style={{ textAlign: "center" }}><h2>{result.score}% of the points covered</h2><Stars n={result.stars} big />
            {result.xpGained > 0 && <p><span className="pill ok">+{result.xpGained} XP</span></p>}</div>
          <ul className="points">{result.points.map(pt => (
            <li key={pt.id} className={pt.hit ? "hit" : "miss"}><b>{pt.hit ? "Covered" : "Missed"}.</b> {pt.point}<small>{pt.comment}</small></li>
          ))}</ul>
          <p><b>Feedback.</b> {result.feedback}</p>
          <Takeaways items={takeaways} />
          <small className="muted">Graded by {result.graded_by === "ai" ? "the AI interviewer" : "a keyword check"}.</small>
          <div className="row2" style={{ marginTop: 10 }}><button className="btn" onClick={() => { setResult(null); }}>Revise my answer</button></div>
        </div>
      )}
    </div>
  );
}
