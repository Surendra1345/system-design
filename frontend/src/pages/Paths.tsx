import { Link } from "react-router-dom";
import { useAuth } from "../auth";
import { PATHS } from "../paths";

export function Paths() {
  const { catalog, progress, isDone } = useAuth();
  if (!catalog) return <p className="muted">Loading...</p>;
  const byId = new Map(catalog.lessons.map(l => [l.id, l]));
  return (
    <>
      <h1>Learning paths</h1>
      <p className="sub">Not sure where to begin? Pick the route that matches your goal. You can still jump to any lesson at any time.</p>
      {PATHS.map(p => {
        const ls = p.lessons.map(id => byId.get(id)).filter(Boolean) as NonNullable<ReturnType<typeof byId.get>>[];
        const done = ls.filter(l => isDone(l.id)).length;
        const next = ls.find(l => !isDone(l.id)) ?? ls[0];
        return (
          <section className="card pathcard" key={p.id}>
            <div className="pathhead">
              <div><h2 style={{ margin: 0 }}>{p.title}</h2><p className="lead" style={{ margin: "4px 0" }}>{p.goal}</p><small className="muted">For you if: {p.who}</small></div>
              <Link className="btn pri" to={`/lesson/${next.id}`}>{done ? (done === ls.length ? "Review" : "Continue") : "Start"}</Link>
            </div>
            <div className="bar" style={{ margin: "12px 0" }}><i style={{ width: `${done / ls.length * 100}%` }} /></div>
            <ol className="pathsteps">
              {ls.map(l => {
                const st = progress?.lessons[l.id]?.stars ?? 0;
                return <li key={l.id} className={isDone(l.id) ? "done" : ""}><Link to={`/lesson/${l.id}`}>{l.title}</Link>{st > 0 && <span className="stars"> ★ {st}</span>}</li>;
              })}
            </ol>
          </section>
        );
      })}
    </>
  );
}
