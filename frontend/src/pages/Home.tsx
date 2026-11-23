import { Link } from "react-router-dom";
import { useAuth } from "../auth";
import { HeroDemo } from "../components/HeroDemo";
import { LAB_HOOKS, PATHS } from "../paths";
import type { GameKind } from "../types";

const KIND: Record<string, string> = { builder: "Build and load-test", incident: "Live incident", interview: "AI interview", lab: "Hands-on lab" };
const ICON: Record<string, string> = { builder: "BUILD", incident: "LIVE", interview: "TALK", lab: "LAB" };
const fmt = (sec: number) => { const m = Math.floor(sec / 60); return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min`; };

export function Home() {
  const { catalog, progress, isDone, loggedIn } = useAuth();
  if (!catalog) return <p className="muted">Loading...</p>;
  const next = catalog.lessons.find(l => !isDone(l.id)) ?? catalog.lessons[0];
  const doneN = catalog.lessons.filter(l => isDone(l.id)).length;
  const stars = Object.values(progress?.lessons ?? {}).reduce((a, l) => a + l.stars, 0);
  const total = Object.values(progress?.time ?? {}).reduce((a, t) => a + t.spentSec, 0);
  const u = progress?.user;
  const maxStars = catalog.lessons.reduce((a, l) => a + l.levels * 3, 0);

  return (
    <>
      <section className="hero">
        <div className="herocols">
          <div>
            <span className="pill blue">Learn by breaking things</span>
            <h1>Don't just read about system design. Break it, fix it, understand it.</h1>
            <p>Run real simulations of load balancers, caches, queues, databases and more. Change a setting, watch the system fail or recover, and earn stars for getting it right. The theory is there when you want it.</p>
            <div className="row2">
              <Link className="btn pri" to="/lesson/lb">Try it now: 30 seconds</Link>
              <Link className="btn" to={`/lesson/${next.id}`}>{doneN ? `Continue: ${next.title}` : "Start the first lesson"}</Link>
              <Link className="btn" to="/start">New here? What is system design?</Link>
            </div>
          </div>
          <HeroDemo />
        </div>
      </section>
      <h2 style={{ marginTop: 8 }}>Choose your goal</h2>
      <div className="grid">
        {PATHS.map(p => <Link key={p.id} to="/paths" className="card pathpick"><b>{p.title}</b><span className="muted">{p.goal}</span></Link>)}
      </div>
      <Link to="/challenge" className="card challengepromo"><span className="pill blue">New</span><b>Unknown Problem Challenge: can you solve what you have never seen?</b><span className="muted">A system is in trouble and nobody tells you why. Diagnose it, fix it within a budget, and defend your choices. Every variation is different.</span></Link>
      <h2 style={{ marginTop: 24 }}>Things you can break</h2>
      <p className="lead">Hands-on labs where you change the settings and watch what happens.</p>
      <div className="grid">
        {catalog.lessons.filter(l => l.game === "lab").map(l => (
          <Link key={l.id} to={`/lesson/${l.id}`} className="card labpick"><b>{l.title}</b><span className="muted">{LAB_HOOKS[l.id] ?? l.summary}</span><small className="pill blue">{l.levels} levels</small></Link>
        ))}
      </div>
      {!loggedIn && <div className="banner info">You are a guest, so your progress is not saved. <Link to="/account">Create a free account</Link> to save progress, earn XP and join the leaderboard.</div>}
      <div className="stats">
        <div className="stat"><b>{u?.rank ?? "Guest"}</b><span>Rank</span></div>
        <div className="stat"><b>{u?.xp ?? 0}</b><span>XP</span></div>
        <div className="stat"><b>{u?.streak ?? 0}</b><span>Day streak</span></div>
        <div className="stat"><b>{doneN}/{catalog.lessons.length}</b><span>Lessons done</span></div>
        <div className="stat"><b>{stars}/{maxStars}</b><span>Stars</span></div>
        <div className="stat"><b>{fmt(total)}</b><span>Time spent</span></div>
      </div>
      <h2 style={{ marginTop: 24 }}>How each lesson works</h2>
      <div className="howto">
        <div className="card"><span className="num">1</span><b>Understand it</b><span className="muted">A short plain-English note: what it is, why we use it, and when to use it or not.</span></div>
        <div className="card"><span className="num">2</span><b>Practise it</b><span className="muted">A hands-on simulation: change the settings of a real mechanism and watch what happens, build and load-test a system, fix a live outage, or explain your design to an AI interviewer.</span></div>
        <div className="card"><span className="num">3</span><b>Go deeper</b><span className="muted">Read the full theory, see what breaks in practice, and ask the AI tutor anything.</span></div>
      </div>
      <p className="lead">New here? Start with the first lesson in <b>Fundamentals</b> and work down. Skip around whenever you like.</p>
      {catalog.tracks.map(t => {
        const ls = catalog.lessons.filter(l => l.track === t.id);
        const d = ls.filter(l => isDone(l.id)).length;
        return (
          <section key={t.id}>
            <h2 style={{ marginTop: 28 }}>{t.name}</h2>
            <p className="lead">{t.blurb}</p>
            <div className="bar" style={{ maxWidth: 320 }}><i style={{ width: `${d / ls.length * 100}%` }} /></div>
            <div className="grid">
              {ls.map(l => {
                const st = progress?.lessons[l.id]?.stars ?? 0;
                const most = l.levels * 3;
                const g = l.game as Exclude<GameKind, null> | null;
                return (
                  <Link key={l.id} to={`/lesson/${l.id}`} className={"card lcard" + (isDone(l.id) ? " done" : "")}>
                    <span className="ico">{g ? ICON[g] : "DIY"}</span>
                    <div><h4>{l.title}</h4><small>{st ? <span className="stars">★ {st}/{most}</span> : isDone(l.id) ? "Read" : g ? `${KIND[g]}${l.levels > 1 ? ` · ${l.levels} levels` : ""}` : "Hands-on projects"}</small></div>
                  </Link>
                );
              })}
            </div>
          </section>
        );
      })}
    </>
  );
}
