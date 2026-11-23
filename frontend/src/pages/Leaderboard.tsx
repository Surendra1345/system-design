import { useEffect, useState } from "react";
import { api } from "../api";

interface Row { rank: number; username: string; xp: number; title: string }

export function Leaderboard() {
  const [rows, setRows] = useState<Row[] | null>(null);
  useEffect(() => { api<Row[]>("GET", "/api/leaderboard").then(setRows).catch(() => setRows([])); }, []);
  return (
    <>
      <h1>Leaderboard</h1>
      <p className="sub">Top learners by XP. Every score is replayed and checked by the server.</p>
      {rows === null ? <p className="muted">Loading...</p> : rows.length === 0 ? <p className="muted">No one yet. Create an account and be the first.</p> : (
        <div className="tw"><table>
          <thead><tr><th>#</th><th>Learner</th><th>Rank</th><th>XP</th></tr></thead>
          <tbody>{rows.map(r => <tr key={r.rank}><td>{r.rank}</td><td>{r.username}</td><td>{r.title}</td><td>{r.xp}</td></tr>)}</tbody>
        </table></div>
      )}
    </>
  );
}
