import {
  Background, Controls, Handle, Position, ReactFlow, ReactFlowProvider, addEdge, useEdgesState, useNodesState, useReactFlow,
  type Connection, type Edge, type Node, type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import { Takeaways } from "../components/Explain";
import { Markdown } from "../components/Markdown";
import { Stars } from "../components/Stars";
import { TrafficView } from "./TrafficView";
import type { BuilderLevel, Design, Frame, NodeKind, SimResult } from "../types";

type Params = Record<string, number | boolean>;
type NodeData = { kind: NodeKind; params: Params; frame?: Frame };
type CompNode = Node<NodeData, "comp">;

const LABEL: Record<NodeKind, string> = {
  client: "Users", cdn: "CDN", limiter: "Rate limiter", lb: "Load balancer", app: "App servers", cache: "Cache", queue: "Queue", db: "Database",
};
const BLURB: Record<NodeKind, string> = {
  client: "Where all traffic comes from.",
  cdn: "Serves images and scripts from the edge so they never reach your servers.",
  limiter: "Drops abusive traffic before it reaches your servers.",
  lb: "Spreads requests across your app servers and routes around a crashed one.",
  app: "Runs your code. Each server handles about 40 requests a second.",
  cache: "Answers repeat reads from memory so the database does less.",
  queue: "Takes slow jobs and writes off the request path and works through them later.",
  db: "The source of truth. Has limited read and write capacity.",
};
// Which connections make sense. The server checks the same rules.
const ALLOWED: Record<NodeKind, NodeKind[]> = {
  client: ["cdn", "limiter", "lb", "app"], cdn: ["limiter", "lb", "app"], limiter: ["lb", "app"], lb: ["app"],
  app: ["cache", "db", "queue"], cache: ["db"], queue: ["db"], db: [],
};
const PALETTE: NodeKind[] = ["cdn", "limiter", "lb", "cache", "queue"];
const EVENT_TEXT: Record<string, string> = {
  crash: "A server has crashed!", hotkey: "A popular cache key just expired!", depslow: "A dependency has slowed down!", abuse: "A flood of abusive traffic!",
};

function statusOf(kind: NodeKind, f?: Frame): "good" | "warn" | "hot" | "" {
  if (!f) return "";
  const u = kind === "app" ? f.nodes.app.util : kind === "db" ? Math.max(f.nodes.db.read, f.nodes.db.write) : 0;
  if (!u) return "good";
  return u > 1 ? "hot" : u > 0.7 ? "warn" : "good";
}

function CompNodeView({ data, selected }: NodeProps<CompNode>) {
  const { kind, params, frame } = data;
  let line = "";
  if (kind === "client") line = frame ? `${Math.round(frame.good)} req/s` : "";
  if (kind === "app") line = frame ? `${params.instances ?? 1} server(s), ${Math.round(frame.nodes.app.util * 100)}% busy` : `${params.instances ?? 1} server(s)`;
  if (kind === "cache") line = `Level ${params.level ?? 1}` + (frame ? `, ${Math.round(frame.nodes.cache.hit * 100)}% hits` : "");
  if (kind === "db") line = `${params.replicas ?? 0} replica(s), ${params.shards ?? 1} shard(s)` + (frame ? `, ${Math.round(Math.max(frame.nodes.db.read, frame.nodes.db.write) * 100)}% busy` : "");
  if (kind === "queue" && frame) line = `${Math.round(frame.nodes.queue.backlog)} waiting`;
  return (
    <div className={`bnode ${statusOf(kind, frame)}${selected ? " sel" : ""}`}>
      {kind !== "client" && <Handle type="target" position={Position.Left} />}
      <b>{LABEL[kind]}</b>
      {line && <small>{line}</small>}
      {kind !== "client" && kind !== "app" && kind !== "db" && kind !== "cache" && <small className="muted">{(params.note as unknown as string) ?? ""}</small>}
      {kind !== "db" && <Handle type="source" position={Position.Right} />}
    </div>
  );
}
const nodeTypes = { comp: CompNodeView };

const base = (id: NodeKind, x: number, y: number, params: Params = {}): CompNode => ({
  id, type: "comp", position: { x, y }, data: { kind: id, params }, deletable: id !== "client" && id !== "app" && id !== "db",
});

function toDesign(nodes: CompNode[], edges: Edge[]): Design {
  return {
    nodes: nodes.map(n => ({ id: n.id, type: n.data.kind, params: n.data.params })),
    edges: edges.map(e => ({ source: e.source, target: e.target })),
  };
}

function estimate(nodes: CompNode[], level: BuilderLevel): number {
  const c = level.costs;
  let cost = 0;
  for (const n of nodes) {
    const p = n.data.params;
    switch (n.data.kind) {
      case "app": cost += (Number(p.instances ?? level.base_servers) - level.base_servers) * c.server + (p.breaker ? c.breaker : 0) + (p.autoscale ? c.autoscale : 0); break;
      case "lb": cost += c.lb; break;
      case "cdn": cost += c.cdn; break;
      case "limiter": cost += c.limiter; break;
      case "queue": cost += c.queue; break;
      case "cache": cost += Number(p.level ?? 1) * c.cache + (p.coalesce ? c.coalesce : 0); break;
      case "db": cost += Number(p.replicas ?? 0) * c.replica + (Number(p.shards ?? 1) - 1) * c.shard; break;
      default: break;
    }
  }
  return cost;
}

function BuilderInner({ lessonId, level: lv, takeaways }: { lessonId: string; level: number; takeaways?: string[] }) {
  const q = `?level=${lv}`;
  const { loggedIn, aiEnabled, refresh } = useAuth();
  const [level, setLevel] = useState<BuilderLevel | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<CompNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [sim, setSim] = useState<SimResult | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [idx, setIdx] = useState(-1);
  const [playing, setPlaying] = useState(false);
  const [saved, setSaved] = useState<{ xp: number } | null>(null);
  const [review, setReview] = useState("");
  const [view, setView] = useState<"design" | "traffic">("design");
  const [busy, setBusy] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const flow = useReactFlow();
  const flowRef = useRef(flow);
  flowRef.current = flow;
  const home = () => setTimeout(() => flowRef.current.setViewport({ x: 24, y: 70, zoom: 0.78 }), 60);

  useEffect(() => {
    let live = true;
    api<BuilderLevel>("GET", `/api/games/${lessonId}/builder${q}`).then(l => {
      if (!live) return;
      setLevel(l);
      setNodes([base("client", 0, 120), base("app", 270, 120, { instances: l.base_servers }), base("db", 540, 120, { replicas: 0, shards: 1 })]);
      setEdges([]);
      home();
    });
    return () => { live = false; };
  }, [lessonId, q, setNodes, setEdges]);

  const frame = playing || (sim && idx >= 0) ? sim?.frames[Math.max(0, idx)] : undefined;
  useEffect(() => {
    setNodes(ns => ns.map(n => ({ ...n, data: { ...n.data, frame } })));
  }, [frame, setNodes]);

  useEffect(() => {
    if (!playing || !sim) return;
    const t = setInterval(() => {
      setIdx(i => {
        if (i + 1 >= sim.frames.length) { setPlaying(false); return i; }
        return i + 1;
      });
    }, 320);
    return () => clearInterval(t);
  }, [playing, sim]);

  const finished = !!sim && !playing && idx >= (sim?.frames.length ?? 0) - 1 && idx >= 0;
  const design = useMemo(() => toDesign(nodes, edges), [nodes, edges]);
  const cost = level ? estimate(nodes, level) : 0;

  const isValid = useCallback((c: Connection | Edge) => {
    const s = nodes.find(n => n.id === c.source), t = nodes.find(n => n.id === c.target);
    return !!s && !!t && s.id !== t.id && ALLOWED[s.data.kind].includes(t.data.kind);
  }, [nodes]);
  const onConnect = useCallback((c: Connection) => setEdges(es => addEdge({ ...c, animated: false }, es)), [setEdges]);

  const addNode = (kind: NodeKind, pos?: { x: number; y: number }) => {
    if (nodes.some(n => n.id === kind)) { setErrors([`You already have a ${LABEL[kind]}. Select it to change its settings.`]); return; }
    const params: Params = kind === "cache" ? { level: 1, coalesce: false } : {};
    const fallback = { x: 170 + (nodes.length % 3) * 20, y: -40 + (nodes.length % 4) * 70 };
    setNodes(ns => [...ns, base(kind, pos?.x ?? fallback.x, pos?.y ?? fallback.y, params)]);
    setErrors([]);
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    const kind = e.dataTransfer.getData("application/blueprint") as NodeKind;
    if (kind) addNode(kind, flow.screenToFlowPosition({ x: e.clientX, y: e.clientY }));
  };
  const setParams = (id: string, patch: Params) => setNodes(ns => ns.map(n => n.id === id ? { ...n, data: { ...n.data, params: { ...n.data.params, ...patch } } } : n));

  const reset = () => {
    if (!level) return;
    setNodes([base("client", 0, 120), base("app", 270, 120, { instances: level.base_servers }), base("db", 540, 120, { replicas: 0, shards: 1 })]);
    home();
    setEdges([]); setSim(null); setIdx(-1); setPlaying(false); setSaved(null); setErrors([]); setReview(""); setView("design");
  };

  const run = async () => {
    if (playing || busy) return;
    setBusy(true); setErrors([]); setSaved(null); setReview("");
    try {
      const r = await api<SimResult>("POST", `/api/games/${lessonId}/builder/simulate${q}`, design);
      if (!r.valid) { setSim(null); setIdx(-1); setErrors(r.errors); return; }
      setErrors(r.warnings.map(w => "Note: " + w));
      setSim(r); setIdx(0); setPlaying(true); setView("traffic");
      setEdges(es => es.map(e => ({ ...e, animated: true })));
      if (loggedIn) {
        const s = await api<{ xpGained: number }>("POST", `/api/games/${lessonId}/builder/submit${q}`, design);
        setSaved({ xp: s.xpGained });
        void refresh();
      }
    } catch (e) { setErrors([e instanceof ApiError ? e.message : "Could not run the test."]); }
    finally { setBusy(false); }
  };
  useEffect(() => { if (!playing) setEdges(es => es.map(e => ({ ...e, animated: false }))); }, [playing, setEdges]);

  const askReview = async () => {
    setBusy(true);
    try { setReview((await api<{ review: string }>("POST", `/api/games/${lessonId}/builder/review${q}`, design)).review); }
    catch (e) { setReview(e instanceof ApiError ? e.message : "Could not get a review."); }
    finally { setBusy(false); }
  };

  if (!level) return <p className="muted">Loading the level...</p>;
  const selected = nodes.find(n => n.id === selectedId);
  const avail = new Set(level.available);
  const over = cost > level.budget;
  const frames = sim?.frames.slice(0, Math.max(0, idx) + 1) ?? [];
  const peak = Math.max(60, level.peak * 1.15);
  const bw = 560 / level.ticks;
  const live = frame?.events.map(e => EVENT_TEXT[e]).filter(Boolean) ?? [];

  return (
    <div className="gm">
      <div className="gm-head">
        <div><h2>{level.title}</h2><p>{level.brief}</p></div>
        <div className="chips">
          <span className={"chip coin" + (over ? " over" : "")}>Cost {cost} / {level.budget} coins</span>
          <span className="chip">Efficient: {level.par} or less</span>
        </div>
      </div>

      <div className="banner info">
        Build your system: drag components onto the canvas, then draw arrows between them. A simple path is
        <b> Users → App servers → Database</b>. Select a node to change its settings, then run the load test. Expect surprises mid-test.
      </div>

      <div className="tabs small" role="tablist" aria-label="View">
        <button role="tab" aria-selected={view === "design"} onClick={() => setView("design")}>1. Design</button>
        <button role="tab" aria-selected={view === "traffic"} disabled={!sim} onClick={() => setView("traffic")}>2. Watch the traffic</button>
      </div>
      {view === "traffic" && sim?.comps && <TrafficView comps={sim.comps} frames={sim.frames} idx={Math.max(0, idx)} playing={playing} />}

      <div className="builder" style={view === "design" ? undefined : { display: "none" }}>
        <div className="palette" aria-label="Components">
          <div className="vl">Components</div>
          {PALETTE.filter(k => avail.has(k)).map(k => (
            <button key={k} className="pitem" draggable onDragStart={e => e.dataTransfer.setData("application/blueprint", k)} onClick={() => addNode(k)} title={BLURB[k]}>
              <b>{LABEL[k]}</b><small>{BLURB[k]}</small>
            </button>
          ))}
          <small className="muted">Drag onto the canvas, or click to add.</small>
        </div>

        <div className="canvas" ref={wrap} onDrop={onDrop} onDragOver={e => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; }}>
          <ReactFlow
            nodes={nodes} edges={edges} nodeTypes={nodeTypes}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect} isValidConnection={isValid}
            onSelectionChange={({ nodes: sel }) => setSelectedId(sel[0]?.id ?? null)}
            defaultViewport={{ x: 24, y: 70, zoom: 0.78 }} minZoom={0.3} zoomOnScroll={false} preventScrolling={false} deleteKeyCode={["Backspace", "Delete"]}
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={20} /><Controls showInteractive={false} />
          </ReactFlow>
        </div>

        <div className="inspector">
          <div className="vl">Settings</div>
          {!selected && <p className="muted">Select a component to see what it does and change its settings.</p>}
          {selected && (
            <>
              <h4>{LABEL[selected.data.kind]}</h4>
              <p className="muted">{BLURB[selected.data.kind]}</p>
              {selected.data.kind === "app" && (
                <>
                  {avail.has("server") && (
                    <label className="field">Servers: <b>{String(selected.data.params.instances)}</b>
                      <input type="range" min={level.base_servers} max={8} value={Number(selected.data.params.instances)} onChange={e => setParams("app", { instances: Number(e.target.value) })} />
                      <small className="muted">{level.costs.server} coins for each extra server</small>
                    </label>
                  )}
                  {avail.has("breaker") && <label className="chk"><input type="checkbox" checked={!!selected.data.params.breaker} onChange={e => setParams("app", { breaker: e.target.checked })} /> Circuit breaker ({level.costs.breaker})</label>}
                  {avail.has("autoscale") && <label className="chk"><input type="checkbox" checked={!!selected.data.params.autoscale} onChange={e => setParams("app", { autoscale: e.target.checked })} /> Auto scaling ({level.costs.autoscale})</label>}
                </>
              )}
              {selected.data.kind === "cache" && (
                <>
                  <label className="field">Size: level <b>{String(selected.data.params.level)}</b>
                    <input type="range" min={1} max={3} value={Number(selected.data.params.level)} onChange={e => setParams("cache", { level: Number(e.target.value) })} />
                    <small className="muted">{level.costs.cache} coins per level</small>
                  </label>
                  {avail.has("coalesce") && <label className="chk"><input type="checkbox" checked={!!selected.data.params.coalesce} onChange={e => setParams("cache", { coalesce: e.target.checked })} /> Request coalescing ({level.costs.coalesce})</label>}
                </>
              )}
              {selected.data.kind === "db" && (
                <>
                  {avail.has("replica") && (
                    <label className="field">Read replicas: <b>{String(selected.data.params.replicas)}</b>
                      <input type="range" min={0} max={3} value={Number(selected.data.params.replicas)} onChange={e => setParams("db", { replicas: Number(e.target.value) })} />
                      <small className="muted">{level.costs.replica} coins each</small>
                    </label>
                  )}
                  {avail.has("shard") && (
                    <label className="field">Shards: <b>{String(selected.data.params.shards)}</b>
                      <input type="range" min={1} max={4} value={Number(selected.data.params.shards)} onChange={e => setParams("db", { shards: Number(e.target.value) })} />
                      <small className="muted">{level.costs.shard} coins per extra shard</small>
                    </label>
                  )}
                  {!avail.has("replica") && !avail.has("shard") && <small className="muted">No database upgrades in this level.</small>}
                </>
              )}
              {selected.data.kind !== "client" && selected.data.kind !== "app" && selected.data.kind !== "db" && <small className="muted">Press Delete to remove it.</small>}
            </>
          )}
        </div>
      </div>

      {errors.length > 0 && <div className="banner warn" role="alert">{errors.map((e, i) => <div key={i}>{e}</div>)}</div>}
      {live.length > 0 && <div className="banner bad">{live.join(" ")}</div>}

      <div className="row2">
        <button className="btn pri" onClick={run} disabled={playing || busy || over}>{sim ? "Run the load test again" : "Run the load test"}</button>
        <button className="btn" onClick={reset} disabled={playing}>Start over</button>
        {edges.length === 0 && <button className="btn" onClick={() => setEdges([{ id: "e-client-app", source: "client", target: "app" }, { id: "e-app-db", source: "app", target: "db" }])} disabled={playing}>Connect Users → App → Database</button>}
        {over && <span className="err">Over budget. Remove something or lower a setting.</span>}
      </div>

      {sim && (
        <svg className="chart" viewBox="0 0 600 150" role="img" aria-label="Requests over time. Blue is served, red is dropped.">
          <line x1="30" y1="120" x2="600" y2="120" stroke="var(--line)" />
          {frames.map((f, i) => {
            const x = 30 + i * bw, hg = Math.max(1, f.good / peak * 100), hs = Math.min(hg, f.served / peak * 100);
            return <g key={i}>
              <rect x={x + 1} y={120 - hg} width={Math.max(1, bw - 2)} height={hg} fill="var(--danger)" opacity={0.8} />
              <rect x={x + 1} y={120 - hs} width={Math.max(1, bw - 2)} height={hs} fill="var(--primary)" />
              {f.events.length > 0 && <rect x={x + 1} y={124} width={Math.max(1, bw - 2)} height={6} fill="var(--warning)" />}
            </g>;
          })}
          <text x="30" y="144">Each bar is one second. Blue: served. Red: dropped. Amber: something went wrong.</text>
        </svg>
      )}

      {finished && sim && (
        <div className="card result">
          <h2>{sim.result.stars ? "Load test passed" : "Load test failed"}</h2>
          <Stars n={sim.result.stars} big />
          <p>{Math.round(sim.result.success * 100)}% of requests succeeded. You spent {sim.result.spent} of {level.budget} coins. Efficient target: {level.par} or less.</p>
          {saved ? <p><span className={"pill " + (saved.xp ? "ok" : "")}>{saved.xp ? `+${saved.xp} XP` : "No new XP. You already earned these stars."}</span></p>
            : <p className="muted">{loggedIn ? "Saving..." : "Log in to save your stars and XP."}</p>}
          <p className="muted">{sim.result.stars === 3 ? "Excellent: almost nothing failed and the design is efficient."
            : sim.result.stars ? "It held up. A tighter, cheaper design earns 3 stars." : "Too many requests failed. Look at where the bars turn red and which component was busiest."}</p>
          <div className="row2">
            <button className="btn" onClick={() => { setView("design"); }}>Edit my design</button>
            {aiEnabled && loggedIn && <button className="btn" onClick={askReview} disabled={busy}>Ask an AI engineer to review it</button>}
          </div>
          {review && <div className="review"><Markdown text={review} /></div>}
          <Takeaways items={takeaways} />
        </div>
      )}
    </div>
  );
}

export function Builder({ lessonId, level, takeaways }: { lessonId: string; level: number; takeaways?: string[] }) {
  return <ReactFlowProvider><BuilderInner key={`${lessonId}-${level}`} lessonId={lessonId} level={level} takeaways={takeaways} /></ReactFlowProvider>;
}
