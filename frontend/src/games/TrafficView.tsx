import { useEffect, useMemo, useRef } from "react";
import type { Frame } from "../types";

/**
 * A live picture of the load test. Each moving dot is a small batch of requests.
 * You can watch the load balancer split them across servers, a crashed server turn grey,
 * and requests turn red where the system cannot cope.
 */
interface Props { comps: Record<string, number>; frames: Frame[]; idx: number; playing: boolean }
type Pt = [number, number];
interface Particle { pts: Pt[]; start: number; dur: number; kind: "ok" | "drop" | "abuse" | "block"; stop: number }
interface Box { x: number; y: number; w: number; h: number }

const W = 1000, TRAVEL_MS = 1150;
const clamp = (n: number, a: number, b: number) => Math.max(a, Math.min(b, n));

interface Layout {
  H: number;
  stages: string[];
  box: Record<string, Box>;
  servers: Box[];
  dbBoxes: Box[];
  replicas: Box[];
  queue?: Box;
}

function buildLayout(comps: Record<string, number>, serverCount: number): Layout {
  const nSrv = Math.max(1, serverCount), shardsN = (comps.shard || 0) + 1;
  const H = clamp(Math.max(nSrv * 40, shardsN * 60 + (comps.replica || 0) * 30) + 150 + (comps.queue ? 50 : 0), 300, 470);
  const CY = (H - (comps.queue ? 50 : 0)) / 2;
  const stages = ["users"];
  if (comps.cdn) stages.push("cdn");
  if (comps.limiter) stages.push("limiter");
  if (comps.lb) stages.push("lb");
  stages.push("servers");
  if (comps.cache) stages.push("cache");
  stages.push("db");
  const xs = stages.map((_, i) => 75 + i * (850 / (stages.length - 1)));
  const box: Record<string, Box> = {};
  stages.forEach((s, i) => {
    const w = s === "servers" ? 120 : s === "lb" ? 124 : 96, h = s === "users" || s === "lb" || s === "cache" ? 64 : 50;
    box[s] = { x: xs[i] - w / 2, y: CY - h / 2, w, h };
  });
  const n = nSrv, sh = clamp(300 / n - 8, 22, 54);
  const total = n * (sh + 8);
  const servers: Box[] = Array.from({ length: n }, (_, i) => ({ x: xs[stages.indexOf("servers")] - 60, y: CY - total / 2 + i * (sh + 8), w: 120, h: sh }));
  const dbX = xs[stages.indexOf("db")];
  const shards = shardsN;
  const dh = clamp(150 / shards - 6, 32, 60);
  const dbTotal = shards * (dh + 8) + (comps.replica ? (comps.replica) * 30 + 6 : 0);
  const dbTop = CY - dbTotal / 2;
  const dbBoxes: Box[] = Array.from({ length: shards }, (_, i) => ({ x: dbX - 55, y: dbTop + i * (dh + 8), w: 110, h: dh }));
  const replicas: Box[] = Array.from({ length: comps.replica || 0 }, (_, i) => ({ x: dbX - 55, y: dbTop + shards * (dh + 8) + 6 + i * 30, w: 110, h: 24 }));
  const queue = comps.queue ? { x: xs[stages.indexOf("servers")] - 60, y: H - 56, w: 120, h: 38 } : undefined;
  return { H, stages, box, servers, dbBoxes, replicas, queue };
}

const centre = (b: Box): Pt => [b.x + b.w / 2, b.y + b.h / 2];

export function TrafficView({ comps, frames, idx, playing }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const particles = useRef<Particle[]>([]);
  const lastSpawn = useRef(-1);
  const rr = useRef(0);
  const frame: Frame | undefined = frames[Math.max(0, Math.min(idx, frames.length - 1))];
  const serverCount = frame?.servers.length ?? comps.server ?? 1;
  const layout = useMemo(() => buildLayout(comps, serverCount), [comps, serverCount]);
  const live = useRef({ layout, frame, comps, frames, idx });
  live.current = { layout, frame, comps, frames, idx };

  /* Create the dots for one second of traffic. */
  useEffect(() => {
    if (!frame || lastSpawn.current === idx) return;
    lastSpawn.current = idx;
    const L = layout, now = performance.now(), f = frame.flow;
    const users = centre(L.box.users);
    const front: Pt[] = [users];
    for (const s of ["cdn", "limiter", "lb"]) if (L.box[s]) front.push(centre(L.box[s]));
    const alive: number[] = [];
    frame.servers.forEach((s, i) => { if (comps.lb ? s.state !== "dead" : i === 0) alive.push(i); });
    const dynFrac = f.rate > 0 ? Math.min(1, f.dynamic / f.rate) : 1;
    const lostAppFrac = f.dynamic > 0 ? f.lost_app / f.dynamic : 0;
    const afterApp = f.dynamic - f.lost_app;
    const lostDbFrac = afterApp > 0 ? f.lost_db / afterApp : 0;
    const add = (pts: Pt[], kind: Particle["kind"], stop = 1) => particles.current.push({ pts, start: now + Math.random() * 380, dur: TRAVEL_MS, kind, stop });
    const serverPath = (i: number): Pt[] => [...front, centre(L.servers[Math.min(i, L.servers.length - 1)])];
    const backPath = (): Pt[] => {
      const out: Pt[] = [];
      if (L.box.cache) out.push(centre(L.box.cache));
      out.push(centre(L.dbBoxes[Math.floor(Math.random() * L.dbBoxes.length)]));
      return out;
    };

    const legit = clamp(Math.round(f.rate / 7), 1, 16);
    for (let k = 0; k < legit; k++) {
      if (comps.cdn && Math.random() > dynFrac) { add([users, centre(L.box.cdn)], "ok"); continue; }   // images and scripts stop at the CDN
      let pick = -1;
      if (comps.lb) { if (alive.length) pick = alive[rr.current++ % alive.length]; }                    // round robin across healthy servers
      else pick = 0;                                                                                    // no load balancer: everything hits server 1
      if (pick < 0) { add([...front], "drop", 0.92); continue; }
      const dead = frame.servers[pick]?.state === "dead";
      if (dead || Math.random() < lostAppFrac) { add(serverPath(pick), "drop", 0.9); continue; }
      const hit = comps.cache && Math.random() < frame.nodes.cache.hit;
      if (hit) { add([...serverPath(pick), centre(L.box.cache)], "ok"); continue; }
      const path = [...serverPath(pick), ...backPath()];
      add(path, Math.random() < lostDbFrac ? "drop" : "ok", Math.random() < lostDbFrac ? 0.95 : 1);
    }
    const abusive = clamp(Math.round(f.abuse / 14), 0, 8);
    for (let k = 0; k < abusive; k++) {
      if (comps.limiter && Math.random() < 0.95) add([users, centre(L.box.limiter)], "block", 1);
      else if (alive.length) add(serverPath(alive[rr.current++ % alive.length]), "abuse", 0.9);
    }
  }, [idx, frame, layout, comps]);

  /* Draw, many times a second. */
  useEffect(() => {
    let raf = 0;
    const draw = () => {
      raf = requestAnimationFrame(draw);
      const el = canvas.current, host = wrap.current;
      if (!el || !host) return;
      const { layout: L, frame: fr, comps: cp, frames: all } = live.current;
      const dpr = window.devicePixelRatio || 1, cw = host.clientWidth, scale = cw / W;
      if (cw === 0) return;
      const H = L.H;
      if (el.width !== Math.round(cw * dpr) || el.height !== Math.round(H * scale * dpr)) {
        el.width = Math.round(cw * dpr); el.height = Math.round(H * scale * dpr);
        el.style.width = cw + "px"; el.style.height = H * scale + "px";
      }
      const ctx = el.getContext("2d");
      if (!ctx) return;
      const css = getComputedStyle(document.documentElement);
      const v = (n: string) => css.getPropertyValue(n).trim();
      const C = { text: v("--text"), muted: v("--muted"), line: v("--line"), surface: v("--surface"), soft: v("--bg-soft"),
        primary: v("--primary"), ok: v("--success"), warn: v("--warning"), bad: v("--danger"), badSoft: v("--danger-soft") };
      ctx.setTransform(dpr * scale, 0, 0, dpr * scale, 0, 0);
      ctx.clearRect(0, 0, W, H);
      ctx.textAlign = "center"; ctx.textBaseline = "middle";

      const link = (a: Pt, b: Pt) => { ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.strokeStyle = C.line; ctx.lineWidth = 2; ctx.stroke(); };
      const rbox = (b: Box, stroke: string, fill: string, dashed = false) => {
        ctx.beginPath(); ctx.roundRect(b.x, b.y, b.w, b.h, 10); ctx.fillStyle = fill; ctx.fill();
        ctx.setLineDash(dashed ? [5, 4] : []); ctx.strokeStyle = stroke; ctx.lineWidth = 2.5; ctx.stroke(); ctx.setLineDash([]);
      };
      const label = (t: string, b: Box, sub?: string, colour = C.text) => {
        ctx.fillStyle = colour; ctx.font = "600 13px Inter, system-ui, sans-serif"; ctx.fillText(t, b.x + b.w / 2, b.y + b.h / 2 - (sub ? 8 : 0));
        if (sub) { ctx.fillStyle = C.muted; ctx.font = "500 11px Inter, system-ui, sans-serif"; ctx.fillText(sub, b.x + b.w / 2, b.y + b.h / 2 + 9); }
      };

      // links between the stages
      const st = L.stages;
      for (let i = 0; i < st.length - 1; i++) {
        const a = st[i], b = st[i + 1];
        if (a === "servers") continue;
        if (b === "servers") L.servers.forEach(s => link(centre(L.box[a]), centre(s)));
        else if (b === "db") L.dbBoxes.forEach(d => link(centre(L.box[a]), centre(d)));
        else link(centre(L.box[a]), centre(L.box[b]));
      }
      const next = st[st.indexOf("servers") + 1];
      L.servers.forEach(s => (next === "db" ? L.dbBoxes : [L.box[next]]).forEach(t => link(centre(s), centre(t))));
      if (L.queue) { link(centre(L.servers[L.servers.length - 1]), centre(L.queue)); L.dbBoxes.forEach(d => link(centre(L.queue!), centre(d))); }

      const rate = fr ? Math.round(fr.flow.rate) : 0;
      rbox(L.box.users, C.primary, C.surface); label("Users", L.box.users, fr ? `${rate} req/s` : "");
      if (L.box.cdn) { rbox(L.box.cdn, C.ok, C.surface); label("CDN", L.box.cdn, fr ? `${Math.round(fr.flow.static)} static` : "edge cache"); }
      if (L.box.limiter) { rbox(L.box.limiter, C.ok, C.surface); label("Rate limiter", L.box.limiter, fr && fr.flow.blocked > 0 ? `${Math.round(fr.flow.blocked)} blocked` : "watching"); }
      if (L.box.lb) { rbox(L.box.lb, C.ok, C.surface); label("Load balancer", L.box.lb, `${fr ? fr.servers.filter(s => s.state !== "dead").length : cp.server} servers`); }

      L.servers.forEach((b, i) => {
        const s = fr?.servers[i];
        const state = s?.state ?? "ok";
        const border = state === "dead" ? C.muted : state === "hot" ? C.bad : state === "warm" ? C.warn : state === "idle" ? C.line : C.ok;
        rbox(b, border, state === "dead" ? C.soft : state === "hot" ? C.badSoft : C.surface, state === "dead" || state === "idle");
        const sub = state === "dead" ? "crashed" : state === "idle" ? (cp.lb ? "idle" : "idle: no load balancer") : `${Math.round((s?.util ?? 0) * 100)}% busy`;
        label(`Server ${i + 1}`, b, b.h > 30 ? sub : undefined, state === "dead" ? C.muted : C.text);
        if (state === "dead") { ctx.strokeStyle = C.bad; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(b.x + 14, b.y + 7); ctx.lineTo(b.x + 30, b.y + b.h - 7); ctx.moveTo(b.x + 30, b.y + 7); ctx.lineTo(b.x + 14, b.y + b.h - 7); ctx.stroke(); }
        else if (s && s.state !== "idle") { // little load bar under the label
          ctx.fillStyle = C.soft; ctx.fillRect(b.x + 10, b.y + b.h - 8, b.w - 20, 4);
          ctx.fillStyle = border; ctx.fillRect(b.x + 10, b.y + b.h - 8, (b.w - 20) * Math.min(1, s.util), 4);
        }
      });
      if (L.box.cache) { rbox(L.box.cache, C.ok, C.surface); label(`Cache L${cp.cache}`, L.box.cache, fr ? `${Math.round(fr.nodes.cache.hit * 100)}% hits` : "ready"); }
      const dbUtil = fr ? Math.max(fr.nodes.db.read, fr.nodes.db.write) : 0;
      const dbBorder = dbUtil > 1 ? C.bad : dbUtil > 0.7 ? C.warn : C.ok;
      L.dbBoxes.forEach((b, i) => { rbox(b, dbBorder, dbUtil > 1 ? C.badSoft : C.surface); label(L.dbBoxes.length > 1 ? `Shard ${i + 1}` : "Database", b, fr ? `${Math.round(dbUtil * 100)}% busy` : undefined); });
      L.replicas.forEach((b, i) => { rbox(b, C.ok, C.surface, true); label(`Replica ${i + 1}`, b); });
      if (L.queue) {
        rbox(L.queue, C.ok, C.surface); label("Queue", L.queue, fr ? `${Math.round(fr.nodes.queue.backlog)} waiting` : "workers ready");
        if (fr) { ctx.fillStyle = C.soft; ctx.fillRect(L.queue.x + 10, L.queue.y + L.queue.h - 7, L.queue.w - 20, 4); ctx.fillStyle = C.primary; ctx.fillRect(L.queue.x + 10, L.queue.y + L.queue.h - 7, (L.queue.w - 20) * Math.min(1, fr.nodes.queue.backlog / 200), 4); }
      }

      // the moving dots
      const now = performance.now();
      particles.current = particles.current.filter(p => now - p.start < p.dur + 450);
      for (const p of particles.current) {
        const t = (now - p.start) / p.dur;
        if (t < 0) continue;
        const lens: number[] = []; let total = 0;
        for (let i = 1; i < p.pts.length; i++) { const l = Math.hypot(p.pts[i][0] - p.pts[i - 1][0], p.pts[i][1] - p.pts[i - 1][1]); lens.push(l); total += l; }
        const reach = Math.min(Math.min(1, t) * p.stop, p.stop) * total;
        let d = reach, i = 0;
        while (i < lens.length - 1 && d > lens[i]) { d -= lens[i]; i++; }
        const a = p.pts[i], b = p.pts[i + 1] ?? p.pts[i], f = lens[i] > 0 ? d / lens[i] : 0;
        const x = a[0] + (b[0] - a[0]) * f, y = a[1] + (b[1] - a[1]) * f;
        const colour = p.kind === "ok" ? C.primary : p.kind === "drop" ? C.bad : C.warn;
        if (t > 1 && (p.kind === "drop" || p.kind === "block")) { // lost here: show a short red cross
          const fade = 1 - (t - 1) / 0.4; ctx.globalAlpha = Math.max(0, fade); ctx.strokeStyle = p.kind === "drop" ? C.bad : C.warn; ctx.lineWidth = 3;
          ctx.beginPath(); ctx.moveTo(x - 6, y - 6); ctx.lineTo(x + 6, y + 6); ctx.moveTo(x + 6, y - 6); ctx.lineTo(x - 6, y + 6); ctx.stroke(); ctx.globalAlpha = 1;
        } else if (t <= 1) {
          ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2); ctx.fillStyle = colour; ctx.fill(); ctx.lineWidth = 1.5; ctx.strokeStyle = C.surface; ctx.stroke();
        }
      }

      // caption and legend
      ctx.textAlign = "left"; ctx.fillStyle = C.muted; ctx.font = "600 12px Inter, system-ui, sans-serif";
      ctx.fillText(fr ? `Second ${fr.t + 1} of ${all.length}` : "", 14, 20);
      const legend: [string, string][] = [[C.primary, "served"], [C.bad, "dropped"], [C.warn, "abuse"]];
      legend.forEach(([c, t], i) => { const lx = W - 250 + i * 84; ctx.beginPath(); ctx.arc(lx, 20, 5, 0, Math.PI * 2); ctx.fillStyle = c; ctx.fill(); ctx.fillStyle = C.muted; ctx.fillText(t, lx + 10, 20); });
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, []);

  useEffect(() => { if (idx <= 0) { particles.current = []; lastSpawn.current = -1; rr.current = 0; } }, [idx, frames]);

  const f = frame;
  const lost = f ? Math.round(f.flow.lost_app + f.flow.lost_db) : 0;
  const parts: string[] = [];
  if (f) {
    parts.push(`Second ${f.t + 1}: ${Math.round(f.flow.rate)} requests a second arrive and ${Math.round(f.served)} are served${lost > 0 ? `, ${lost} dropped` : ""}`);
    if (f.servers.some(s => s.state === "dead")) parts.push(comps.lb ? "A server has crashed, so the load balancer sends traffic to the others" : "A server has crashed and nothing can route around it");
    if (!comps.lb && comps.server > 1) parts.push("Without a load balancer only server 1 gets traffic");
  }
  const caption = f ? parts.join(". ") + "." : "Press the load test to see traffic.";
  return (
    <div className="traffic" ref={wrap}>
      <canvas ref={canvas} role="img" aria-label="Live traffic through your system. Blue dots are served requests, red are dropped." />
      <p className="traffic-cap" aria-live="polite">{caption}{playing ? "" : ""}</p>
    </div>
  );
}
