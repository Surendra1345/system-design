import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../api";
import { useAuth } from "../auth";

export function Account() {
  const { loggedIn, progress, login, register, logout } = useAuth();
  const nav = useNavigate();
  const [mode, setMode] = useState<"register" | "login">("register");
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  if (loggedIn && progress) {
    const user = progress.user;
    return (
      <>
        <h1>Your account</h1>
        <div className="stats">
          <div className="stat"><b>{user.username}</b><span>Learner</span></div>
          <div className="stat"><b>{user.rank}</b><span>Rank</span></div>
          <div className="stat"><b>{user.xp}</b><span>XP</span></div>
          <div className="stat"><b>{user.streak} days</b><span>Streak</span></div>
        </div>
        <p>Your progress, time and scores are saved on the server.</p>
        <button className="btn" onClick={async () => { await logout(); nav("/"); }}>Log out</button>
      </>
    );
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try { await (mode === "register" ? register(u.trim(), p) : login(u.trim(), p)); nav("/"); }
    catch (x) { setErr(x instanceof ApiError ? x.message : "Something went wrong."); setBusy(false); }
  };

  return (
    <div className="auth">
      <h1>Save your progress</h1>
      <p className="sub" style={{ fontSize: 16 }}>Create a free account to keep your progress, get your scores verified and join the leaderboard.</p>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={mode === "register"} onClick={() => setMode("register")}>Create account</button>
        <button role="tab" aria-selected={mode === "login"} onClick={() => setMode("login")}>Log in</button>
      </div>
      <form onSubmit={submit}>
        <div className="field"><label htmlFor="un">Username</label><input id="un" type="text" value={u} onChange={e => setU(e.target.value)} autoComplete="username" maxLength={24} required /></div>
        <div className="field"><label htmlFor="pw">Password (8 or more characters)</label><input id="pw" type="password" value={p} onChange={e => setP(e.target.value)} autoComplete={mode === "register" ? "new-password" : "current-password"} maxLength={128} required /></div>
        <div className="err" role="alert">{err}</div>
        <button className="btn pri" disabled={busy}>{mode === "register" ? "Create account" : "Log in"}</button>
      </form>
    </div>
  );
}
