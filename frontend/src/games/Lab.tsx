import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import { Takeaways } from "../components/Explain";
import { Stars } from "../components/Stars";
import { SANDBOXES } from "./Sandbox";

type Control =
  | { id: string; label: string; type: "select"; options: string[][]; default: string; help: string }
  | { id: string; label: string; type: "range"; min: number; max: number; step: number; default: number; help: string; unit?: string }
  | { id: string; label: string; type: "toggle"; default: boolean; help: string }
  | { id: string; label: string; type: "multi"; options: string[][]; default: string[]; help: string; max: number };
type Settings = Record<string, string | number | boolean | string[]>;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Any = any;
interface LabInfo { kind: string; name: string; title: string; brief: string; goal: string; controls: Control[]; env: Any }
interface LabRun { frames: Any[]; segments?: Any[]; stats: Any; insights: string[]; stars: number; badness: number; settings: Settings }

const C = { ok: "var(--success)", bad: "var(--danger)", warn: "var(--warning)", pri: "var(--primary)", line: "var(--line)", soft: "var(--bg-soft)", text: "var(--text)", muted: "var(--muted)" };
const T = (x: number, y: number, s: ReactNode, o: Any = {}) => <text x={x} y={y} fontSize={o.size ?? 12} textAnchor={o.anchor ?? "middle"} fill={o.fill ?? C.text} fontWeight={o.bold ? 700 : 400}>{s}</text>;

// ---------------------------------------------------------------- load balancer: requests are dealt into server queues
function LbView({ f, info, st }: { f: Any; info: LabInfo; st: Any }) {
  const n = info.env.speeds.length, w = 600 / n;
  return (
    <svg viewBox="0 0 640 330" className="labsvg">
      <rect x={250} y={8} width={140} height={34} rx={8} fill={C.pri} />{T(320, 30, "Load balancer", { fill: "#fff", bold: true })}
      {f.arrivals.slice(0, 16).map((a: Any, i: number) => a.server >= 0 && (
        <line key={a.id} x1={320} y1={42} x2={20 + a.server * w + w / 2} y2={96} stroke={a.lost ? C.bad : a.size > 1 ? C.warn : C.pri} strokeWidth={a.size > 1 ? 3 : 1.4} opacity={0.35 + (i % 3) * 0.2} />
      ))}
      {Array.from({ length: n }).map((_, i) => {
        const x = 20 + i * w, dead = f.dead[i], q: number[] = f.queues[i];
        let y = 300;
        return (
          <g key={i}>
            <rect x={x + 8} y={96} width={w - 16} height={218} rx={8} fill={dead ? "var(--danger-soft)" : C.soft} stroke={dead ? C.bad : C.line} />
            {T(x + w / 2, 114, dead ? `Server ${i + 1} DOWN` : `Server ${i + 1}`, { bold: true, fill: dead ? C.bad : C.text })}
            {T(x + w / 2, 128, `speed ${info.env.speeds[i]} · waiting ${f.qlen[i]}`, { size: 11, fill: C.muted })}
            {!dead && q.map((left, k) => { const h = Math.max(6, Math.min(40, left * 4.4)); y -= h + 2; return y > 134 ? <rect key={k} x={x + 18} y={y} width={w - 36} height={h} rx={3} fill={left > 1.5 ? C.warn : C.pri} opacity={k === 0 ? 1 : 0.8} /> : null; })}
            {dead && T(x + w / 2, 220, "✕", { size: 44, fill: C.bad })}
          </g>
        );
      })}
      {T(320, 326, `finished ${f.done} · lost ${f.lost} · small requests blue, large requests orange`, { size: 11, fill: C.muted })}
      <rect x={0} y={0} width={0} height={0} data-p95={st.p95} />
    </svg>
  );
}

// ---------------------------------------------------------------- cache: slots in memory, HIT/MISS stream, database meter
function CacheView({ f, info, set }: { f: Any; info: LabInfo; set: Settings }) {
  const size = Number(set.size), cols = Math.min(size, 20), cap = info.env.db_cap;
  return (
    <svg viewBox="0 0 640 330" className="labsvg">
      {T(20, 20, `Cache memory (${size} slots)`, { anchor: "start", bold: true })}
      {Array.from({ length: size }).map((_, i) => {
        const key = f.slots[i], x = 20 + (i % cols) * 30, y = 30 + Math.floor(i / cols) * 30;
        return <g key={i}><rect x={x} y={y} width={26} height={26} rx={5} fill={key === undefined ? C.soft : C.pri} opacity={key === undefined ? 1 : 0.85} stroke={C.line} />{key !== undefined && T(x + 13, y + 17, key, { size: 9, fill: "#fff" })}</g>;
      })}
      {T(20, 130, "Incoming requests this tick (green = answered from cache, red = went to the database)", { anchor: "start", size: 11, fill: C.muted })}
      {f.reqs.map((r: number[], i: number) => <g key={i}><rect x={20 + i * 34} y={140} width={30} height={30} rx={6} fill={r[1] ? C.ok : C.bad} />{T(20 + i * 34 + 15, 160, r[1] ? "HIT" : "MISS", { size: 9, fill: "#fff", bold: true })}</g>)}
      {T(20, 205, "Database load", { anchor: "start", bold: true })}
      <rect x={20} y={214} width={400} height={22} rx={6} fill={C.soft} stroke={C.line} />
      <rect x={20} y={214} width={Math.min(400, (f.db_load / (cap * 3)) * 400)} height={22} rx={6} fill={f.db_load > cap ? C.bad : C.ok} />
      <line x1={20 + 400 / 3} y1={208} x2={20 + 400 / 3} y2={242} stroke={C.text} strokeDasharray="4 3" />
      {T(20 + 400 / 3, 256, `limit ${cap}`, { size: 11 })}
      {T(440, 231, `${f.db_load} lookups`, { anchor: "start", bold: true, fill: f.db_load > cap ? C.bad : C.text })}
      {T(20, 290, `Hit ratio so far: ${Math.round(f.ratio * 100)}%   ·   average answer: ${f.avg_ms} ms`, { anchor: "start", bold: true })}
      {f.db_load > cap && T(20, 312, "The database is overloaded, so everything slows down.", { anchor: "start", fill: C.bad })}
    </svg>
  );
}

// ---------------------------------------------------------------- CDN: world map, click to place edge servers
function CdnView({ f, info, set, toggle }: { f: Any; info: LabInfo; set: Settings; toggle: (id: string) => void }) {
  const env = info.env, X = (x: number) => 20 + x * 6.4, Y = (y: number) => 30 + y * 6.4, chosen = set.sites as string[];
  const shown = f.region ? info.env.regions.map((r: Any) => r.id) : [];
  const rows: Any[] = f._rows ?? [];
  return (
    <svg viewBox="0 0 640 330" className="labsvg">
      <rect x={4} y={4} width={632} height={322} rx={12} fill={C.soft} />
      {rows.filter((_: Any, i: number) => i <= f.t).map((r: Any) => {
        const reg = env.regions.find((q: Any) => q.id === r.region), site = env.sites.find((s: Any) => s.id === r.edge);
        const tx = site ? X(site.pos[0]) : X(env.origin[0]), ty = site ? Y(site.pos[1]) : Y(env.origin[1]);
        const col = r.latency < 100 ? C.ok : r.latency < 220 ? C.warn : C.bad, path = `M${X(reg.pos[0])},${Y(reg.pos[1])} L${tx},${ty}`;
        return <g key={r.region}><line x1={X(reg.pos[0])} y1={Y(reg.pos[1])} x2={tx} y2={ty} stroke={col} strokeWidth={2.4} strokeDasharray={site ? "" : "5 4"} opacity={0.6} />
          {[0, 1].map(k => <circle key={k} r={4.5} fill={col}><animateMotion dur={`${Math.max(0.5, r.latency / 120)}s`} begin={`${k * Math.max(0.5, r.latency / 120) / 2}s`} repeatCount="indefinite" path={path} /></circle>)}
          {T(X(reg.pos[0]), Y(reg.pos[1]) - 22, `${reg.name}`, { size: 10, fill: C.muted })}{T(X(reg.pos[0]), Y(reg.pos[1]) - 10, `${Math.round(r.latency)} ms`, { size: 12, bold: true })}</g>;
      })}
      {env.regions.map((r: Any) => <circle key={r.id} cx={X(r.pos[0])} cy={Y(r.pos[1])} r={4 + r.weight / 6} fill={C.pri} opacity={0.5} />)}
      {env.sites.map((s: Any) => { const on = chosen.includes(s.id); return <g key={s.id} style={{ cursor: "pointer" }} onClick={() => toggle(s.id)}><rect x={X(s.pos[0]) - 9} y={Y(s.pos[1]) + 6} width={18} height={18} rx={4} fill={on ? C.ok : "var(--surface)"} stroke={on ? C.ok : C.muted} />{T(X(s.pos[0]), Y(s.pos[1]) + 38, s.name, { size: 10, fill: on ? C.ok : C.muted })}</g>; })}
      <g><polygon points={`${X(env.origin[0])},${Y(env.origin[1]) - 12} ${X(env.origin[0]) + 11},${Y(env.origin[1]) + 8} ${X(env.origin[0]) - 11},${Y(env.origin[1]) + 8}`} fill={C.bad} />{T(X(env.origin[0]), Y(env.origin[1]) + 22, "ORIGIN", { size: 10, bold: true, fill: C.bad })}</g>
      {T(320, 318, "Click a square to place or remove an edge server. Dots are requests: the slower the trip, the slower the dot. Dashed = all the way to the origin.", { size: 11, fill: C.muted })}
      {shown.length === 0 && null}
    </svg>
  );
}

// ---------------------------------------------------------------- queue: lane of jobs, workers, dead-letter queue
function QueueView({ f }: { f: Any }) {
  return (
    <svg viewBox="0 0 640 330" className="labsvg">
      {T(20, 22, `Queue (${f.qlen} waiting, oldest healthy job has waited ${f.oldest} ticks)`, { anchor: "start", bold: true })}
      <rect x={20} y={32} width={600} height={54} rx={8} fill={C.soft} stroke={C.line} />
      {f.queue.slice(0, 28).map((j: number[], i: number) => <rect key={i} x={26 + i * 21} y={40} width={17} height={38} rx={3} fill={j[0] ? C.bad : C.pri} opacity={0.9} />)}
      {T(20, 112, "Workers", { anchor: "start", bold: true })}
      {f.workers.map((b: number, i: number) => <g key={i}><rect x={20 + i * 48} y={122} width={42} height={42} rx={8} fill={b ? C.ok : C.soft} stroke={C.line} />{T(20 + i * 48 + 21, 148, b ? "busy" : "idle", { size: 10, fill: b ? "#fff" : C.muted })}</g>)}
      {T(20, 206, `Dead-letter queue: ${f.dlq} parked jobs`, { anchor: "start", bold: true })}
      {Array.from({ length: Math.min(f.dlq, 28) }).map((_, i) => <rect key={i} x={20 + i * 21} y={214} width={17} height={30} rx={3} fill={C.bad} opacity={0.6} />)}
      {T(20, 280, `Completed: ${f.done}`, { anchor: "start", bold: true, fill: C.ok })}
      {f.dups > 0 && T(20, 302, `Duplicates processed: ${f.dups}`, { anchor: "start", bold: true, fill: C.bad })}
      {T(620, 302, "blue = healthy job · red = broken job", { anchor: "end", size: 11, fill: C.muted })}
    </svg>
  );
}

// ---------------------------------------------------------------- sharding: hash ring and shard load bars
function ShardView({ f, run, info }: { f: Any; run: LabRun; info: LabInfo }) {
  const st = run.stats, n = st.shards, tot = f.counts.reduce((a: number, b: number) => a + b, 0) || 1, cols = ["#2563EB", "#16A34A", "#D97706", "#9333EA", "#DC2626", "#0891B2", "#65A30D", "#DB2777"];
  const cap = info.env.cap;
  return (
    <svg viewBox="0 0 640 330" className="labsvg">
      {T(20, 20, "Requests per shard", { anchor: "start", bold: true })}
      {f.counts.map((c: number, i: number) => { const h = (c / tot) * 220; return <g key={i}><rect x={30 + i * 46} y={270 - h} width={36} height={h} rx={4} fill={cols[i % 8]} />{T(48 + i * 46, 288, `S${i + 1}`, { size: 11 })}{T(48 + i * 46, 264 - h, `${Math.round((c / tot) * 100)}%`, { size: 10 })}</g>; })}
      <line x1={24} y1={270 - cap * 220} x2={30 + n * 46} y2={270 - cap * 220} stroke={C.bad} strokeDasharray="5 4" />{T(30 + n * 46 + 4, 274 - cap * 220, "safe limit", { size: 10, anchor: "start", fill: C.bad })}
      {st.ring.length > 0 ? (
        <g>{T(500, 20, "Hash ring", { bold: true })}<circle cx={500} cy={130} r={90} fill="none" stroke={C.line} strokeWidth={2} />
          {st.ring.map((p: number[], i: number) => <circle key={i} cx={500 + 90 * Math.sin(p[0] * 2 * Math.PI)} cy={130 - 90 * Math.cos(p[0] * 2 * Math.PI)} r={6} fill={cols[p[1] % 8]} />)}
          {T(500, 134, "keys go to the next point", { size: 10, fill: C.muted })}</g>
      ) : (
        <g>{T(500, 130, run.settings.strategy === "range" ? "Ranges: 1..N split in order" : "hash(key) mod N", { bold: true })}{T(500, 150, "no ring in this strategy", { size: 10, fill: C.muted })}</g>
      )}
      {info.env.grow && T(500, 230, `Adding one shard moves ${Math.round(st.moved * 100)}% of keys`, { bold: true, fill: st.moved > 0.4 ? C.bad : C.ok })}
    </svg>
  );
}

// ---------------------------------------------------------------- rate limiter: requests arrive at a gate, some pass, some bounce
function LimiterView({ frames, i }: { frames: Any[]; i: number }) {
  const f = frames[i], bw = 600 / frames.length, max = Math.max(10, ...frames.map(g => Math.max(g.legit[0] + g.legit[1], g.abuse[0] + g.abuse[1]))), sc = 50 / max;
  const dots = (n: number, lane: number, kind: "pass" | "block", color: string) => Array.from({ length: Math.min(7, n) }).map((_, k) => {
    const y = lane + ((k % 4) - 1.5) * 9, d = `${(k * 0.09).toFixed(2)}s`;
    return <circle key={`${kind}${lane}${k}`} r={4} fill={kind === "block" ? C.bad : color} cy={0}><animateMotion dur={kind === "pass" ? "0.9s" : "0.55s"} begin={d} fill="freeze" path={kind === "pass" ? `M60,${y} L540,${y}` : `M60,${y} L300,${y} L240,${y + (k % 2 ? 14 : -14)}`} />{kind === "block" && <animate attributeName="opacity" values="1;1;0" keyTimes="0;0.7;1" dur="0.9s" begin={d} fill="freeze" />}</circle>;
  });
  return (
    <svg viewBox="0 0 640 330" className="labsvg" key="lim">
      {T(20, 18, "Real users (top) and a bot (bottom) send requests to the limiter. Green gets through. Red is turned away.", { anchor: "start", size: 11, bold: true })}
      <rect x={14} y={50} width={46} height={30} rx={6} fill={C.soft} stroke={C.line} />{T(37, 69, "Users", { size: 10 })}
      <rect x={14} y={104} width={46} height={30} rx={6} fill={C.soft} stroke={C.line} />{T(37, 123, "Bot", { size: 10 })}
      <rect x={296} y={44} width={10} height={98} rx={4} fill={C.text} opacity={0.75} />{T(301, 156, "limiter", { size: 10, bold: true })}
      <rect x={548} y={64} width={72} height={56} rx={8} fill={C.soft} stroke={C.line} />{T(584, 96, "Your API", { size: 11, bold: true })}
      <g key={f.t}>{dots(f.legit[0], 65, "pass", C.ok)}{dots(f.legit[1], 65, "block", C.bad)}{dots(f.abuse[0], 119, "pass", C.warn)}{dots(f.abuse[1], 119, "block", C.bad)}</g>
      {T(20, 182, `this tick: users ${f.legit[0]} let in, ${f.legit[1]} turned away · bot ${f.abuse[0]} let in, ${f.abuse[1]} turned away${f.tokens != null ? ` · fewest tokens left ${f.tokens}` : ""}`, { anchor: "start", size: 11, bold: true })}
      <line x1={20} y1={270} x2={620} y2={270} stroke={C.line} />{T(20, 200, "history of every tick: green allowed, red blocked (users above the line, bot below)", { anchor: "start", size: 10, fill: C.muted })}
      {frames.slice(0, i + 1).map((g, k) => <g key={k}><rect x={20 + k * bw} y={265 - g.legit[0] * sc} width={Math.max(1, bw - 1)} height={g.legit[0] * sc} fill={C.ok} /><rect x={20 + k * bw} y={265 - (g.legit[0] + g.legit[1]) * sc} width={Math.max(1, bw - 1)} height={g.legit[1] * sc} fill={C.bad} />
        <rect x={20 + k * bw} y={276} width={Math.max(1, bw - 1)} height={g.abuse[0] * sc} fill={C.warn} /><rect x={20 + k * bw} y={276 + g.abuse[0] * sc} width={Math.max(1, bw - 1)} height={g.abuse[1] * sc} fill={C.bad} opacity={0.5} /></g>)}
    </svg>
  );
}

// ---------------------------------------------------------------- circuit breaker: thread pool and breaker state
function BreakerView({ frames, i, info }: { frames: Any[]; i: number; info: LabInfo }) {
  const f = frames[i], pool = info.env.pool, bw = 600 / frames.length, col = f.state === "open" ? C.bad : f.state === "half" ? C.warn : C.ok;
  return (
    <svg viewBox="0 0 640 330" className="labsvg">
      {T(20, 20, `Worker threads (${f.threads} of ${pool} busy)`, { anchor: "start", bold: true })}
      {Array.from({ length: pool }).map((_, k) => <rect key={k} x={20 + k * 30} y={30} width={24} height={34} rx={5} fill={k < f.threads ? (f.threads >= pool ? C.bad : C.warn) : C.soft} stroke={C.line} />)}
      <rect x={20} y={90} width={190} height={46} rx={10} fill={col} />{T(115, 119, `Breaker: ${f.state === "half" ? "HALF-OPEN" : f.state.toUpperCase()}`, { fill: "#fff", bold: true, size: 14 })}
      {T(230, 108, f.incident ? "The payment service is having an incident right now" : "The payment service is healthy", { anchor: "start", fill: f.incident ? C.bad : C.ok, bold: true })}
      {T(230, 128, `calls sent to it this tick: ${f.calls} · retries waiting: ${f.waiting}`, { anchor: "start", size: 11, fill: C.muted })}
      {T(20, 170, "Incident (shaded) and outcomes so far", { anchor: "start", bold: true })}
      {frames.slice(0, i + 1).map((g, k) => <g key={k}>{g.incident && <rect x={20 + k * bw} y={178} width={bw} height={110} fill={C.bad} opacity={0.1} />}<rect x={20 + k * bw} y={288 - g.threads * 4.5} width={Math.max(1, bw - 1)} height={g.threads * 4.5} fill={g.state === "open" ? C.bad : C.pri} opacity={0.7} /></g>)}
      {T(20, 312, `OK ${f.ok}   ·   fallback ${f.degraded}   ·   failed ${f.failed}`, { anchor: "start", bold: true })}
    </svg>
  );
}

// ---------------------------------------------------------------- autoscaling: servers appear and disappear as traffic rises and falls
function ScaleView({ frames, i, info }: { frames: Any[]; i: number; info: LabInfo }) {
  const f = frames[i], max = Math.max(...frames.map(g => Math.max(g.load, g.cap))) * 1.1, bw = 600 / frames.length, y = (v: number) => 300 - (v / max) * 90;
  const total = f.ready + f.booting, per = info.env.per, cols = Math.min(10, Math.max(1, total)), slot = 56;
  const path = (k: "load" | "cap") => frames.slice(0, i + 1).map((g, j) => `${j ? "L" : "M"}${20 + j * bw + bw / 2},${y(g[k])}`).join(" ");
  const loadDots = Math.min(9, Math.round(f.load / per / 1.2) + 1), droppedDots = f.dropped > 0.5 ? Math.min(6, Math.ceil(f.dropped / per)) : 0;
  return (
    <svg viewBox="0 0 640 330" className="labsvg">
      {T(20, 18, `${f.ready} server(s) running${f.booting ? `, ${f.booting} booting (cannot serve yet)` : ""}. Traffic: ${Math.round(f.load)} requests/tick, capacity ${Math.round(f.cap)}.`, { anchor: "start", size: 11, bold: true, fill: f.dropped > 0.5 ? C.bad : C.text })}
      <rect x={14} y={80} width={54} height={36} rx={7} fill={C.soft} stroke={C.line} />{T(41, 103, "Users", { size: 10, bold: true })}
      <g key={`d${f.t}`}>{Array.from({ length: loadDots }).map((_, k) => <circle key={k} r={3.5} fill={C.pri}><animateMotion dur="0.8s" begin={`${(k * 0.08).toFixed(2)}s`} fill="freeze" path={`M68,98 L${100 + ((k % cols) * slot)},${60 + (k % 3) * 20}`} /></circle>)}
        {Array.from({ length: droppedDots }).map((_, k) => <circle key={`x${k}`} r={4} fill={C.bad}><animateMotion dur="0.8s" begin={`${(k * 0.1).toFixed(2)}s`} fill="freeze" path={`M68,98 L90,${140 + k * 6}`} /><animate attributeName="opacity" values="1;1;0" dur="0.9s" begin={`${(k * 0.1).toFixed(2)}s`} fill="freeze" /></circle>)}</g>
      {Array.from({ length: Math.min(20, total) }).map((_, k) => { const col = k % cols, row = Math.floor(k / cols), booting = k >= f.ready; return <g key={k}><rect x={100 + col * slot} y={38 + row * 44} width={46} height={32} rx={6} fill={booting ? C.warn : C.ok} opacity={booting ? 0.55 : 0.9} />{T(123 + col * slot, 59 + row * 44, booting ? "boot" : "up", { size: 10, fill: "#fff", bold: true })}</g>; })}
      {frames.slice(0, i + 1).map((g, k) => g.dropped > 0.5 && <rect key={k} x={20 + k * bw} y={y(g.load)} width={Math.max(1, bw)} height={Math.max(1, y(g.cap) - y(g.load))} fill={C.bad} opacity={0.45} />)}
      <path d={path("cap")} fill="none" stroke={C.ok} strokeWidth={3} /><path d={path("load")} fill="none" stroke={C.pri} strokeWidth={2.4} />
      {T(20, 322, "blue: traffic · green: capacity · red: requests dropped", { anchor: "start", size: 10, fill: C.muted })}
    </svg>
  );
}

// ---------------------------------------------------------------- replication: primary, lagging followers, reads
function ReplView({ f, info }: { f: Any; info: LabInfo }) {
  const n = f.pending.length, cap = info.env.cap, xs = Array.from({ length: n }, (_, i) => 320 + (i - (n - 1) / 2) * 190);
  return (
    <svg viewBox="0 0 640 330" className="labsvg">
      <rect x={220} y={14} width={200} height={70} rx={10} fill={f.down ? "var(--danger-soft)" : C.soft} stroke={f.down ? C.bad : C.pri} strokeWidth={2} />
      {T(320, 36, f.down ? "PRIMARY DOWN, electing a new one" : f.after ? "New primary (was a follower)" : "Primary", { bold: true, fill: f.down ? C.bad : C.text })}
      <rect x={236} y={48} width={168} height={14} rx={4} fill="var(--surface)" stroke={C.line} /><rect x={236} y={48} width={Math.min(168, (f.load / cap) * 168)} height={14} rx={4} fill={f.load >= cap ? C.bad : C.ok} />
      {T(320, 78, `${f.load} of ${cap} operations this tick · ${f.writes} writes`, { size: 11, fill: C.muted })}
      {xs.map((x, i) => (
        <g key={i}>
          <line x1={320} y1={84} x2={x} y2={150} stroke={C.line} strokeWidth={2} />
          {Array.from({ length: Math.min(f.pending[i], 6) }).map((_, k) => <circle key={k} r={5} fill={C.warn}><animateMotion dur="1.2s" begin={`${k * 0.2}s`} repeatCount="indefinite" path={`M320,84 L${x},150`} /></circle>)}
          <rect x={x - 75} y={150} width={150} height={60} rx={10} fill={C.soft} stroke={C.line} />
          {T(x, 172, `Follower ${i + 1}`, { bold: true })}{T(x, 192, `${f.pending[i]} writes not yet copied`, { size: 11, fill: f.pending[i] > 8 ? C.bad : C.muted })}
        </g>
      ))}
      {T(20, 238, "Reads this tick (green = fresh, red = stale answer, blue = from the primary)", { anchor: "start", size: 11, fill: C.muted })}
      {f.reads.map((r: Any[], i: number) => <g key={i}><rect x={20 + i * 40} y={246} width={34} height={26} rx={6} fill={r[1] ? C.bad : r[0] === "L" ? C.pri : C.ok} />{T(37 + i * 40, 263, r[0] === "L" ? "P" : "F" + (Number(r[0]) + 1), { size: 10, fill: "#fff", bold: true })}</g>)}
      {T(20, 304, `stale answers ${f.stale} · refused reads ${f.unserved} · writes lost in the crash ${f.lost}`, { anchor: "start", bold: true, fill: f.lost ? C.bad : C.text })}
    </svg>
  );
}

// ---------------------------------------------------------------- transactions: one lane per transaction, locks and balances
function TxView({ frames, i, info }: { frames: Any[]; i: number; info: LabInfo }) {
  const f = frames[i], n = f.state.length, bw = Math.min(14, 560 / Math.max(20, frames.length)), lane = Math.min(22, 170 / n);
  const col: Record<string, string> = { ready: C.pri, blocked: C.warn, aborted: C.bad, done: C.ok };
  return (
    <svg viewBox="0 0 640 330" className="labsvg">
      {info.env.accounts.map((a: string, k: number) => {
        const holders = f.locks[a] ? Object.entries(f.locks[a]).map(([id, m]) => `T${Number(id) + 1}:${m}`).join(" ") : "free";
        return <g key={a}><rect x={20 + k * 150} y={8} width={140} height={46} rx={8} fill={C.soft} stroke={f.locks[a] ? C.warn : C.line} />{T(90 + k * 150, 26, `${a} = ${f.db[a]}`, { bold: true, size: 14 })}{T(90 + k * 150, 45, `lock: ${holders}`, { size: 10, fill: C.muted })}</g>;
      })}
      {Array.from({ length: n }).map((_, k) => <g key={k}>{T(20, 82 + k * lane, `T${k + 1}`, { anchor: "start", size: 10, fill: C.muted })}
        {frames.slice(0, i + 1).map((g, j) => <rect key={j} x={44 + j * bw} y={72 + k * lane} width={Math.max(1, bw - 1)} height={lane - 4} fill={col[g.state[k]]} opacity={g.state[k] === "ready" ? 0.55 : 0.95} />)}</g>)}
      <g>{T(20, 264, "events now", { anchor: "start", size: 11, fill: C.muted, bold: true })}{f.events.map((e: string, k: number) => T(20, 280 + k * 14, e, { anchor: "start", size: 11, fill: e.includes("DEADLOCK") || e.includes("aborted") || e.includes("not") ? C.bad : C.text }))}</g>
      {T(620, 264, "blue working · orange waiting for a lock · red aborted · green done", { anchor: "end", size: 10, fill: C.muted })}
    </svg>
  );
}

// ---------------------------------------------------------------- consensus: five nodes with roles, terms and messages
function ConsensusView({ f }: { f: Any }) {
  const pos = f.nodes.map((_: Any, k: number) => [320 + 150 * Math.sin((k / 5) * 2 * Math.PI), 150 - 100 * Math.cos((k / 5) * 2 * Math.PI)]);
  const fill = (n: Any) => !n.alive ? "#9CA3AF" : n.role === "L" ? C.ok : n.role === "C" ? C.warn : C.pri;
  const split = f.nodes.some((n: Any) => n.group === 1);
  return (
    <svg viewBox="0 0 640 330" className="labsvg">
      {f.msgs.map((m: Any[], k: number) => <g key={k}><line x1={pos[m[1]][0]} y1={pos[m[1]][1]} x2={pos[m[2]][0]} y2={pos[m[2]][1]} stroke={m[0] === "hb" ? C.ok : m[0] === "rv" ? C.warn : C.pri} strokeWidth={1.6} opacity={0.6} />
        <circle r={4} fill={m[0] === "hb" ? C.ok : m[0] === "rv" ? C.warn : C.pri}><animateMotion dur="0.7s" repeatCount="indefinite" path={`M${pos[m[1]][0]},${pos[m[1]][1]} L${pos[m[2]][0]},${pos[m[2]][1]}`} /></circle></g>)}
      {f.nodes.map((n: Any, k: number) => <g key={k}><circle cx={pos[k][0]} cy={pos[k][1]} r={36} fill={fill(n)} stroke={split ? (n.group ? C.bad : C.text) : "none"} strokeWidth={4} strokeDasharray={split ? "6 3" : ""} />
        {T(pos[k][0], pos[k][1] - 2, `N${k + 1}`, { fill: "#fff", bold: true, size: 14 })}{T(pos[k][0], pos[k][1] + 13, !n.alive ? "down" : `${n.role === "L" ? "leader" : n.role === "C" ? "cand." : "follower"} t${n.term}`, { fill: "#fff", size: 9 })}</g>)}
      {T(20, 306, f.leaders.length === 0 ? "No usable leader right now: writes are refused." : f.leaders.length === 1 ? `Leader: N${f.leaders[0] + 1}` : `TWO leaders (${f.leaders.map((x: number) => "N" + (x + 1)).join(", ")}) are both accepting writes: split brain!`, { anchor: "start", bold: true, fill: f.leaders.length === 1 ? C.ok : C.bad })}
      {T(20, 324, `ticks without a leader: ${f.no_leader} · ticks with two leaders: ${f.conflict} · orange = vote request, blue = vote, green = heartbeat`, { anchor: "start", size: 10, fill: C.muted })}
      {split && T(580, 20, "NETWORK SPLIT", { fill: C.bad, bold: true, anchor: "end" })}
    </svg>
  );
}

// ---------------------------------------------------------------- clocks: edits stamped by three servers
function ClocksView({ frames, i }: { frames: Any[]; i: number }) {
  const shown = frames.slice(0, i + 1), bw = 580 / Math.max(frames.length, 10);
  const xy = (k: number, srv: number) => [30 + k * bw + bw / 2, 60 + srv * 80];
  return (
    <svg viewBox="0 0 640 330" className="labsvg">
      {[0, 1, 2].map(s => <g key={s}><line x1={20} y1={60 + s * 80} x2={620} y2={60 + s * 80} stroke={C.line} />{T(20, 44 + s * 80, `Server ${s + 1}`, { anchor: "start", bold: true, size: 11 })}</g>)}
      {shown.map((g, k) => { if (k === 0) return null; const a = xy(k - 1, shown[k - 1].srv), b = xy(k, g.srv); return <line key={k} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke={g.bad ? C.bad : C.muted} strokeWidth={g.bad ? 2 : 1} opacity={0.7} />; })}
      {shown.map((g, k) => { const p = xy(k, g.srv); return <circle key={k} cx={p[0]} cy={p[1]} r={Math.min(7, bw / 2 + 1)} fill={g.bad ? C.bad : C.ok} />; })}
      {shown.length > 0 && (() => { const g = shown[shown.length - 1], p = xy(shown.length - 1, g.srv); return <g>{T(Math.min(560, p[0]), p[1] - 14, `ts ${g.ts}`, { size: 10 })}{T(20, 300, `latest edit via server ${g.srv + 1}: clock is ${g.off >= 0 ? "+" : ""}${g.off} ms off · ${shown.filter(x => x.bad).length} edits lost to an older timestamp`, { anchor: "start", size: 11, bold: true, fill: g.bad ? C.bad : C.text })}</g>; })()}
      {T(20, 318, "Each dot is an edit that happened after the previous one. Red = the newer edit got an older timestamp and would be thrown away.", { anchor: "start", size: 10, fill: C.muted })}
    </svg>
  );
}

// ---------------------------------------------------------------- CAP: three replicas and a partition
function CapView({ f, info }: { f: Any; info: LabInfo }) {
  const pos = [[120, 70], [520, 70], [320, 230]], iso = info.env.iso;
  return (
    <svg viewBox="0 0 640 330" className="labsvg">
      {[[0, 1], [0, 2], [1, 2]].map(([a, b]) => { const cut = f.part && (a === iso || b === iso); return <line key={a + "-" + b} x1={pos[a][0]} y1={pos[a][1]} x2={pos[b][0]} y2={pos[b][1]} stroke={cut ? C.bad : C.ok} strokeWidth={cut ? 2 : 3} strokeDasharray={cut ? "6 6" : ""} />; })}
      {pos.map((p, i) => <g key={i}><rect x={p[0] - 70} y={p[1] - 28} width={140} height={56} rx={10} fill={f.part && i === iso ? "var(--danger-soft)" : C.soft} stroke={f.part && i === iso ? C.bad : C.pri} strokeWidth={2} />
        {T(p[0], p[1] - 6, `Replica ${i + 1}`, { bold: true })}{T(p[0], p[1] + 14, `${f.fresh[i]} of 6 items up to date`, { size: 11, fill: f.fresh[i] < 6 ? C.warn : C.muted })}</g>)}
      {T(320, 20, f.part ? "NETWORK PARTITION: the dashed links are cut" : "Network healthy", { bold: true, fill: f.part ? C.bad : C.ok })}
      {f.ops.map((o: Any[], k: number) => <g key={k}><rect x={20 + k * 44} y={276} width={38} height={22} rx={5} fill={!o[2] ? C.bad : o[3] ? C.warn : C.ok} />{T(39 + k * 44, 291, `${o[0] === "w" ? "W" : "R"}${o[1] + 1}`, { size: 10, fill: "#fff", bold: true })}</g>)}
      {T(20, 318, `refused ${f.fails} · stale reads ${f.stale} · lost writes ${f.lost} (green = served, orange = stale answer, red = refused; the number is the replica asked)`, { anchor: "start", size: 10, fill: C.muted })}
    </svg>
  );
}

// A clock that runs from 0 to 1 over `ms`, restarting whenever `key` changes. Used by views that animate on their own timeline.
function useClock(ms: number, key: unknown, finished = false): number {
  const [p, setP] = useState(0);
  useEffect(() => {
    setP(0);
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => { const v = Math.min(1, (now - t0) / ms); setP(v); if (v < 1) raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [key, ms]);
  return finished ? 1 : p;
}
const CLOCK_MS: Record<string, number> = { journey: 7000, slo: 9000 };
const tri = (x: number) => 1 - Math.abs((x % 1) * 2 - 1);      // 0 -> 1 -> 0

// ---------------------------------------------------------------- journey: a packet travels between you and the servers while the clock runs
function JourneyView({ run, info, finished }: { run: LabRun; info: LabInfo; finished: boolean }) {
  const segs: Any[] = run.segments ?? [], total = run.stats.total, target = info.env.target, rtt = info.env.rtt, cdn = !!run.settings.cdn;
  const p = useClock(CLOCK_MS.journey, run, finished), now = p * total;
  if (!segs.length) return null;
  const cur = segs.find(s => now >= s.start && now < s.start + s.dur) ?? segs[segs.length - 1];
  const col: Record<string, string> = { setup: C.warn, wait: C.pri, download: C.ok };
  const isImg = /image|Img/i.test(cur.name), isDns = /DNS/.test(cur.name);
  const tx = isDns ? 300 : isImg && cdn ? 300 : 560, ty = isDns ? 62 : isImg && cdn ? 150 : 150;
  const trips = Math.max(1, Math.round(cur.dur / ((isImg && cdn) ? 10 : isDns ? cur.dur : rtt)));
  const ph = Math.max(0, Math.min(1, (now - cur.start) / Math.max(1, cur.dur)));
  const d = tri(ph * trips), dx = 70 + (tx - 70) * d, dy = 150 + (ty - 150) * d;
  const done = now >= total;
  const sc = 470 / Math.max(total, target) / 1.05;
  return (
    <svg viewBox="0 0 640 330" className="labsvg">
      <rect x={20} y={128} width={56} height={44} rx={9} fill={C.soft} stroke={C.line} />{T(48, 155, "You", { bold: true })}
      <rect x={532} y={128} width={92} height={44} rx={9} fill={C.soft} stroke={C.line} />{T(578, 150, "Origin", { bold: true })}{T(578, 164, "server", { size: 10, fill: C.muted })}
      <rect x={256} y={36} width={88} height={34} rx={9} fill={C.soft} stroke={C.line} />{T(300, 58, "DNS", { bold: true })}
      {cdn && <g><rect x={256} y={132} width={88} height={34} rx={9} fill={C.soft} stroke={C.ok} />{T(300, 154, "CDN edge", { bold: true })}</g>}
      <line x1={76} y1={150} x2={532} y2={150} stroke={C.line} strokeDasharray="4 4" />
      {!done && <circle cx={dx} cy={dy} r={9} fill={col[cur.kind]} />}
      {T(20, 20, done ? `Page loaded in ${total} ms${total <= target ? ": goal met" : ": too slow"}` : `${cur.name}`, { anchor: "start", bold: true, fill: done ? (total <= target ? C.ok : C.bad) : C.text })}
      {T(620, 20, `${Math.round(Math.min(now, total))} ms`, { anchor: "end", bold: true, size: 15, fill: now > target ? C.bad : C.text })}
      {segs.map((s, i) => { const w = Math.max(0, Math.min(s.dur, now - s.start)) * sc; return <g key={i}><rect x={150 + s.start * sc} y={200 + i * 14} width={Math.max(0, w)} height={10} rx={3} fill={col[s.kind]} opacity={s === cur && !done ? 1 : 0.7} />{T(146, 209 + i * 14, s.name.replace(" (new connections)", "").slice(0, 24), { anchor: "end", size: 9, fill: C.muted })}</g>; })}
      <line x1={150 + target * sc} y1={196} x2={150 + target * sc} y2={196 + segs.length * 14 + 6} stroke={C.bad} strokeDasharray="4 3" />{T(150 + target * sc, 322, `goal ${target} ms`, { size: 10, fill: C.bad })}
    </svg>
  );
}

// ---------------------------------------------------------------- SLO: a month plays out, incidents appear, the budget drains, people are paged
function SloView({ frames, run, info, finished }: { frames: Any[]; run: LabRun; info: LabInfo; finished: boolean }) {
  const p = useClock(CLOCK_MS.slo, run, finished), day = p * 30, budget = run.stats.budget;
  const seen = frames.filter(g => g.day <= day);
  const spent = seen.length ? seen[seen.length - 1].spent : 0, pct = Math.min(1.2, spent / budget);
  const x = (d: number) => 20 + (d / 30) * 600;
  return (
    <svg viewBox="0 0 640 330" className="labsvg">
      {T(20, 20, `Error budget for the month: ${budget} minutes of full outage`, { anchor: "start", bold: true })}
      <rect x={20} y={32} width={600} height={26} rx={7} fill={C.soft} stroke={C.line} /><rect x={20} y={32} width={Math.min(600, pct * 600)} height={26} rx={7} fill={pct > 1 ? C.bad : pct > 0.7 ? C.warn : C.ok} />
      {T(320, 50, `${spent.toFixed(1)} of ${budget} minutes spent (${Math.round(pct * 100)}%)`, { bold: true, fill: "#fff" })}
      <line x1={20} y1={160} x2={620} y2={160} stroke={C.line} strokeWidth={2} />
      {[0, 5, 10, 15, 20, 25, 30].map(d => <g key={d}><line x1={x(d)} y1={156} x2={x(d)} y2={164} stroke={C.line} />{T(x(d), 180, `day ${d}`, { size: 9, fill: C.muted })}</g>)}
      {seen.map((g, i) => { const r = Math.min(30, 6 + g.cost * 1.4), fresh = day - g.day < 1.6; return <g key={i}><circle cx={x(g.day)} cy={150 - r / 2} r={r} fill={g.paged ? C.bad : C.pri} opacity={0.6} />{T(x(g.day), 150 - r - 8, `${g.len} min at ${g.err}%`, { size: 9, fill: C.muted })}{g.paged && fresh && <text x={x(g.day)} y={110 - r} textAnchor="middle" fontSize="12" fontWeight={700} fill={C.bad}>PAGED</text>}</g>; })}
      <line x1={x(day)} y1={90} x2={x(day)} y2={170} stroke={C.text} strokeWidth={2} />{T(x(day), 84, `day ${Math.floor(day)}`, { size: 10, bold: true })}
      {T(20, 230, `Pages sent so far: ${seen.filter(g => g.paged).length} · incidents so far: ${seen.length} of ${frames.length}`, { anchor: "start", bold: true })}
      {T(20, 252, "Blue = nobody was paged, so it ran its full length. Red = a human was paged and fixed it quickly.", { anchor: "start", size: 10, fill: C.muted })}
      {T(20, 284, `Users need ${info.env.needs}% availability. Your SLO: ${run.settings.slo}%. Alert rule: ${run.settings.alert === "any" ? "page on every spike" : run.settings.alert === "burn" ? "page on fast burn" : "page on slow burn"}.`, { anchor: "start", size: 11, fill: C.muted })}
    </svg>
  );
}

// ---------------------------------------------------------------- deployment: a crowd of users is moved to the new version
function DeployView({ frames, i }: { frames: Any[]; i: number }) {
  const f = frames[i], bad = f.failed > 0 ? Math.min(1, f.failed / Math.max(1, 1000 * f.frac)) : 0, exposed = Math.round(f.frac * 100), red = f.frac > 0 ? Math.round(bad * exposed) : 0;
  const bw = 580 / frames.length, maxFail = Math.max(10, ...frames.map(g => g.failed));
  return (
    <svg viewBox="0 0 640 330" className="labsvg">
      {T(20, 20, `100 users. Grey = old version, blue = new version, red = seeing errors.  ${f.state === "rolled_back" ? "ROLLED BACK" : f.state === "rolling" ? "rolling out" : "not started"}`, { anchor: "start", bold: true, fill: f.state === "rolled_back" ? C.ok : C.text })}
      {Array.from({ length: 100 }).map((_, k) => { const c = Math.floor(k / 20), r = k % 20; const isNew = k < exposed; return <rect key={k} x={24 + r * 29} y={34 + c * 30} width={24} height={24} rx={6} fill={isNew ? (k < red ? C.bad : C.pri) : "var(--line)"} />; })}
      <line x1={20} y1={300} x2={620} y2={300} stroke={C.line} />
      {frames.slice(0, i + 1).map((g, k) => <rect key={k} x={20 + k * bw} y={300 - (g.failed / maxFail) * 60} width={Math.max(1, bw - 1)} height={(g.failed / maxFail) * 60} fill={C.bad} opacity={0.8} />)}
      {T(20, 322, `failed requests per tick (red bars) · users hurt so far: ${f.hurt.toLocaleString()}`, { anchor: "start", size: 11, bold: true, fill: f.hurt > 0 ? C.bad : C.muted })}
    </svg>
  );
}

// ---------------------------------------------------------------- streaming: producer, partitions, consumers; lag builds as dots queue up
function StreamingView({ f }: { f: Any }) {
  const n = f.lag.length, bw = Math.min(32, 400 / n), gap = Math.min(10, 20 - n * 0.5), x0 = 110, mx = Math.max(300, ...f.lag), cols = ["#2563EB", "#16A34A", "#D97706", "#9333EA", "#DC2626", "#0891B2", "#65A30D", "#DB2777", "#0D9488", "#CA8A04", "#7C3AED", "#EA580C"];
  const px = (i: number) => x0 + i * (bw + gap) + bw / 2, consumers = Array.from(new Set<number>(f.assign));
  return (
    <svg viewBox="0 0 640 330" className="labsvg">
      {T(20, 20, `Events flow in from the producer. ${f.alive} consumer(s) alive${f.paused ? ". REBALANCING: nobody is reading right now" : ""}`, { anchor: "start", bold: true, fill: f.paused ? C.bad : C.text })}
      <rect x={14} y={120} width={66} height={44} rx={9} fill={C.soft} stroke={C.line} />{T(47, 147, "Producer", { size: 11, bold: true })}
      {f.lag.map((v: number, i: number) => {
        const h = (v / mx) * 120, c = f.assign[i];
        return (
          <g key={i}>
            <line x1={80} y1={142} x2={px(i)} y2={170} stroke={C.line} />
            {[0, 1].map(k => <circle key={k} r={3.5} fill={C.pri}><animateMotion dur="1.1s" begin={`${(k * 0.55 + i * 0.07).toFixed(2)}s`} repeatCount="indefinite" path={`M80,142 L${px(i)},170`} /></circle>)}
            <rect x={x0 + i * (bw + gap)} y={170} width={bw} height={130} rx={4} fill={C.soft} stroke={C.line} />
            <rect x={x0 + i * (bw + gap)} y={300 - h} width={bw} height={h} rx={4} fill={f.paused ? C.warn : cols[(c ?? 0) % 12]} />
            {T(px(i), 316, `P${i + 1}`, { size: 9, bold: true })}
            {c !== undefined && !f.paused && <circle r={3.5} fill={cols[c % 12]}><animateMotion dur="1.4s" begin={`${(i * 0.09).toFixed(2)}s`} repeatCount="indefinite" path={`M${px(i)},170 L560,${60 + c * 24}`} /></circle>}
          </g>
        );
      })}
      {consumers.map(c => <g key={c}><rect x={520} y={46 + c * 24} width={100} height={20} rx={5} fill={cols[c % 12]} opacity={0.9} />{T(570, 60 + c * 24, `Consumer ${c + 1}`, { size: 10, fill: "#fff", bold: true })}</g>)}
      {T(620, 322, `total lag ${f.total.toLocaleString()} events`, { anchor: "end", size: 11, bold: true })}
    </svg>
  );
}

// ---------------------------------------------------------------- storage engines: watch a write travel, a buffer fill, files flush and merge
function EnginesView({ f, frames, i, run }: { f: Any; frames: Any[]; i: number; run: LabRun }) {
  const btree = run.settings.engine === "btree", last = frames[frames.length - 1], mx = Math.max(1, last.write_cost, last.read_cost, last.disk_writes);
  const recent = frames.slice(Math.max(0, i - 25), i + 1).reverse().find(g => g.ev), isW = f.op === "w";
  const leaf = f.page, leafX = (k: number) => 34 + k * 66;
  return (
    <svg viewBox="0 0 640 330" className="labsvg">
      {T(20, 20, btree ? "B-tree: every write finds its page and changes it in place" : "LSM-tree: writes pile into a memory buffer, then flush as sorted files", { anchor: "start", bold: true })}
      {T(620, 20, isW ? "WRITE" : "READ", { anchor: "end", bold: true, fill: isW ? C.warn : C.pri })}
      {btree ? (
        <g>
          <rect x={270} y={40} width={100} height={26} rx={5} fill={C.soft} stroke={isW ? C.warn : C.pri} strokeWidth={2} />{T(320, 58, "root page", { size: 10 })}
          {[0, 1].map(k => <g key={k}><line x1={320} y1={66} x2={200 + k * 240} y2={100} stroke={C.line} /><rect x={150 + k * 240} y={100} width={100} height={26} rx={5} fill={C.soft} stroke={Math.floor(leaf / 4) === k ? (isW ? C.warn : C.pri) : C.line} strokeWidth={2} />{T(200 + k * 240, 118, "branch page", { size: 10 })}</g>)}
          {Array.from({ length: 8 }).map((_, k) => <g key={k}><line x1={200 + Math.floor(k / 4) * 240} y1={126} x2={leafX(k) + 24} y2={156} stroke={C.line} /><rect x={leafX(k)} y={156} width={52} height={26} rx={5} fill={k === leaf ? (isW ? C.warn : C.pri) : C.soft} stroke={C.line} />{T(leafX(k) + 26, 173, `page ${k + 1}`, { size: 9, fill: k === leaf ? "#fff" : C.text })}</g>)}
          {T(20, 206, isW ? "A write rewrites one page somewhere on the disk (a random write)." : "A read walks down the tree to one page.", { anchor: "start", size: 11, fill: C.muted })}
        </g>
      ) : (
        <g>
          <rect x={24} y={44} width={170} height={34} rx={6} fill={C.soft} stroke={C.line} /><rect x={24} y={44} width={170 * f.mem} height={34} rx={6} fill={C.warn} opacity={0.8} />{T(109, 66, "memory buffer", { size: 11, bold: true })}
          {isW && <circle r={4} fill={C.warn}><animateMotion dur="0.4s" repeatCount="indefinite" path="M10,100 L109,78" /></circle>}
          {Array.from({ length: Math.min(f.files, 14) }).map((_, k) => <rect key={k} x={236 + (k % 7) * 54} y={44 + Math.floor(k / 7) * 38} width={48} height={30} rx={5} fill={C.ok} opacity={0.85} />)}
          {T(236, 130, `${f.files} sorted file(s) on disk${f.files > 8 ? ": every read must check them all" : ""}`, { anchor: "start", size: 11, fill: f.files > 8 ? C.bad : C.muted })}
          {recent && T(24, 120, recent.ev === "flush" ? "The buffer filled and was flushed as a new file." : "Files were merged (compaction): extra disk work now, fewer files later.", { anchor: "start", size: 11, bold: true, fill: recent.ev === "flush" ? C.ok : C.warn })}
        </g>
      )}
      {[["Cost of writes so far", f.write_cost, C.warn], ["Cost of reads so far", f.read_cost, C.pri], ["Bytes written to disk", f.disk_writes, C.bad]].map((r, k) => <g key={k}>{T(20, 252 + k * 26, String(r[0]), { anchor: "start", size: 11 })}<rect x={200} y={240 + k * 26} width={Math.min(400, (Number(r[1]) / mx) * 400)} height={16} rx={4} fill={String(r[2])} /></g>)}
    </svg>
  );
}

// ---------------------------------------------------------------- microservices: a stream of requests runs down the chain and breaks where a service fails
function MicroView({ frames, run }: { frames: Any[]; run: LabRun }) {
  const path: string[] = run.stats.path, fails: Record<string, number> = run.stats.fails, w = Math.min(100, 560 / path.length), gap = (560 - w * path.length) / Math.max(1, path.length - 1);
  const sx = (k: number) => 40 + k * (w + gap);
  return (
    <svg viewBox="0 0 640 330" className="labsvg">
      {T(20, 20, `${run.stats.success}% of ${run.stats.reqs ?? 4000} checkouts worked. Each dot is one request.`, { anchor: "start", bold: true })}
      {path.map((n, k) => <g key={n}><rect x={sx(k)} y={70} width={w} height={46} rx={8} fill={fails[n] > 20 ? "var(--danger-soft)" : C.soft} stroke={fails[n] > 20 ? C.bad : C.line} />{T(sx(k) + w / 2, 98, n.length > 12 ? n.slice(0, 11) + "…" : n, { size: 11, bold: true })}{T(sx(k) + w / 2, 134, `${fails[n]} failed`, { size: 10, fill: fails[n] ? C.bad : C.muted })}</g>)}
      <line x1={14} y1={93} x2={626} y2={93} stroke={C.line} strokeDasharray="3 4" />
      {frames.map((g, i) => {
        const endK = g.broke ? path.indexOf(g.broke) : path.length - 1, ex = g.broke ? sx(endK) + w / 2 : 626, y = 93 + ((i * 7) % 5 - 2) * 6;
        const col = g.broke ? C.bad : g.degraded ? C.warn : C.ok;
        return <circle key={i} r={5} fill={col} cy={0} opacity={0}><set attributeName="opacity" to="1" begin={`${(i * 0.18).toFixed(2)}s`} fill="freeze" /><animateMotion dur={`${(0.35 + endK * 0.25).toFixed(2)}s`} begin={`${(i * 0.18).toFixed(2)}s`} fill="freeze" path={`M14,${y} L${ex},${y}`} />{g.broke && <animate attributeName="r" values="5;5;11;0" keyTimes="0;0.7;0.85;1" dur={`${(0.35 + endK * 0.25).toFixed(2)}s`} begin={`${(i * 0.18).toFixed(2)}s`} fill="freeze" />}</circle>;
      })}
      {T(20, 210, `Latency of the slowest 5%: ${run.stats.p95} ms · about ${run.stats.downtime} minutes of failure a month`, { anchor: "start", bold: true })}
      {T(20, 232, `${path.length} services in the critical path. Each one multiplies the chance something goes wrong.`, { anchor: "start", size: 11, fill: C.muted })}
      {T(20, 262, "Green = the checkout worked. Orange = it worked without an optional service (fallback). Red = it broke at that service.", { anchor: "start", size: 10, fill: C.muted })}
    </svg>
  );
}

function Field({ c, v, set, disabled }: { c: Control; v: Any; set: (v: Any) => void; disabled: boolean }) {
  return (
    <label className="labfield" title={c.help}>
      <span><b>{c.label}</b>{c.type === "range" && <span className="muted"> {v}{c.unit ?? ""}</span>}{c.type === "toggle" && <input type="checkbox" style={{ marginLeft: 10 }} checked={!!v} disabled={disabled} onChange={e => set(e.target.checked)} />}</span>
      {c.type === "range" && <input type="range" min={c.min} max={c.max} step={c.step} value={v} disabled={disabled} onChange={e => set(Number(e.target.value))} />}
      {c.type === "select" && <select value={v} disabled={disabled} onChange={e => set(e.target.value)}>{c.options.map(o => <option key={o[0]} value={o[0]}>{o[1]}</option>)}</select>}
      {c.type === "multi" && <span className="chips">{c.options.map(o => <button type="button" key={o[0]} className={"chip" + ((v as string[]).includes(o[0]) ? " on" : "")} disabled={disabled} onClick={() => set((v as string[]).includes(o[0]) ? (v as string[]).filter(x => x !== o[0]) : [...v, o[0]].slice(0, c.max))}>{o[1]}</button>)}</span>}
      <small className="muted">{c.help}</small>
    </label>
  );
}

export function Lab({ lessonId, level, takeaways }: { lessonId: string; level: number; takeaways?: string[] }) {
  const { loggedIn, refresh } = useAuth();
  const [info, setInfo] = useState<LabInfo | null>(null);
  const [set, setSet] = useState<Settings>({});
  const [run, setRun] = useState<LabRun | null>(null);
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [err, setErr] = useState("");
  const [saved, setSaved] = useState<number | null>(null);
  const [free, setFree] = useState(false);
  const timer = useRef<number | null>(null);
  const q = `?level=${level}`;

  useEffect(() => {
    setInfo(null); setRun(null); setErr(""); setSaved(null); setPlaying(false);
    api<LabInfo>("GET", `/api/games/${lessonId}/lab${q}`).then(i => { setInfo(i); setSet(Object.fromEntries(i.controls.map(c => [c.id, c.default]))); }).catch(e => setErr(String(e.message ?? e)));
  }, [lessonId, level]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!playing || !run) return;
    const every = CLOCK_MS[info?.kind ?? ""] ? CLOCK_MS[info!.kind] / run.frames.length : run.frames.length > 120 ? 12 : run.frames.length > 60 ? 70 : 110;
    timer.current = window.setInterval(() => setIdx(i => { if (i + 1 >= run.frames.length) { setPlaying(false); return i; } return i + 1; }), every);
    return () => { if (timer.current) window.clearInterval(timer.current); };
  }, [playing, run]);

  const go = async () => {
    setErr(""); setSaved(null);
    try {
      const r = await api<LabRun>("POST", `/api/games/${lessonId}/lab/simulate${q}`, { settings: set });
      setRun(r); setIdx(0); setPlaying(true);
      if (loggedIn) { const s = await api<{ xpGained: number }>("POST", `/api/games/${lessonId}/lab/submit${q}`, { settings: set }); setSaved(s.xpGained); void refresh(); }
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Could not run the lab."); }
  };

  const frames = useMemo(() => run?.frames ?? [], [run]);
  if (!info) return <div className="card">{err || "Loading the lab..."}</div>;
  const kind = info.kind, done = !!run && !playing && idx >= frames.length - 1;
  const f = frames[Math.min(idx, frames.length - 1)];
  const toggleSite = (id: string) => { if (playing) return; const cur = (set.sites as string[]) ?? []; setSet({ ...set, sites: cur.includes(id) ? cur.filter(x => x !== id) : [...cur, id].slice(0, 8) }); };
  let visual: ReactNode = <div className="muted" style={{ padding: 24, textAlign: "center" }}>Change the settings below, then press Run to watch it happen.</div>;
  if (kind === "cdn") {
    const rows = run ? frames.map(x => x.region) : [];
    visual = <CdnView f={{ ...(f ?? { t: -1 }), region: f?.region, _rows: rows, t: run ? idx : -1 }} info={info} set={set} toggle={toggleSite} />;
  } else if (run && f) {
    if (kind === "lb") visual = <LbView f={f} info={info} st={run.stats} />;
    if (kind === "cache") visual = <CacheView f={f} info={info} set={run.settings} />;
    if (kind === "queue") visual = <QueueView f={f} />;
    if (kind === "shard") visual = <ShardView f={f} run={run} info={info} />;
    if (kind === "limiter") visual = <LimiterView frames={frames} i={idx} />;
    if (kind === "breaker") visual = <BreakerView frames={frames} i={idx} info={info} />;
    if (kind === "autoscale") visual = <ScaleView frames={frames} i={idx} info={info} />;
    if (kind === "repl") visual = <ReplView f={f} info={info} />;
    if (kind === "tx") visual = <TxView frames={frames} i={Math.min(idx, frames.length - 1)} info={info} />;
    if (kind === "consensus") visual = <ConsensusView f={f} />;
    if (kind === "clocks") visual = <ClocksView frames={frames} i={idx} />;
    if (kind === "cap") visual = <CapView f={f} info={info} />;
    if (kind === "journey") visual = <JourneyView run={run} info={info} finished={done} />;
    if (kind === "slo") visual = <SloView frames={frames} run={run} info={info} finished={done} />;
    if (kind === "deploy") visual = <DeployView frames={frames} i={Math.min(idx, frames.length - 1)} />;
    if (kind === "streaming") visual = <StreamingView f={f} />;
    if (kind === "engines") visual = <EnginesView f={f} frames={frames} i={Math.min(idx, frames.length - 1)} run={run} />;
    if (kind === "micro") visual = <MicroView frames={frames} run={run} />;
  }
  const Sandbox = SANDBOXES[lessonId] as (() => JSX.Element) | undefined;
  if (free && Sandbox) return <div className="lab"><div className="modebar"><button className="btn sm" onClick={() => setFree(false)}>Challenge levels</button><button className="btn sm pri" disabled>Free play</button></div><Sandbox /></div>;
  return (
    <div className="lab">
      {Sandbox && <div className="modebar"><button className="btn sm pri" disabled>Challenge levels</button><button className="btn sm" onClick={() => setFree(true)}>Free play: poke it live</button></div>}
      <div className="card"><b>{info.title}</b><p>{info.brief}</p><p className="muted"><b>Goal:</b> {info.goal}</p></div>
      <div className="labgrid">
        <div className="card labctl">
          {info.controls.map(c => <Field key={c.id} c={c} v={set[c.id]} disabled={playing} set={v => setSet(s => ({ ...s, [c.id]: v }))} />)}
          <div className="row labrun">
            <button className="btn pri" onClick={go} disabled={playing}>{run ? "Run again" : "Run it"}</button>
            {playing && <button className="btn" onClick={() => setIdx(frames.length - 1)}>Skip to the end</button>}
          </div>
          {err && <p className="banner warn">{err}</p>}
        </div>
        <div className="card labview">{visual}</div>
      </div>
      {done && run && (
        <div className="card result">
          <Stars n={run.stars} big />
          <p>{run.stars === 3 ? "Excellent. This is about as good as it gets." : run.stars === 0 ? "Not good enough yet. Read what happened below, change a setting and run again." : "Good. You can still improve it."}</p>
          {saved !== null && <p className="muted">{saved > 0 ? `+${saved} XP` : "Saved."}</p>}
          {!loggedIn && <p className="muted">Log in to save your stars.</p>}
          <ul className="notes">{run.insights.map((t, i) => <li key={i}>{t}</li>)}</ul>
          {run.stars >= 2 && <Takeaways items={takeaways} />}
        </div>
      )}
    </div>
  );
}
