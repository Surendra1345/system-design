import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import { Takeaways } from "../components/Explain";
import { Stars } from "../components/Stars";
import type { IncidentEvent, IncidentState, IncidentStepResult } from "../types";

interface Intro { title: string; brief: string; max: number; start: number; help: string; fixes_needed: number }
interface Line { kind: "cmd" | "out" | "good" | "band" | "wr" | "sys"; text: string }
interface Outcome { result: { resolved: boolean; minutes: number; stars: number }; xpGained: number; learn: string; fix?: string[] }

const QUICK = ["logs", "metrics", "traces", "deploys", "deps", "help"];

/** A terminal-style incident. The player investigates with commands and then types what they would do in their own words. */
export function Incident({ lessonId, level, takeaways }: { lessonId: string; level: number; takeaways?: string[] }) {
  const q = `?level=${level}`;
  const { loggedIn, refresh } = useAuth();
  const [intro, setIntro] = useState<Intro | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [events, setEvents] = useState<IncidentEvent[]>([]);
  const [state, setState] = useState<IncidentState | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [attempt, setAttempt] = useState(0);
  const box = useRef<HTMLDivElement>(null);
  const field = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let live = true;
    setLines([]); setEvents([]); setState(null); setOutcome(null); setInput("");
    api<Intro>("GET", `/api/games/${lessonId}/incident${q}`).then(i => {
      if (!live) return;
      setIntro(i);
      setState({ minute: 0, max: i.max, error_rate: i.start, history: [i.start], resolved: false, failed: false, seen: [] });
      setLines([{ kind: "sys", text: "ALERT: " + i.brief }, { kind: "sys", text: i.help }]);
    });
    return () => { live = false; };
  }, [lessonId, attempt, q]);

  useEffect(() => { box.current?.scrollTo({ top: box.current.scrollHeight }); }, [lines]);

  const finish = async (evs: IncidentEvent[]) => {
    try {
      const o = await api<Outcome>("POST", `/api/games/${lessonId}/incident/submit${q}`, { events: evs });
      setOutcome(o);
      if (loggedIn) void refresh();
    } catch (e) { setLines(l => [...l, { kind: "sys", text: e instanceof ApiError ? e.message : "Could not save the result." }]); }
  };

  const run = async (text: string) => {
    const cmd = text.trim();
    if (!cmd || busy || outcome) return;
    setBusy(true); setInput("");
    setLines(l => [...l, { kind: "cmd", text: cmd }]);
    try {
      const r = await api<IncidentStepResult>("POST", `/api/games/${lessonId}/incident/step${q}`, { events, input: cmd });
      const kind: Line["kind"] = r.kind === "fix" ? "good" : r.kind === "band" ? "band" : r.kind === "wr" ? "wr" : "out";
      setLines(l => [...l, { kind, text: (r.label && r.kind !== "inv" ? `[${r.label}] ` : "") + r.output }]);
      setState(r.state);
      if (r.event) {
        const next = [...events, r.event];
        setEvents(next);
        if (r.state.resolved || r.state.failed) await finish(next);
      }
    } catch (e) { setLines(l => [...l, { kind: "sys", text: e instanceof ApiError ? e.message : "Something went wrong." }]); }
    finally { setBusy(false); field.current?.focus(); }
  };

  const submit = (e: FormEvent) => { e.preventDefault(); void run(input); };

  if (!intro || !state) return <p className="muted">Connecting to production...</p>;
  const pct = state.error_rate;
  const W = 300, H = 70, steps = Math.max(intro.max, state.history.length - 1);
  const pts = state.history.map((v, i) => `${(i * W / steps).toFixed(1)},${(H - v / 100 * (H - 8) - 4).toFixed(1)}`).join(" ");

  return (
    <div className="gm">
      <div className="gm-head">
        <div><h2>{intro.title}</h2><p>{intro.brief}</p></div>
        <div className="chips"><span className="chip">Minute {state.minute} of {state.max}</span>{intro.fixes_needed > 1 && <span className="chip coin">{intro.fixes_needed} fixes needed</span>}</div>
      </div>

      <div className="inc-grid">
        <div className="card">
          <div className="vl">Customers seeing errors</div>
          <div className="gauge">
            <b style={{ color: pct > 60 ? "var(--danger)" : pct > 25 ? "var(--warning)" : "var(--success)" }}>{pct}%</b>
            <div style={{ flex: 1 }}>
              <div className={"bar " + (pct > 25 ? "red" : "")}><i style={{ width: `${pct}%` }} /></div>
            </div>
          </div>
          <svg viewBox={`0 0 ${W} ${H}`} className="chart" style={{ height: 70, marginTop: 8 }} role="img" aria-label="Error rate over time">
            <polyline points={pts} fill="none" stroke="var(--danger)" strokeWidth="2.5" />
          </svg>
          <p className="muted" style={{ marginTop: 8 }}>Every command costs a minute and errors keep rising. Look before you act, but not for too long.</p>
        </div>

        <div className="term-wrap">
          <div className="term" ref={box} role="log" aria-live="polite" onClick={() => field.current?.focus()}>
            {lines.map((l, i) => <div key={i} className={"tl " + l.kind}>{l.kind === "cmd" ? "$ " : ""}{l.text}</div>)}
            {busy && <div className="tl sys">...</div>}
          </div>
          {!outcome && (
            <form className="term-in" onSubmit={submit}>
              <span aria-hidden="true">$</span>
              <input ref={field} value={input} onChange={e => setInput(e.target.value)} maxLength={300} autoFocus autoComplete="off" spellCheck={false}
                placeholder="Type a command, or say what you would do..." aria-label="Terminal input" disabled={busy} />
            </form>
          )}
          {!outcome && (
            <div className="row2" style={{ marginTop: 8 }}>
              {QUICK.map(q => <button key={q} className="btn sm" onClick={() => void run(q)} disabled={busy}>{q}</button>)}
            </div>
          )}
        </div>
      </div>

      {outcome && (
        <div className="card result">
          <h2>{outcome.result.resolved ? "Incident resolved" : "Out of time"}</h2>
          <Stars n={outcome.result.stars} big />
          <p>{outcome.result.resolved ? `Resolved in ${outcome.result.minutes} minutes.` : `The outage ran too long. The fix was: ${(outcome.fix ?? []).join(" ")}`}</p>
          <p><b>What to remember.</b> {outcome.learn}</p>
          {outcome.result.resolved && (outcome.xpGained ? <p><span className="pill ok">+{outcome.xpGained} XP</span></p> : <p className="muted">No new XP. You already earned these stars.</p>)}
          {!loggedIn && outcome.result.resolved && <p className="muted">Log in to save your stars and XP.</p>}
          <Takeaways items={takeaways} />
          <div className="row2"><button className="btn pri" onClick={() => setAttempt(a => a + 1)}>Play again</button></div>
        </div>
      )}
    </div>
  );
}
