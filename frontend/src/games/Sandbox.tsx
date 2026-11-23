import { useEffect, useRef, useState, type ReactNode } from "react";

// Free play: a live, continuous simulation you poke while it runs. Click things, drag sliders, press buttons, and watch it react.
const C = { ok: "var(--success)", bad: "var(--danger)", warn: "var(--warning)", pri: "var(--primary)", line: "var(--line)", soft: "var(--bg-soft)", text: "var(--text)", muted: "var(--muted)" };
const T = (x: number, y: number, s: ReactNode, o: { size?: number; anchor?: "start" | "middle" | "end"; fill?: string; bold?: boolean } = {}) =>
  <text x={x} y={y} fontSize={o.size ?? 12} textAnchor={o.anchor ?? "middle"} fill={o.fill ?? C.text} fontWeight={o.bold ? 700 : 400}>{s}</text>;
const rnd = () => Math.random();

function useTick(ms: number, fn: () => void, running: boolean) {
  const f = useRef(fn);
  f.current = fn;
  useEffect(() => { if (!running) return; const id = setInterval(() => f.current(), ms); return () => clearInterval(id); }, [ms, running]);
}
function useLive<S>(init: () => S): [S, () => void, () => void] {
  const s = useRef<S>(null as unknown as S);
  if (s.current === null) s.current = init();
  const [, force] = useState(0);
  return [s.current, () => force(n => n + 1), () => { s.current = init(); force(n => n + 1); }];
}

function Shell({ title, hint, children, controls, running, setRunning, onReset, stats }: { title: string; hint: string; children: ReactNode; controls: ReactNode; running: boolean; setRunning: (b: boolean) => void; onReset: () => void; stats: ReactNode }) {
  return (
    <div className="sandbox">
      <div className="card"><b>{title}</b><p className="muted" style={{ margin: "4px 0 0" }}>{hint}</p></div>
      <div className="card labview">{children}</div>
      <div className="card sbstats">{stats}</div>
      <div className="card labctl">
        {controls}
        <div className="row labrun"><button className="btn" onClick={() => setRunning(!running)}>{running ? "Pause" : "Resume"}</button><button className="btn" onClick={onReset}>Start over</button></div>
      </div>
    </div>
  );
}
const Slider = ({ label, v, set, min, max, step = 1, unit = "" }: { label: string; v: number; set: (n: number) => void; min: number; max: number; step?: number; unit?: string }) =>
  <label className="labfield"><span><b>{label}</b><span className="muted"> {v}{unit}</span></span><input type="range" min={min} max={max} step={step} value={v} onChange={e => set(Number(e.target.value))} /></label>;
const Pick = ({ label, v, set, options }: { label: string; v: string; set: (s: string) => void; options: [string, string][] }) =>
  <label className="labfield"><span><b>{label}</b></span><select value={v} onChange={e => set(e.target.value)}>{options.map(o => <option key={o[0]} value={o[0]}>{o[1]}</option>)}</select></label>;
const Check = ({ label, v, set }: { label: string; v: boolean; set: (b: boolean) => void }) =>
  <label className="labfield"><span><b>{label}</b><input type="checkbox" style={{ marginLeft: 10 }} checked={v} onChange={e => set(e.target.checked)} /></span></label>;

// ------------------------------------------------------------------ load balancer
interface Req { size: number; left: number; born: number }
interface LbState { q: Req[][]; dead: boolean[]; rr: number; done: number; lost: number; wait: number; t: number; spike: number }
const LB_SPEED = [9, 9, 5, 9];
export function LbSandbox() {
  const [s, redraw, reset] = useLive<LbState>(() => ({ q: LB_SPEED.map(() => []), dead: LB_SPEED.map(() => false), rr: 0, done: 0, lost: 0, wait: 0, t: 0, spike: 0 }));
  const [running, setRunning] = useState(true);
  const [alg, setAlg] = useState("round_robin"), [hc, setHc] = useState(false), [rate, setRate] = useState(8), [big, setBig] = useState(15);
  useTick(450, () => {
    s.t++;
    const r = (s.spike > 0 ? rate * 2.5 : rate);
    if (s.spike > 0) s.spike--;
    const n = Math.max(0, Math.round(r + (rnd() - 0.5) * 3));
    for (let i = 0; i < n; i++) {
      const size = rnd() * 100 < big ? 8 : 1;
      const alive = LB_SPEED.map((_, k) => k).filter(k => !hc || !s.dead[k]);
      if (!alive.length) { s.lost++; continue; }
      let k: number;
      if (alg === "random") k = alive[Math.floor(rnd() * alive.length)];
      else if (alg === "least") k = alive.reduce((a, b) => s.q[a].reduce((x, y) => x + y.left, 0) / LB_SPEED[a] <= s.q[b].reduce((x, y) => x + y.left, 0) / LB_SPEED[b] ? a : b);
      else { k = alive[s.rr % alive.length]; s.rr++; }
      if (s.dead[k]) s.lost++; else s.q[k].push({ size, left: size, born: s.t });
    }
    LB_SPEED.forEach((sp, k) => {
      if (s.dead[k]) return;
      let cap = sp;
      while (s.q[k].length && cap > 0) { const it = s.q[k][0], w = Math.min(cap, it.left); it.left -= w; cap -= w; if (it.left <= 0.001) { s.q[k].shift(); s.done++; s.wait = s.wait * 0.9 + (s.t - it.born + 1) * 0.1; } }
    });
    redraw();
  }, running);
  const toggle = (k: number) => { s.dead[k] = !s.dead[k]; if (s.dead[k]) { s.lost += s.q[k].length; s.q[k] = []; } redraw(); };
  const w = 150;
  return (
    <Shell title="Free play: load balancer" hint="Click a server to crash it (click again to revive it). Press Spike to flood it. Change the algorithm while it runs and watch the queues react." running={running} setRunning={setRunning} onReset={reset}
      stats={<span>finished <b>{s.done}</b> · lost <b style={{ color: s.lost ? "var(--danger)" : undefined }}>{s.lost}</b> · typical wait <b>{s.wait.toFixed(1)}</b> ticks</span>}
      controls={<>
        <Pick label="Algorithm" v={alg} set={setAlg} options={[["round_robin", "Round robin"], ["random", "Random"], ["least", "Least work"]]} />
        <Slider label="Requests per tick" v={rate} set={setRate} min={2} max={24} />
        <Slider label="Share of big requests" v={big} set={setBig} min={0} max={50} unit="%" />
        <Check label="Health checks" v={hc} set={setHc} />
        <div className="row labrun"><button className="btn pri" onClick={() => { s.spike = 8; redraw(); }}>Spike traffic</button></div>
      </>}>
      <svg viewBox="0 0 640 320" className="labsvg">
        <rect x={250} y={8} width={140} height={32} rx={8} fill={C.pri} />{T(320, 29, "Load balancer", { bold: true, fill: "#fff" })}
        {LB_SPEED.map((sp, k) => {
          const x = 14 + k * (w + 8); let y = 296;
          return (
            <g key={k} style={{ cursor: "pointer" }} onClick={() => toggle(k)}>
              <line x1={320} y1={40} x2={x + w / 2} y2={80} stroke={s.dead[k] ? C.bad : C.line} strokeWidth={2} />
              <rect x={x} y={80} width={w} height={226} rx={8} fill={s.dead[k] ? "var(--danger-soft)" : C.soft} stroke={s.dead[k] ? C.bad : C.line} />
              {T(x + w / 2, 98, s.dead[k] ? `Server ${k + 1} DOWN` : `Server ${k + 1}${sp < 9 ? " (small)" : ""}`, { bold: true, size: 12, fill: s.dead[k] ? C.bad : C.text })}
              {T(x + w / 2, 112, `${s.q[k].length} waiting`, { size: 10, fill: C.muted })}
              {!s.dead[k] && s.q[k].slice(0, 12).map((it, j) => { const h = Math.max(6, Math.min(34, it.left * 4)); y -= h + 2; return y > 120 ? <rect key={j} x={x + 12} y={y} width={w - 24} height={h} rx={3} fill={it.size > 1 ? C.warn : C.pri} /> : null; })}
              {s.dead[k] && T(x + w / 2, 200, "✕", { size: 46, fill: C.bad })}
            </g>
          );
        })}
      </svg>
    </Shell>
  );
}

// ------------------------------------------------------------------ queue
interface Job { poison: boolean; tries: number; born: number }
interface QState { q: Job[]; workers: number; down: number; dlq: number; done: number; lost: number; t: number; maxAge: number; spike: number }
export function QueueSandbox() {
  const [s, redraw, reset] = useLive<QState>(() => ({ q: [], workers: 3, down: 0, dlq: 0, done: 0, lost: 0, t: 0, maxAge: 0, spike: 0 }));
  const [running, setRunning] = useState(true);
  const [rate, setRate] = useState(3), [retries, setRetries] = useState(3), [dlq, setDlq] = useState(false);
  useTick(450, () => {
    s.t++;
    const n = Math.round((s.spike > 0 ? rate * 3 : rate) + (rnd() - 0.5));
    if (s.spike > 0) s.spike--;
    for (let i = 0; i < n; i++) s.q.push({ poison: false, tries: 0, born: s.t });
    if (s.down > 0) { s.down--; if (s.down === 0) s.workers++; }
    for (let w = 0; w < s.workers; w++) {
      const j = s.q.shift();
      if (!j) break;
      if (j.poison) { j.tries++; if (retries >= 6 || j.tries <= retries) s.q.push(j); else if (dlq) s.dlq++; else s.lost++; }
      else { s.done++; s.maxAge = Math.max(s.maxAge * 0.95, s.t - j.born + 1); }
    }
    redraw();
  }, running);
  const oldest = s.q.filter(j => !j.poison).reduce((a, j) => Math.max(a, s.t - j.born), 0);
  return (
    <Shell title="Free play: queue and workers" hint="Press Poison to send a job that always fails. Crash a worker. Spike the traffic. Add workers, turn on the dead-letter queue, and see what saves you." running={running} setRunning={setRunning} onReset={reset}
      stats={<span>done <b>{s.done}</b> · waiting <b>{s.q.length}</b> · oldest healthy job has waited <b style={{ color: oldest > 8 ? "var(--danger)" : undefined }}>{oldest}</b> ticks · parked in dead-letter queue <b>{s.dlq}</b></span>}
      controls={<>
        <Slider label="Jobs per tick" v={rate} set={setRate} min={0} max={12} />
        <Slider label="Retries for a failed job (6 = forever)" v={retries} set={setRetries} min={0} max={6} />
        <Check label="Dead-letter queue" v={dlq} set={setDlq} />
        <div className="row labrun">
          <button className="btn" onClick={() => { s.workers++; redraw(); }}>Add a worker</button>
          <button className="btn" onClick={() => { if (s.workers > 0) { s.workers--; s.down = 6; } redraw(); }}>Crash a worker</button>
          <button className="btn" onClick={() => { s.q.unshift({ poison: true, tries: 0, born: s.t }); redraw(); }}>Poison message</button>
          <button className="btn pri" onClick={() => { s.spike = 8; redraw(); }}>Spike traffic</button>
        </div>
      </>}>
      <svg viewBox="0 0 640 300" className="labsvg">
        {T(20, 20, `Queue (${s.q.length})`, { anchor: "start", bold: true })}
        <rect x={20} y={30} width={600} height={50} rx={8} fill={C.soft} stroke={C.line} />
        {s.q.slice(0, 28).map((j, k) => <rect key={k} x={26 + k * 21} y={38} width={17} height={34} rx={3} fill={j.poison ? C.bad : C.pri} />)}
        {T(20, 106, `Workers (${s.workers}${s.down ? `, ${1} restarting` : ""})`, { anchor: "start", bold: true })}
        {Array.from({ length: Math.min(16, s.workers) }).map((_, k) => <g key={k}><rect x={20 + k * 38} y={116} width={32} height={32} rx={6} fill={C.ok} />{T(36 + k * 38, 136, "W", { size: 11, fill: "#fff", bold: true })}</g>)}
        {s.down > 0 && T(20 + Math.min(16, s.workers) * 38 + 6, 136, "a worker crashed and is restarting…", { anchor: "start", size: 11, fill: C.bad })}
        {T(20, 184, `Dead-letter queue (${s.dlq})`, { anchor: "start", bold: true })}
        {Array.from({ length: Math.min(28, s.dlq) }).map((_, k) => <rect key={k} x={20 + k * 21} y={194} width={17} height={30} rx={3} fill={C.bad} opacity={0.6} />)}
        {T(20, 262, "blue = healthy job · red = a poison job that always fails", { anchor: "start", size: 11, fill: C.muted })}
      </svg>
    </Shell>
  );
}

// ------------------------------------------------------------------ autoscaling
interface AState { ready: number; booting: number[]; load: number[]; cap: number[]; dropped: number; cost: number; t: number; flash: number; cool: number }
export function AutoscaleSandbox() {
  const [s, redraw, reset] = useLive<AState>(() => ({ ready: 2, booting: [], load: [], cap: [], dropped: 0, cost: 0, t: 0, flash: 0, cool: 0 }));
  const [running, setRunning] = useState(true);
  const [traffic, setTraffic] = useState(40), [auto, setAuto] = useState(false), [up, setUp] = useState(75), [down, setDown] = useState(30);
  useTick(500, () => {
    s.t++;
    s.booting = s.booting.map(x => x - 1);
    s.ready += s.booting.filter(x => x <= 0).length;
    s.booting = s.booting.filter(x => x > 0);
    const load = Math.round((s.flash > 0 ? traffic * 4 : traffic) * (0.92 + rnd() * 0.16));
    if (s.flash > 0) s.flash--;
    const cap = s.ready * 10;
    if (auto && s.cool <= 0) {
      const util = cap ? (load / cap) * 100 : 999;
      if (util > up) { s.booting.push(4); s.cool = 1; } else if (util < down && s.ready > 1 && !s.booting.length) { s.ready--; s.cool = 1; }
    }
    s.cool--;
    s.dropped += Math.max(0, load - cap);
    s.cost += s.ready + s.booting.length;
    s.load = [...s.load, load].slice(-60); s.cap = [...s.cap, cap].slice(-60);
    redraw();
  }, running);
  const mx = Math.max(60, ...s.load, ...s.cap) * 1.1, bw = 600 / 60, y = (v: number) => 290 - (v / mx) * 120;
  const path = (a: number[]) => a.map((v, i) => `${i ? "L" : "M"}${20 + i * bw},${y(v)}`).join(" ");
  const last = s.load[s.load.length - 1] ?? 0, lastCap = s.cap[s.cap.length - 1] ?? 0;
  return (
    <Shell title="Free play: autoscaling" hint="Drag the traffic slider, or press Flash sale. Add and remove servers yourself, or switch on the autoscaler and see whether it keeps up. New servers take a few ticks to boot." running={running} setRunning={setRunning} onReset={reset}
      stats={<span>servers up <b>{s.ready}</b>{s.booting.length ? ` (+${s.booting.length} booting)` : ""} · requests dropped <b style={{ color: s.dropped ? "var(--danger)" : undefined }}>{s.dropped}</b> · running cost <b>{s.cost}</b></span>}
      controls={<>
        <Slider label="Traffic (requests per tick)" v={traffic} set={setTraffic} min={5} max={150} />
        <Check label="Autoscaler on" v={auto} set={setAuto} />
        <Slider label="Add a server above" v={up} set={setUp} min={40} max={95} step={5} unit="%" />
        <Slider label="Remove a server below" v={down} set={setDown} min={10} max={60} step={5} unit="%" />
        <div className="row labrun">
          <button className="btn" onClick={() => { s.booting.push(4); redraw(); }}>Add a server</button>
          <button className="btn" onClick={() => { if (s.ready > 1) s.ready--; redraw(); }}>Remove a server</button>
          <button className="btn pri" onClick={() => { s.flash = 10; redraw(); }}>Flash sale</button>
        </div>
      </>}>
      <svg viewBox="0 0 640 320" className="labsvg">
        {T(20, 18, `Traffic ${last} per tick · capacity ${lastCap}${last > lastCap ? " · DROPPING REQUESTS" : ""}`, { anchor: "start", bold: true, fill: last > lastCap ? C.bad : C.text })}
        {Array.from({ length: Math.min(20, s.ready + s.booting.length) }).map((_, k) => { const b = k >= s.ready; return <g key={k}><rect x={20 + (k % 10) * 58} y={30 + Math.floor(k / 10) * 40} width={50} height={32} rx={6} fill={b ? C.warn : C.ok} opacity={b ? 0.55 : 0.9} />{T(45 + (k % 10) * 58, 51 + Math.floor(k / 10) * 40, b ? "boot" : "up", { size: 11, fill: "#fff", bold: true })}</g>; })}
        {s.load.map((v, i) => v > (s.cap[i] ?? 0) && <rect key={i} x={20 + i * bw} y={y(v)} width={bw} height={Math.max(1, y(s.cap[i] ?? 0) - y(v))} fill={C.bad} opacity={0.45} />)}
        <path d={path(s.cap)} fill="none" stroke={C.ok} strokeWidth={3} /><path d={path(s.load)} fill="none" stroke={C.pri} strokeWidth={2.4} />
        {T(20, 312, "blue: traffic · green: capacity · red: dropped", { anchor: "start", size: 10, fill: C.muted })}
      </svg>
    </Shell>
  );
}

// ------------------------------------------------------------------ rate limiter
interface Lim { tok: number; win: number; cnt: number; log: number[] }
interface LState { lim: Lim[]; t: number; stat: number[]; last: number[]; burst: number }
const NCLI = 6;   // clients 0..4 are real users, client 5 is a bot
export function LimiterSandbox() {
  const [s, redraw, reset] = useLive<LState>(() => ({ lim: Array.from({ length: NCLI }, () => ({ tok: 5, win: 0, cnt: 0, log: [] })), t: 0, stat: [0, 0, 0, 0], last: [0, 0, 0, 0], burst: 0 }));
  const [running, setRunning] = useState(true);
  const [algo, setAlgo] = useState("fixed"), [limit, setLimit] = useState(5), [refill, setRefill] = useState(2), [bot, setBot] = useState(12);
  useTick(600, () => {
    s.t++;
    s.last = [0, 0, 0, 0];
    for (let c = 0; c < NCLI; c++) {
      const isBot = c === NCLI - 1;
      let n = isBot ? Math.round(bot + (s.burst > 0 ? 40 : 0)) : (rnd() < 0.7 ? 1 : 0) + (rnd() < 0.06 ? 6 : 0);
      if (isBot && s.burst > 0) s.burst = 0;
      const L = s.lim[c];
      L.tok = Math.min(limit, L.tok + refill);
      for (let i = 0; i < n; i++) {
        let ok = false;
        if (algo === "fixed") { if (L.win !== s.t) { L.win = s.t; L.cnt = 0; } if (L.cnt < limit) { L.cnt++; ok = true; } }
        else if (algo === "sliding") { L.log = L.log.filter(x => x > s.t - 3); if (L.log.length < limit * 3) { L.log.push(s.t); ok = true; } }
        else if (L.tok >= 1) { L.tok--; ok = true; }
        const idx = (isBot ? 2 : 0) + (ok ? 0 : 1);
        s.stat[idx]++; s.last[idx]++;
      }
    }
    redraw();
  }, running);
  const lu = s.stat[0] + s.stat[1], lb = s.stat[2] + s.stat[3];
  const dots = (n: number, y: number, color: string, pass: boolean) => Array.from({ length: Math.min(10, n) }).map((_, k) => <circle key={`${y}${pass}${k}`} r={4} fill={color}><animateMotion dur={pass ? "0.8s" : "0.5s"} begin={`${k * 0.04}s`} fill="freeze" path={pass ? `M70,${y + (k % 4) * 8 - 12} L540,${y + (k % 4) * 8 - 12}` : `M70,${y + (k % 4) * 8 - 12} L300,${y + (k % 4) * 8 - 12} L255,${y + (k % 2 ? 24 : -24)}`} /></circle>);
  return (
    <Shell title="Free play: rate limiter" hint="Turn up the bot and press Burst. Switch between the three algorithms while it runs. Real users sometimes click six times at once, so watch whether they get blocked too." running={running} setRunning={setRunning} onReset={reset}
      stats={<span>real users: <b style={{ color: "var(--success)" }}>{s.stat[0]} let in</b>, <b style={{ color: s.stat[1] ? "var(--danger)" : undefined }}>{s.stat[1]} blocked ({lu ? Math.round(s.stat[1] / lu * 100) : 0}%)</b> · bot: <b>{s.stat[2]} let in</b>, {s.stat[3]} blocked ({lb ? Math.round(s.stat[3] / lb * 100) : 0}%)</span>}
      controls={<>
        <Pick label="Algorithm" v={algo} set={setAlgo} options={[["fixed", "Fixed window"], ["sliding", "Sliding window"], ["bucket", "Token bucket"]]} />
        <Slider label="Allowed per tick (and bucket size)" v={limit} set={setLimit} min={1} max={20} />
        <Slider label="Token refill per tick" v={refill} set={setRefill} min={1} max={10} />
        <Slider label="Bot requests per tick" v={bot} set={setBot} min={0} max={30} />
        <div className="row labrun"><button className="btn pri" onClick={() => { s.burst = 1; redraw(); }}>Burst: bot sends 40 at once</button></div>
      </>}>
      <svg viewBox="0 0 640 300" className="labsvg">
        {T(20, 18, "Real users (top) and a bot (bottom) send requests through the limiter. Green gets in, red is turned away.", { anchor: "start", size: 11, bold: true })}
        <rect x={14} y={60} width={52} height={36} rx={7} fill={C.soft} stroke={C.line} />{T(40, 83, "Users", { size: 10 })}
        <rect x={14} y={150} width={52} height={36} rx={7} fill={C.soft} stroke={C.line} />{T(40, 173, "Bot", { size: 10 })}
        <rect x={296} y={44} width={10} height={160} rx={4} fill={C.text} opacity={0.75} />{T(301, 220, "limiter", { size: 10, bold: true })}
        <rect x={548} y={90} width={72} height={60} rx={8} fill={C.soft} stroke={C.line} />{T(584, 124, "Your API", { size: 11, bold: true })}
        <g key={s.t}>{dots(s.last[0], 78, C.ok, true)}{dots(s.last[1], 78, C.bad, false)}{dots(s.last[2], 168, C.warn, true)}{dots(s.last[3], 168, C.bad, false)}</g>
        {T(20, 262, `this tick: users ${s.last[0]} in / ${s.last[1]} out · bot ${s.last[2]} in / ${s.last[3]} out`, { anchor: "start", size: 11, fill: C.muted })}
      </svg>
    </Shell>
  );
}

// ------------------------------------------------------------------ consensus
interface RNode { role: "F" | "C" | "L"; term: number; voted: number | null; votes: number; timer: number; alive: boolean; hb: number }
interface Msg { kind: "rv" | "vote" | "hb"; a: number; b: number; tm: number; at: number }
interface CState { n: RNode[]; msgs: Msg[]; shown: Msg[]; t: number; elections: number; split: boolean; noLeader: number }
const NN = 5;
export function ConsensusSandbox() {
  const [rand, setRand] = useState(true), [hbEvery, setHb] = useState(2), [emin, setEmin] = useState(6), [unsafe, setUnsafe] = useState(false);
  const mk = (): CState => ({ n: Array.from({ length: NN }, () => ({ role: "F" as const, term: 0, voted: null, votes: 0, timer: 6 + Math.floor(rnd() * 6), alive: true, hb: 0 })), msgs: [], shown: [], t: 0, elections: 0, split: false, noLeader: 0 });
  const [s, redraw, reset] = useLive<CState>(mk);
  const [running, setRunning] = useState(true);
  const group = (k: number) => (s.split && (k === 0 || k === 1) ? 1 : 0);
  const need = unsafe ? 2 : 3;
  const timeout = () => (rand ? emin + Math.floor(rnd() * (emin + 1)) : emin);
  const send = (kind: Msg["kind"], a: number, b: number, tm: number) => { if (s.n[a].alive && s.n[b].alive && group(a) === group(b)) s.msgs.push({ kind, a, b, tm, at: s.t + 1 }); };
  useTick(500, () => {
    s.t++;
    s.shown = [];
    const due = s.msgs.filter(m => m.at === s.t);
    s.msgs = s.msgs.filter(m => m.at > s.t);
    for (const m of due) {
      const b = s.n[m.b];
      if (!b.alive || !s.n[m.a].alive || group(m.a) !== group(m.b)) continue;
      s.shown.push(m);
      if (m.tm > b.term) { b.term = m.tm; b.role = "F"; b.voted = null; }
      if (m.kind === "rv" && m.tm === b.term && (b.voted === null || b.voted === m.a)) { b.voted = m.a; b.timer = timeout(); send("vote", m.b, m.a, m.tm); }
      else if (m.kind === "vote" && b.role === "C" && m.tm === b.term) { b.votes++; if (b.votes >= need) { b.role = "L"; b.hb = 0; } }
      else if (m.kind === "hb" && m.tm >= b.term) { b.term = m.tm; b.role = "F"; b.timer = timeout(); }
    }
    s.n.forEach((nd, i) => {
      if (!nd.alive) return;
      if (nd.role === "L") { if (nd.hb <= 0) { for (let j = 0; j < NN; j++) if (j !== i) send("hb", i, j, nd.term); nd.hb = hbEvery; } nd.hb--; }
      else { nd.timer--; if (nd.timer <= 0) { nd.role = "C"; nd.term++; nd.voted = i; nd.votes = 1; nd.timer = timeout(); s.elections++; for (let j = 0; j < NN; j++) if (j !== i) send("rv", i, j, nd.term); } }
    });
    const leaders = usable();
    if (!leaders.length) s.noLeader++;
    redraw();
  }, running);
  function usable(): number[] {
    return s.n.map((nd, i) => ({ nd, i })).filter(({ nd, i }) => nd.alive && nd.role === "L" && s.n.filter((o, j) => o.alive && group(j) === group(i)).length >= need).map(x => x.i);
  }
  const leaders = usable();
  const pos = s.n.map((_, k) => [320 + 150 * Math.sin((k / NN) * 2 * Math.PI), 140 - 95 * Math.cos((k / NN) * 2 * Math.PI)]);
  const fill = (nd: RNode) => !nd.alive ? "#9CA3AF" : nd.role === "L" ? C.ok : nd.role === "C" ? C.warn : C.pri;
  return (
    <Shell title="Free play: leader election" hint="Click a node to crash it (click again to revive). Press Split the network to cut N1 and N2 off from the rest. Try fixed timeouts and watch nodes keep splitting the vote, or allow any 2 nodes to elect a leader and watch two leaders appear." running={running} setRunning={setRunning} onReset={reset}
      stats={<span>{leaders.length === 0 ? <b style={{ color: "var(--danger)" }}>no usable leader (writes refused)</b> : leaders.length === 1 ? <b style={{ color: "var(--success)" }}>leader: N{leaders[0] + 1}</b> : <b style={{ color: "var(--danger)" }}>TWO leaders: split brain!</b>} · elections started {s.elections} · ticks without a leader {s.noLeader}</span>}
      controls={<>
        <Check label="Random election timeouts" v={rand} set={setRand} />
        <Slider label="Shortest election timeout" v={emin} set={setEmin} min={3} max={16} unit=" ticks" />
        <Slider label="Heartbeat every" v={hbEvery} set={setHb} min={1} max={8} unit=" ticks" />
        <Check label="Any 2 nodes can elect a leader (risky)" v={unsafe} set={setUnsafe} />
        <div className="row labrun"><button className="btn pri" onClick={() => { s.split = !s.split; redraw(); }}>{s.split ? "Heal the network" : "Split the network"}</button></div>
      </>}>
      <svg viewBox="0 0 640 300" className="labsvg">
        {s.split && <line x1={170} y1={30} x2={470} y2={270} stroke={C.bad} strokeWidth={3} strokeDasharray="8 6" />}
        {s.shown.map((m, k) => <g key={k}><line x1={pos[m.a][0]} y1={pos[m.a][1]} x2={pos[m.b][0]} y2={pos[m.b][1]} stroke={m.kind === "hb" ? C.ok : m.kind === "rv" ? C.warn : C.pri} strokeWidth={1.6} opacity={0.6} /><circle r={4} fill={m.kind === "hb" ? C.ok : m.kind === "rv" ? C.warn : C.pri}><animateMotion dur="0.45s" fill="freeze" path={`M${pos[m.a][0]},${pos[m.a][1]} L${pos[m.b][0]},${pos[m.b][1]}`} /></circle></g>)}
        {s.n.map((nd, k) => (
          <g key={k} style={{ cursor: "pointer" }} onClick={() => { nd.alive = !nd.alive; if (!nd.alive) nd.role = "F"; else nd.timer = timeout(); redraw(); }}>
            <circle cx={pos[k][0]} cy={pos[k][1]} r={36} fill={fill(nd)} stroke={s.split ? (group(k) ? C.bad : C.text) : "none"} strokeWidth={4} strokeDasharray={s.split ? "6 3" : ""} />
            {T(pos[k][0], pos[k][1] - 2, `N${k + 1}`, { fill: "#fff", bold: true, size: 14 })}{T(pos[k][0], pos[k][1] + 14, !nd.alive ? "down" : `${nd.role === "L" ? "leader" : nd.role === "C" ? "cand." : "follower"} t${nd.term}`, { fill: "#fff", size: 9 })}
          </g>
        ))}
        {T(20, 292, "orange = vote request · blue = vote · green = heartbeat (a leader telling everyone it is alive)", { anchor: "start", size: 10, fill: C.muted })}
      </svg>
    </Shell>
  );
}

// ------------------------------------------------------------------ replication
interface Wr { key: number; at: number }
interface RState { w: Wr[]; t: number; downFor: number; lost: number; stale: number; reads: number; reads_log: { to: string; stale: boolean }[]; msg: string; primaryIsOld: boolean; lagA: number; lagB: number; failedWrites: number }
export function ReplSandbox() {
  const [s, redraw, reset] = useLive<RState>(() => ({ w: [], t: 0, downFor: 0, lost: 0, stale: 0, reads: 0, reads_log: [], msg: "", primaryIsOld: true, lagA: 2, lagB: 6, failedWrites: 0 }));
  const [running, setRunning] = useState(true);
  const [route, setRoute] = useState("followers"), [ack, setAck] = useState("async"), [rate, setRate] = useState(3);
  const lagOf = (to: string) => to === "A" ? s.lagA : s.lagB;
  const isStale = (key: number, to: string) => { if (to === "P") return false; const last = [...s.w].reverse().find(x => x.key === key); return !!last && last.at + lagOf(to) > s.t && last.at !== s.t; };
  useTick(600, () => {
    s.t++;
    if (s.downFor > 0) { s.downFor--; if (s.downFor === 0) s.msg = "A follower was promoted to be the new primary."; }
    for (let i = 0; i < rate; i++) { if (s.downFor > 0) s.failedWrites++; else s.w.push({ key: Math.floor(rnd() * 40), at: s.t }); }
    s.w = s.w.filter(x => s.t - x.at < 30);
    const log: { to: string; stale: boolean }[] = [];
    for (let i = 0; i < 6; i++) {
      if (s.downFor > 0) continue;
      const recent = s.w.slice(-12), key = rnd() < 0.5 && recent.length ? recent[Math.floor(rnd() * recent.length)].key : Math.floor(rnd() * 40);
      const to = route === "primary" ? "P" : route === "followers" ? (i % 2 ? "A" : "B") : "P";
      const st = isStale(key, to);
      s.reads++; if (st) s.stale++;
      log.push({ to, stale: st });
    }
    s.reads_log = log;
    redraw();
  }, running);
  const crash = () => {
    if (s.downFor > 0) return;
    const lagP = Math.min(s.lagA, s.lagB);
    const lostNow = ack === "async" ? s.w.filter(x => x.at > s.t - lagP).length : 0;
    s.lost += lostNow; s.downFor = 4; s.w = s.w.filter(x => ack !== "async" || x.at <= s.t - lagP);
    s.msg = lostNow ? `The primary crashed. ${lostNow} writes that users were told succeeded were never copied: lost for good.` : "The primary crashed. Nothing acknowledged was lost.";
    redraw();
  };
  const readMine = () => {
    const key = 999;
    s.w.push({ key, at: s.t });
    const to = route === "primary" ? "P" : route === "followers" ? "A" : "P";
    s.msg = isStale(key, to) ? "You just saved a change, reloaded, and it is MISSING: that read hit a follower that has not received it yet." : "You just saved a change and reloaded: you see it. That read came from the primary.";
    redraw();
  };
  const pend = (to: string) => s.w.filter(x => x.at + lagOf(to) > s.t).length;
  return (
    <Shell title="Free play: replication" hint="Writes go to the primary and copy out to two followers, one slower than the other. Send reads to followers, crash the primary, and press Save and reload to see a change vanish." running={running} setRunning={setRunning} onReset={reset}
      stats={<span>stale answers <b style={{ color: s.stale ? "var(--danger)" : undefined }}>{s.stale}</b> of {s.reads} reads · writes lost in crashes <b style={{ color: s.lost ? "var(--danger)" : undefined }}>{s.lost}</b> · writes refused during failover {s.failedWrites}{s.msg ? ` · ${s.msg}` : ""}</span>}
      controls={<>
        <Pick label="Where reads go" v={route} set={setRoute} options={[["primary", "Always the primary"], ["followers", "Followers only"]]} />
        <Pick label="A write counts as saved" v={ack} set={setAck} options={[["async", "When the primary has it (async)"], ["semi", "When a follower also has it (semi-sync)"]]} />
        <Slider label="Writes per tick" v={rate} set={setRate} min={0} max={8} />
        <div className="row labrun"><button className="btn pri" onClick={readMine}>Save a change and reload</button><button className="btn" onClick={crash}>Crash the primary</button></div>
      </>}>
      <svg viewBox="0 0 640 300" className="labsvg">
        <rect x={220} y={14} width={200} height={64} rx={10} fill={s.downFor > 0 ? "var(--danger-soft)" : C.soft} stroke={s.downFor > 0 ? C.bad : C.pri} strokeWidth={2} />
        {T(320, 40, s.downFor > 0 ? "PRIMARY DOWN: electing a new one" : "Primary", { bold: true, fill: s.downFor > 0 ? C.bad : C.text })}{T(320, 62, s.downFor > 0 ? "writes are refused" : `${rate} writes per tick`, { size: 11, fill: C.muted })}
        {[["A", 170, s.lagA], ["B", 470, s.lagB]].map(([nm, x, lag]) => (
          <g key={String(nm)}>
            <line x1={320} y1={78} x2={Number(x)} y2={140} stroke={C.line} strokeWidth={2} />
            {s.downFor === 0 && Array.from({ length: Math.min(6, pend(String(nm))) }).map((_, k) => <circle key={k} r={5} fill={C.warn}><animateMotion dur={`${Number(lag) * 0.35 + 0.6}s`} begin={`${k * 0.2}s`} repeatCount="indefinite" path={`M320,78 L${x},140`} /></circle>)}
            <rect x={Number(x) - 80} y={140} width={160} height={58} rx={10} fill={C.soft} stroke={C.line} />{T(Number(x), 164, `Follower ${nm} (${lag} ticks behind)`, { bold: true, size: 11 })}{T(Number(x), 184, `${pend(String(nm))} writes not yet copied`, { size: 11, fill: pend(String(nm)) > 8 ? C.bad : C.muted })}
          </g>
        ))}
        {T(20, 226, "Reads this tick (green fresh, red stale, blue from the primary)", { anchor: "start", size: 11, fill: C.muted })}
        {s.reads_log.map((r, i) => <g key={i}><rect x={20 + i * 40} y={236} width={34} height={26} rx={6} fill={r.stale ? C.bad : r.to === "P" ? C.pri : C.ok} />{T(37 + i * 40, 253, r.to === "P" ? "P" : r.to, { size: 10, fill: "#fff", bold: true })}</g>)}
      </svg>
    </Shell>
  );
}

// ------------------------------------------------------------------ cache
interface CcState { store: Map<number, { exp: number }>; order: number[]; t: number; hits: number; reqs: number; dbHist: number[]; row: { key: number; hit: boolean }[]; overload: number; shift: number; msg: string }
const KEYS = 200;
export function CacheSandbox() {
  const [size, setSize] = useState(24), [ttl, setTtl] = useState(15), [policy, setPolicy] = useState("lru"), [rate, setRate] = useState(12), [jitter, setJitter] = useState(false), [merge, setMerge] = useState(false);
  const [s, redraw, reset] = useLive<CcState>(() => ({ store: new Map(), order: [], t: 0, hits: 0, reqs: 0, dbHist: [], row: [], overload: 0, shift: 0, msg: "" }));
  const [running, setRunning] = useState(true);
  const zipf = () => { const u = rnd(); return Math.min(KEYS - 1, Math.floor(Math.pow(u, 2.6) * KEYS)); };
  const keyOf = (k: number) => (k * (s.shift ? 7 : 1) + (s.shift ? 131 : 0)) % KEYS;
  const evict = () => { while (s.order.length > size) { const v = s.order.shift()!; s.store.delete(v); } };
  useTick(500, () => {
    s.t++;
    for (const [k, v] of [...s.store]) if (ttl > 0 && v.exp <= s.t) { s.store.delete(k); s.order = s.order.filter(x => x !== k); }
    const row: { key: number; hit: boolean }[] = [], miss: number[] = [];
    for (let i = 0; i < rate; i++) {
      const k = keyOf(zipf()); s.reqs++;
      if (s.store.has(k)) { s.hits++; row.push({ key: k, hit: true }); if (policy === "lru") { s.order = s.order.filter(x => x !== k); s.order.push(k); } }
      else { miss.push(k); row.push({ key: k, hit: false }); }
    }
    const db = merge ? new Set(miss).size : miss.length;
    for (const k of new Set(miss)) { s.store.set(k, { exp: ttl > 0 ? s.t + Math.max(1, Math.round(ttl * (jitter ? 0.5 + rnd() : 1))) : 1e9 }); s.order.push(k); evict(); }
    if (db > 8) s.overload++;
    s.dbHist = [...s.dbHist, db].slice(-40); s.row = row.slice(0, 16);
    redraw();
  }, running);
  const warm = () => { const exp = ttl > 0 ? s.t + ttl : 1e9; s.store.clear(); s.order = []; for (let r = 0; r < size; r++) { const k = keyOf(r); s.store.set(k, { exp }); s.order.push(k); } s.msg = ttl > 0 ? `Warmed: all ${size} items load now and will all expire together at tick ${s.t + ttl}.` : ""; redraw(); };
  const flush = () => { s.store.clear(); s.order = []; s.msg = "Cache flushed, like a restart."; redraw(); };
  const lastDb = s.dbHist[s.dbHist.length - 1] ?? 0, mx = Math.max(12, ...s.dbHist);
  return (
    <Shell title="Free play: cache" hint="Press Warm to load the popular items all at once, and watch what happens when they all expire together. Then add TTL jitter or merge duplicate misses. Flush the cache, or press Trend change so different items become popular." running={running} setRunning={setRunning} onReset={reset}
      stats={<span>hit ratio <b>{s.reqs ? Math.round(s.hits / s.reqs * 100) : 0}%</b> · database lookups this tick <b style={{ color: lastDb > 8 ? "var(--danger)" : undefined }}>{lastDb}</b> (limit 8) · ticks the database was overloaded <b>{s.overload}</b>{s.msg ? ` · ${s.msg}` : ""}</span>}
      controls={<>
        <Slider label="Cache size" v={size} set={setSize} min={2} max={40} unit=" slots" />
        <Slider label="Time to live (0 = never)" v={ttl} set={setTtl} min={0} max={40} unit=" ticks" />
        <Pick label="When full, throw out" v={policy} set={setPolicy} options={[["lru", "Least recently used"], ["fifo", "Oldest first"]]} />
        <Slider label="Requests per tick" v={rate} set={setRate} min={4} max={30} />
        <Check label="Spread out expiry (jitter)" v={jitter} set={setJitter} />
        <Check label="Merge duplicate misses" v={merge} set={setMerge} />
        <div className="row labrun"><button className="btn pri" onClick={warm}>Warm the cache</button><button className="btn" onClick={flush}>Flush the cache</button><button className="btn" onClick={() => { s.shift = s.shift ? 0 : 1; s.msg = "A different set of items is now popular."; redraw(); }}>Trend change</button></div>
      </>}>
      <svg viewBox="0 0 640 300" className="labsvg">
        {T(20, 18, `Cache memory (${s.store.size} of ${size} slots used)`, { anchor: "start", bold: true })}
        {Array.from({ length: Math.min(40, size) }).map((_, i) => { const k = s.order[i]; return <g key={i}><rect x={20 + (i % 20) * 30} y={28 + Math.floor(i / 20) * 30} width={26} height={26} rx={5} fill={k === undefined ? C.soft : C.pri} stroke={C.line} opacity={0.9} />{k !== undefined && T(33 + (i % 20) * 30, 45 + Math.floor(i / 20) * 30, k, { size: 9, fill: "#fff" })}</g>; })}
        {T(20, 112, "Requests this tick (green = found in the cache, red = went to the database)", { anchor: "start", size: 11, fill: C.muted })}
        {s.row.map((r, i) => <g key={i}><rect x={20 + i * 37} y={120} width={32} height={26} rx={6} fill={r.hit ? C.ok : C.bad} />{T(36 + i * 37, 137, r.hit ? "HIT" : "MISS", { size: 9, fill: "#fff", bold: true })}</g>)}
        {T(20, 178, "Database lookups per tick (the dashed line is its limit)", { anchor: "start", bold: true })}
        {s.dbHist.map((v, i) => <rect key={i} x={20 + i * 15} y={270 - (v / mx) * 80} width={12} height={(v / mx) * 80} fill={v > 8 ? C.bad : C.ok} />)}
        <line x1={20} y1={270 - (8 / mx) * 80} x2={620} y2={270 - (8 / mx) * 80} stroke={C.text} strokeDasharray="5 4" />
      </svg>
    </Shell>
  );
}

export const SANDBOXES: Record<string, () => JSX.Element> = { lb: LbSandbox, queue: QueueSandbox, serverless: AutoscaleSandbox, ratelimiter: LimiterSandbox, consensus: ConsensusSandbox, repl: ReplSandbox, cache: CacheSandbox };
