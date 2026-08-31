import type { FeatureCollection } from "geojson";

export type Province = {
  id: string;
  name: string;
  kind: string;
  capital: boolean;
  nation: string;
  nation_name: string;
  port: boolean;
  controller: string;
  controller_name: string;
  fort: number;
  threat: number;
  threat_band: string;
  threat_band_name: string;
  relation: number | null;
  army: number;
  army_owner: string;
  economy: number;
  population: number;
  neighbors: string[];
};

export type MapGeojson = FeatureCollection & {
  camera: { longitude: number; latitude: number; zoom: number };
  attribution: string;
};

export type Ui = {
  pause: string;
  resume: string;
  ask_advisor: string;
  ask_placeholder: string;
  configure_api: string;
  advisor_title: string;
  paper_title: string;
  stat_army: string;
  stat_economy: string;
  stat_money: string;
  stat_population: string;
  stat_stability: string;
  stat_relation: string;
  menu_continue: string;
  menu_save: string;
  menu_load: string;
  menu_restart: string;
  menu_quit: string;
  menu_delete: string;
  saves_empty: string;
  ended_title: string;
  place_fort: string;
  place_ours: string;
  place_lost: string;
  place_unowned: string;
  capital_mark: string;
  stat_threat: string;
  map_political: string;
  map_threat: string;
  api_save: string;
  setup_title: string;
  setup_country: string;
  setup_leader: string;
  setup_difficulty: string;
  setup_points: string;
  setup_points_left: string;
  setup_start: string;
  setup_load: string;
  category_order: string[];
  err_prefix: string;
  colonize: string;
  demobilize: string;
  recruit: string;
  march: string;
};

export type DomesticAction = {
  id: string;
  name: string;
  title: string;
  category: string;
  cost_money: number;
  needs_province: boolean;
  needs_kind: string;
  needs_port: boolean;
};

export type GameView = {
  turn: number;
  day: number;
  paused: boolean;
  date: string;
  ended: boolean;
  ending: string;
  save_name: string;
  difficulty: string;
  player: {
    id: string;
    name: string;
    short_name: string;
    leader: string;
    army: number;
    economy: number;
    money: number;
    population: number;
    stability: number;
  };
  relations: Record<string, { name: string; value: number }>;
  map: {
    provinces: Province[];
  };
  news: { turn: number; event_id: string; title: string; text: string }[];
  pending: { event_id: string; title: string; text: string; options: { id: string; text: string }[] }[];
  last_advisor: string;
  domestic: DomesticAction[];
  cooldowns: Record<string, number>;
};

export type FillPair = { fill: string; hover: string };

export type ThreatBand = {
  id: string;
  min: number;
  max: number;
  name: string;
  fill: string;
  hover: string;
};

export type MapStyle = {
  unowned_nation: string;
  hover_lock_ms: number;
  seam: { zooms: number[]; widths: number[] };
  unowned: FillPair;
  lost: FillPair;
  threat: { min: number; max: number; default: number; bands: ThreatBand[] };
};

export type Difficulty = { id: string; name: string };

export type SetupPoints = {
  army: number;
  economy: number;
  population: number;
  stability: number;
};

export function fmtMoney(n: number): string {
  return n.toFixed(1);
}

export type Meta = {
  name: string;
  version: string;
  player: string;
  date_span: string;
  ui: Ui;
  setup: {
    difficulties: Difficulty[];
    default_difficulty: string;
    default_country: string;
    default_leader: string;
    points_total: number;
    army_per_point: number;
    economy_per_point: number;
    population_per_point: number;
    stability_max: number;
    points: SetupPoints;
  };
  map_style: MapStyle;
  day_tick_ms: number;
  army: {
    march_cooldown_days: number;
    recruit_money_per_army: number;
    recruit_cooldown_days: number;
  };
  nations_paint: Record<string, { fill: string; hover: string }>;
};

export type AdvisorPreset = { id: string; name: string; needs_key: boolean; site: string };

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init);
  const raw = await r.text();
  let body: unknown = raw;
  try {
    body = raw ? JSON.parse(raw) : null;
  } catch {
    body = raw;
  }
  if (!r.ok) {
    const detail = typeof body === "object" && body && "detail" in body
      ? String((body as { detail: unknown }).detail)
      : raw;
    throw new Error(detail);
  }
  return body as T;
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return json<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
}

export const api = {
  meta: () => json<Meta>("/api/meta"),
  mapGeojson: () => json<MapGeojson>("/api/map.geojson"),
  state: () => json<GameView>("/api/state"),
  saves: () => json<{ name: string; date: string }[]>("/api/saves"),
  newGame: (country: string, leader: string, difficulty: string, points: SetupPoints, name = "") =>
    post<{ name: string; state: GameView }>("/api/new", { country, leader, difficulty, name, ...points }),
  load: (name: string) => post<{ name: string; state: GameView }>("/api/load", { name }),
  deleteSave: (name: string) => post<{ ok: boolean }>("/api/delete", { name }),
  save: () => post<{ state: GameView }>("/api/save"),
  choice: (event_id: string, option_id: string) =>
    post<{ state: GameView }>("/api/choice", { event_id, option_id }),
  domestic: (action: string, province?: string) =>
    post<{ state: GameView }>("/api/domestic", { action, province: province ?? null }),
  moveArmy: (src: string, dst: string, amount: number) =>
    post<{ state: GameView }>("/api/army/move", { src, dst, amount }),
  colonize: (province: string, amount: number) =>
    post<{ state: GameView }>("/api/army/colonize", { province, amount }),
  demobilize: (province: string, amount: number) =>
    post<{ state: GameView }>("/api/army/demobilize", { province, amount }),
  recruit: (province: string, amount: number) =>
    post<{ state: GameView }>("/api/army/recruit", { province, amount }),
  pause: (paused: boolean) => post<{ state: GameView }>("/api/pause", { paused }),
  day: () => post<{ state: GameView }>("/api/day"),
  turn: () => post<{ state: GameView }>("/api/turn"),
  advisor: (question: string) => post<{ text: string; state: GameView }>("/api/advisor", { question }),
  advisorConfig: () => json<{ provider: string; presets: AdvisorPreset[] }>("/api/advisor/config"),
  setAdvisorConfig: (provider: string, api_key: string) =>
    post<{ provider: string }>("/api/advisor/config", { provider, api_key }),
  exit: () => post<{ ok: boolean }>("/api/exit"),
};
