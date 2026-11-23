import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth";

export function Layout() {
  const { progress, catalog, isDone } = useAuth();
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const [dark, setDark] = useState(() => document.documentElement.dataset.theme === "dark");
  const toggleTheme = () => {
    const next = dark ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("bp-theme", next); } catch { /* ignore */ }
    setDark(!dark);
  };
  const loc = useLocation();
  useEffect(() => { setOpen(false); window.scrollTo(0, 0); }, [loc.pathname]);

  const q = filter.trim().toLowerCase();
  const current = loc.pathname.startsWith("/lesson/") ? loc.pathname.split("/")[2] : "";
  const user = progress?.user;

  return (
    <>
      <header className="topbar">
        <button className="btn sm menu-btn" onClick={() => setOpen(o => !o)} aria-expanded={open} aria-controls="side">Menu</button>
        <Link className="brand" to="/"><span className="logo" aria-hidden="true">B</span><span className="brand-text">Blueprint School</span></Link>
        <nav className="topnav" aria-label="Main">
          <NavLink to="/start">Start here</NavLink>
          <NavLink to="/" end>Learn</NavLink>
          <NavLink to="/paths">Paths</NavLink>
          <NavLink to="/challenge">Challenge</NavLink>
          <NavLink to="/mastery">Mastery</NavLink>
          <details className="morenav"><summary>More</summary><div><NavLink to="/planner">Planner</NavLink><NavLink to="/handbook">Edge cases</NavLink><NavLink to="/glossary">Glossary</NavLink><NavLink to="/leaderboard">Leaderboard</NavLink></div></details>
        </nav>
        <span className="spacer" />
        <button className="btn sm themebtn" onClick={toggleTheme} aria-pressed={dark}><span className="long">{dark ? "Light mode" : "Dark mode"}</span><span className="short">{dark ? "Light" : "Dark"}</span></button>
        {user
          ? <Link className="userchip" to="/account"><b className="nm">{user.username}</b><span className="pill blue">Level {user.level}</span><span className="pill">{user.xp} XP</span></Link>
          : <Link className="btn sm pri" to="/account">Log in</Link>}
      </header>
      <div className="shell">
        <nav className={"side" + (open ? " open" : "")} id="side" aria-label="Course outline">
          <input className="search" type="search" placeholder="Search lessons" aria-label="Search lessons" value={filter} onChange={e => setFilter(e.target.value)} />
          {catalog?.tracks.map(t => {
            const all = catalog.lessons.filter(l => l.track === t.id);
            const ls = all.filter(l => !q || (l.title + " " + l.summary).toLowerCase().includes(q));
            if (!ls.length) return null;
            const done = all.filter(l => isDone(l.id)).length;
            return (
              <details className="tgroup" key={t.id} open={!!q || all.some(l => l.id === current)}>
                <summary>{t.name}<span>{done}/{all.length}</span></summary>
                {ls.map(l => {
                  const stars = progress?.lessons[l.id]?.stars ?? 0;
                  return <NavLink key={l.id} to={`/lesson/${l.id}`} className="navlink"><span className={"dot" + (stars ? " y" : isDone(l.id) ? " p" : "")} />{l.title}</NavLink>;
                })}
              </details>
            );
          })}
        </nav>
        {open && <div className="scrim" onClick={() => setOpen(false)} />}
        <main id="main" tabIndex={-1}><Outlet /></main>
      </div>
    </>
  );
}
