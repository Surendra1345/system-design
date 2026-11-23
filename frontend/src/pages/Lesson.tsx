import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { DeepDive } from "../components/DeepDive";
import { Explain } from "../components/Explain";
import { Html } from "../components/Html";
import { StudyTimer } from "../components/StudyTimer";
import { Tutor } from "../components/Tutor";
import { Builder } from "../games/Builder";
import { Lab } from "../games/Lab";
import { Incident } from "../games/Incident";
import { Interview } from "../games/Interview";
import type { LessonDetail } from "../types";

type Mode = "play" | "read";
const getMode = (): Mode | null => { try { const m = localStorage.getItem("bp-mode"); return m === "read" || m === "play" ? m : null; } catch { return null; } };
const saveMode = (m: Mode) => { try { localStorage.setItem("bp-mode", m); } catch { /* ignore */ } };

export function Lesson() {
  const { id = "" } = useParams();
  const { catalog, progress, refresh, loggedIn } = useAuth();
  const [lesson, setLesson] = useState<LessonDetail | null>(null);
  const [mode, setMode] = useState<Mode>(getMode() ?? "play");
  const [pick, setPick] = useState<number | null>(null);
  const [level, setLevel] = useState(0);
  const [toast, setToast] = useState("");

  useEffect(() => { setLesson(null); setPick(null); setLevel(0); api<LessonDetail>("GET", `/api/lessons/${id}`).then(setLesson).catch(() => setLesson(null)); }, [id]);
  if (!lesson) return <p className="muted">Loading the lesson...</p>;

  const track = catalog?.tracks.find(t => t.id === lesson.t);
  const list = catalog?.lessons ?? [];
  const i = list.findIndex(l => l.id === lesson.id);
  const prev = list[i - 1], next = list[i + 1];
  const effective: Mode = lesson.game ? mode : "read";
  const read = progress?.lessons[lesson.id]?.read ?? false;

  const choose = (m: Mode) => { setMode(m); saveMode(m); };
  const toggleRead = async () => {
    if (!loggedIn) { setToast("Log in to save your progress."); return; }
    const r = await api<{ xpGained: number }>("PUT", `/api/lessons/${lesson.id}/read`, { done: !read });
    setToast(r.xpGained ? `+${r.xpGained} XP` : "");
    await refresh();
  };
  const toggleProject = async (pid: string, done: boolean) => {
    if (!loggedIn) { setToast("Log in to save your progress."); return; }
    const r = await api<{ xpGained: number }>("PUT", `/api/projects/${pid}`, { done });
    setToast(r.xpGained ? `Project done +${r.xpGained} XP` : "");
    await refresh();
  };

  return (
    <article>
      <div className="crumb">{track?.name}</div>
      <h1>{lesson.title}</h1>
      <p className="sub">{lesson.sum}</p>
      {effective === "read" && <Explain e={lesson.explain} />}
      {lesson.outcomes && (
        <details className="outcomes card">
          <summary><b>What you will be able to do</b></summary>
          <ul className="notes">{lesson.outcomes.outcomes.map((o, n) => <li key={n}>{o}</li>)}</ul>
          <p className="muted" style={{ margin: "8px 0 4px" }}><b>To count as mastered, handle these variations too:</b></p>
          <ul className="notes">{lesson.outcomes.variations.map((v, n) => <li key={n}>{v}</li>)}</ul>
          {lesson.outcomes.prereqs.length > 0 && <p className="muted" style={{ margin: "8px 0 0" }}>Builds on: {lesson.outcomes.prereqs.map((p, n) => <span key={p.id}>{n ? ", " : ""}<Link to={`/lesson/${p.id}`}>{p.title}</Link></span>)}</p>}
        </details>
      )}
      <StudyTimer lessonId={lesson.id} />
      <div className="tabs" role="tablist" aria-label="How to learn this lesson">
        {lesson.game && <button role="tab" aria-selected={effective === "play"} onClick={() => choose("play")}>Play</button>}
        <button role="tab" aria-selected={effective === "read"} onClick={() => choose("read")}>Read theory</button>
      </div>

      {effective === "play" && lesson.levels.length > 1 && (
        <div className="levels" role="tablist" aria-label="Levels">
          {lesson.levels.map(l => {
            const st = progress?.levels?.[lesson.id]?.[String(l.index)] ?? 0;
            return <button key={l.index} role="tab" aria-selected={level === l.index} className="levelbtn" onClick={() => setLevel(l.index)}>
              <small>Level {l.index + 1}</small><b>{l.name}</b><span className="stars">{"★".repeat(st)}<span className="off">{"★".repeat(3 - st)}</span></span>
            </button>;
          })}
        </div>
      )}
      {effective === "play" && lesson.game === "lab" && <Lab key={`${lesson.id}-${level}`} lessonId={lesson.id} level={level} takeaways={lesson.explain?.takeaways} />}
      {effective === "play" && lesson.game === "builder" && <Builder lessonId={lesson.id} level={level} takeaways={lesson.explain?.takeaways} />}
      {effective === "play" && lesson.game === "incident" && <Incident key={`${lesson.id}-${level}`} lessonId={lesson.id} level={level} takeaways={lesson.explain?.takeaways} />}
      {effective === "play" && lesson.game === "interview" && <Interview key={`${lesson.id}-${level}`} lessonId={lesson.id} level={level} takeaways={lesson.explain?.takeaways} />}
      {effective === "play" && <details className="primer card" open={!loggedIn && !read}><summary><b>New to this? The 2-minute plain-English primer</b></summary><Explain e={lesson.explain} /></details>}
      {effective === "play" && <Tutor lessonId={lesson.id} />}

      {effective === "read" && (
        <>
          {lesson.projects ? (
            <section className="sec">
              <p>Pick any project, in any order. Spend as long as you want on each. Tick it when you can show the result.</p>
              {lesson.project_list?.map(p => (
                <label className="proj" key={p.id}>
                  <input type="checkbox" checked={progress?.projects.includes(p.id) ?? false} onChange={e => void toggleProject(p.id, e.target.checked)} />
                  <span><b>{p.title}</b><p>{p.what}</p><small className="muted">Done when: {p.done}</small></span>
                </label>
              ))}
            </section>
          ) : (
            <>
              <div className="toc">
                {lesson.sec.map((s, n) => <a key={n} href={`#s${n}`}>{s.h}</a>)}<a href="#brk">What breaks</a>
              </div>
              {lesson.sec.map((s, n) => <section className="sec" key={n}><h2 id={`s${n}`}>{s.h}</h2><Html html={s.b} /></section>)}
            </>
          )}
          <DeepDive d={lesson.deep} />
          <section className="breaks" id="brk"><h2>What breaks in practice</h2><ul>{lesson.breaks.map((b, n) => <li key={n} dangerouslySetInnerHTML={{ __html: b }} />)}</ul></section>
          <section className="quiz">
            <h2>Check yourself</h2>
            <p style={{ margin: "0 0 6px" }}>{lesson.quiz.q}</p>
            {lesson.quiz.o.map((o, n) => (
              <button key={n} className={"opt" + (pick !== null ? (n === lesson.quiz.a ? " right" : n === pick ? " wrong" : "") : "")} onClick={() => setPick(n)}>{o}</button>
            ))}
            {pick !== null && <p className="why">{pick === lesson.quiz.a ? "Correct. " : "Not quite. "}{lesson.quiz.w}</p>}
          </section>
          <div className="foot">
            <button className={"btn" + (read ? " ok" : "")} onClick={() => void toggleRead()}>{read ? "Marked as read ✓" : "Mark as read"}</button>
            <span className="row2" style={{ margin: 0 }}>
              {prev && <Link className="btn" to={`/lesson/${prev.id}`}>← {prev.title}</Link>}
              {next && <Link className="btn pri" to={`/lesson/${next.id}`}>{next.title} →</Link>}
            </span>
          </div>
        </>
      )}
      {toast && <div className="toast" role="status" onAnimationEnd={() => setToast("")}>{toast}</div>}
    </article>
  );
}
