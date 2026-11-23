export type GameKind = "builder" | "incident" | "interview" | "lab" | null;

export interface Track { id: string; name: string; blurb: string }
export interface LevelInfo { index: number; name: string; title: string }
export interface LessonMeta { id: string; track: string; title: string; summary: string; game: GameKind; levels: number; projects: boolean }
export interface Catalog { tracks: Track[]; lessons: LessonMeta[] }
export interface Section { h: string; b: string }
export interface Quiz { q: string; o: string[]; a: number; w: string }
export interface Project { id: string; title: string; what: string; done: string }
export interface DeepDive {
  how: { h: string; p: string }[];
  worked: { title: string; steps: string[]; result: string };
  case: { who: string; title: string; text: string; source?: { title: string; url?: string } };
  choose: string[][];
  mistakes: string[];
  reading: { title: string; by: string; kind: string; url?: string }[];
}
export interface Stage {
  id: string; title: string; body?: string; intro?: string; steps?: string[]; takeaway?: string;
  items?: string[]; rows?: string[][]; prompt?: string; checks?: string[];
  questions?: { q: string; options: string[]; answer: number; why: string }[];
}
export interface Explain { what: string; why: string; use: string[]; avoid: string[]; example: string; takeaways: string[] }
export interface LessonDetail {
  explain?: Explain;
  deep?: DeepDive | null;
  levels: LevelInfo[];
  id: string; t: string; title: string; sum: string; sec: Section[]; breaks: string[]; quiz: Quiz;
  projects: boolean; game: GameKind; project_list?: Project[];
  stages?: Stage[]; tutor_prompts?: string[];
  outcomes?: { outcomes: string[]; variations: string[]; prereqs: { id: string; title: string }[] };
}

export interface UserView { username: string; xp: number; rank: string; level: number; streak: number }
export interface LessonProgress { read: boolean; stars: number; score: number | null }
export interface Progress {
  user: UserView;
  lessons: Record<string, LessonProgress>;
  time: Record<string, { targetMin: number | null; spentSec: number }>;
  projects: string[];
  levels: Record<string, Record<string, number>>;
}

/* ---- architecture builder ---- */
export type NodeKind = "client" | "cdn" | "limiter" | "lb" | "app" | "cache" | "queue" | "db";
export interface DesignNode { id: string; type: NodeKind; params?: Record<string, number | boolean> }
export interface DesignEdge { source: string; target: string }
export interface Design { nodes: DesignNode[]; edges: DesignEdge[] }
export interface BuilderLevel {
  level: number; name: string; levels: LevelInfo[];
  title: string; brief: string; budget: number; par: number; ticks: number; available: string[];
  base_servers: number; peak: number; costs: Record<string, number>;
  traffic: { from: number; to: number; read?: number; write?: number; static?: number; job?: number; abuse?: number }[];
}
export interface Frame {
  t: number; good: number; served: number; ok: number; events: string[];
  nodes: { client: { load: number }; app: { util: number; servers: number; alive: number }; cache: { hit: number }; queue: { backlog: number }; db: { read: number; write: number } };
  spent: number;
  servers: { state: "ok" | "warm" | "hot" | "dead" | "idle"; util: number }[];
  flow: { rate: number; static: number; dynamic: number; abuse: number; blocked: number; lost_app: number; lost_db: number };
}
export interface SimResult {
  comps?: Record<string, number>;
  valid: boolean; errors: string[]; warnings: string[]; cost: number; frames: Frame[];
  result: { success: number; spent: number; stars: number };
}

/* ---- incident terminal ---- */
export interface IncidentState { minute: number; max: number; error_rate: number; history: number[]; resolved: boolean; failed: boolean; seen: string[] }
export interface IncidentEvent { k: "inv" | "act"; id: string }
export interface IncidentStepResult { output: string; event: IncidentEvent | null; state: IncidentState; kind: string; label?: string }

/* ---- interview ---- */
export interface InterviewPoint { id: string; point: string; hit: boolean; comment: string }
export interface InterviewResult { score: number; stars: number; points: InterviewPoint[]; feedback: string; graded_by: "ai" | "keywords"; xpGained: number }
