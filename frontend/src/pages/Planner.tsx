import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import { Markdown } from "../components/Markdown";

const EXAMPLES = [
  "A food delivery app for one university campus, about 5,000 students, with live order tracking and card payments.",
  "A photo sharing app where friends post pictures and follow each other. Expecting 100,000 daily users in a year.",
  "A booking system for a chain of 20 gyms with class limits, waiting lists and payments.",
];

/** Describe an app in plain words. An AI engineer proposes a starting architecture, what to add later, edge cases and a build order. */
export function Planner() {
  const { loggedIn, aiEnabled } = useAuth();
  const [idea, setIdea] = useState("");
  const [plan, setPlan] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const go = async () => {
    setBusy(true); setErr(""); setPlan("");
    try { setPlan((await api<{ plan: string }>("POST", "/api/ai/plan", { idea })).plan); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Could not make a plan."); }
    finally { setBusy(false); }
  };

  return (
    <>
      <h1>Design planner</h1>
      <p className="sub">Describe the app you want to build. You get a starting architecture, the components to add later and when, the edge cases to plan for, and a build order. There is no timeline: you set your own pace.</p>
      {!aiEnabled && <div className="banner warn">The planner uses the AI engineer, which is off. Start the backend with <code>GROQ_API_KEY</code> set to turn it on.</div>}
      {aiEnabled && !loggedIn && <div className="banner info"><Link to="/account">Log in</Link> to use the planner.</div>}
      <label className="field">Your idea
        <textarea rows={6} value={idea} maxLength={2000} onChange={e => setIdea(e.target.value)} placeholder="Who uses it, what they do, roughly how many users, and anything special such as payments, live updates or uploads." />
      </label>
      <div className="row2">
        <button className="btn pri" onClick={go} disabled={busy || !aiEnabled || !loggedIn || idea.trim().length < 10}>{busy ? "Planning..." : "Make my plan"}</button>
        {EXAMPLES.map((e, i) => <button key={i} className="btn sm" onClick={() => setIdea(e)}>Example {i + 1}</button>)}
      </div>
      {err && <div className="err" role="alert">{err}</div>}
      {plan && <div className="card plan"><Markdown text={plan} /></div>}
    </>
  );
}
