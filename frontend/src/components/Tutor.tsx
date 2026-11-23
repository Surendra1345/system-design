import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import { Markdown } from "./Markdown";

interface Msg { role: "user" | "assistant"; content: string }

/** An AI tutor that answers questions using the current lesson as its notes. */
export function Tutor({ lessonId }: { lessonId: string }) {
  const { loggedIn, aiEnabled } = useAuth();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const end = useRef<HTMLDivElement>(null);

  if (!aiEnabled) return <div className="banner warn">The AI tutor is off. Start the backend with <code>GROQ_API_KEY</code> set to turn it on.</div>;
  if (!loggedIn) return <div className="banner info"><Link to="/account">Log in</Link> to ask the AI tutor questions about this lesson.</div>;

  const ask = async (text: string) => {
    if (!text.trim() || busy) return;
    const history = msgs.slice(-8);
    setMsgs(m => [...m, { role: "user", content: text }]);
    setQ(""); setBusy(true); setErr("");
    try {
      const r = await api<{ answer: string }>("POST", "/api/ai/tutor", { lesson_id: lessonId, question: text, history });
      setMsgs(m => [...m, { role: "assistant", content: r.answer }]);
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Something went wrong."); }
    finally { setBusy(false); setTimeout(() => end.current?.scrollIntoView({ block: "nearest" }), 50); }
  };

  return (
    <section className="tutor card">
      <h3>Ask the AI tutor</h3>
      <p className="muted">Answers use this lesson as the source. Ask for an example, a simpler explanation or a comparison.</p>
      <div className="chat" aria-live="polite">
        {msgs.map((m, i) => <div key={i} className={"bubble " + m.role}>{m.role === "assistant" ? <Markdown text={m.content} /> : m.content}</div>)}
        {busy && <div className="bubble assistant muted">Thinking...</div>}
        <div ref={end} />
      </div>
      {err && <div className="err" role="alert">{err}</div>}
      <form className="row2" onSubmit={e => { e.preventDefault(); void ask(q); }}>
        <input type="text" style={{ flex: 1, minWidth: 200 }} value={q} maxLength={1500} placeholder="Ask anything about this lesson" aria-label="Your question" onChange={e => setQ(e.target.value)} />
        <button className="btn pri" disabled={busy || !q.trim()}>Ask</button>
      </form>
    </section>
  );
}
