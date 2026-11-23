import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";

const fmt = (sec: number) => { const m = Math.floor(sec / 60); return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min`; };

/** The learner decides how long to spend. There is no schedule: only an optional target and a timer. */
export function StudyTimer({ lessonId }: { lessonId: string }) {
  const { progress, loggedIn, refresh } = useAuth();
  const saved = progress?.time[lessonId];
  const [running, setRunning] = useState(false);
  const [pending, setPending] = useState(0);
  const [target, setTarget] = useState<string>(saved?.targetMin ? String(saved.targetMin) : "");
  const pendingRef = useRef(0);
  pendingRef.current = pending;

  const flush = useCallback(async () => {
    const add = pendingRef.current;
    if (add < 1 || !loggedIn) return;
    setPending(0);
    try { await api("PUT", `/api/time/${lessonId}`, { addSec: add }); await refresh(); } catch { setPending(p => p + add); }
  }, [lessonId, loggedIn, refresh]);

  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => { if (!document.hidden) setPending(p => p + 1); }, 1000);
    return () => clearInterval(id);
  }, [running]);

  useEffect(() => { if (pending > 0 && pending % 30 === 0) void flush(); }, [pending, flush]);
  useEffect(() => () => { void flush(); }, [flush]);

  const spent = (saved?.spentSec ?? 0) + pending;
  const tgt = Number(target) || 0;

  const saveTarget = async () => {
    if (!loggedIn) return;
    try { await api("PUT", `/api/time/${lessonId}`, { targetMin: Math.max(0, Math.floor(tgt)) }); await refresh(); } catch { /* ignore */ }
  };

  return (
    <div className="timebox">
      <b>My time</b>
      <span>{fmt(spent)}</span>
      <label>Target <input type="number" min={0} max={100000} placeholder="optional" aria-label="Target minutes"
        value={target} onChange={e => setTarget(e.target.value)} onBlur={saveTarget} /> min</label>
      {tgt > 0 && <div className="bar blue" style={{ width: 120 }}><i style={{ width: `${Math.min(100, spent / (tgt * 60) * 100)}%` }} /></div>}
      <button className="btn sm" onClick={() => { if (running) void flush(); setRunning(r => !r); }}>{running ? "Pause timer" : "Start timer"}</button>
      <small className="muted">Your pace. No schedule.{!loggedIn && " Log in to save your time."}</small>
    </div>
  );
}
