import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { api, fmtMoney, type AdvisorPreset, type GameView, type Meta, type SetupPoints } from "./api";
import MapBoard, { type MapMode } from "./MapBoard";

function MapModeBtn({
  active,
  label,
  lockMs,
  onClick,
  children,
}: {
  active: boolean;
  label: string;
  lockMs: number;
  onClick: () => void;
  children: ReactNode;
}) {
  const [showLabel, setShowLabel] = useState(false);
  const timer = useRef(0);

  const onEnter = () => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setShowLabel(true), lockMs);
  };

  const onLeave = () => {
    window.clearTimeout(timer.current);
    setShowLabel(false);
  };

  return (
    <button
      type="button"
      className={`map-mode-btn${active ? " on" : ""}`}
      onClick={onClick}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      aria-label={label}
    >
      <span className="map-mode-icon">{children}</span>
      {showLabel && <span className="map-mode-label">{label}</span>}
    </button>
  );
}

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [view, setView] = useState<GameView | null>(null);
  const [question, setQuestion] = useState("");
  const [menu, setMenu] = useState<"none" | "esc" | "load" | "api">("none");
  const [saves, setSaves] = useState<{ name: string; date: string }[]>([]);
  const [presets, setPresets] = useState<AdvisorPreset[]>([]);
  const [provider, setProvider] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [country, setCountry] = useState("");
  const [leader, setLeader] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [points, setPoints] = useState<SetupPoints>({ army: 0, economy: 0, population: 0, stability: 0 });
  const [mapMode, setMapMode] = useState<MapMode>("political");
  const tickBusy = useRef(false);

  const run = useCallback(async (fn: () => Promise<void>) => {
    setErr("");
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    api.meta().then((m) => {
      setMeta(m);
      document.title = `${m.name} v${m.version}`;
      setCountry(m.setup.default_country);
      setLeader(m.setup.default_leader);
      setDifficulty(m.setup.default_difficulty);
      setPoints(m.setup.points);
      api.saves().then(setSaves);
    });
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && view) {
        setMenu((cur) => (cur === "none" ? "esc" : "none"));
        return;
      }
      if (e.code !== "Space" || !view || view.ended || menu !== "none" || busy) return;
      const t = e.target as HTMLElement;
      if (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable) return;
      e.preventDefault();
      void run(async () => {
        setView((await api.pause(!view.paused)).state);
      });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [view, menu, busy, run]);

  useEffect(() => {
    if (!view || view.paused || view.ended || busy || !meta?.day_tick_ms) return;
    const id = window.setInterval(async () => {
      if (tickBusy.current) return;
      tickBusy.current = true;
      try {
        const next = (await api.day()).state;
        setView(next);
        setErr("");
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        if (!/not found|404/i.test(msg)) setErr(msg);
      } finally {
        tickBusy.current = false;
      }
    }, meta.day_tick_ms);
    return () => window.clearInterval(id);
  }, [view?.paused, view?.ended, view?.turn, view?.day, busy, meta?.day_tick_ms]);

  const ui = meta?.ui;
  if (!meta || !ui) {
    return <div className="boot" />;
  }

  if (!view) {
    const used = points.army + points.economy + points.population + points.stability;
    const left = meta.setup.points_total - used;
    const pointsOk =
      left >= 0 &&
      points.stability <= meta.setup.stability_max &&
      Math.min(points.army, points.economy, points.population, points.stability) >= 0;
    const setPoint = (key: keyof SetupPoints, raw: string) => {
      const n = Number(raw);
      if (!Number.isFinite(n)) return;
      setPoints((cur) => ({ ...cur, [key]: Math.floor(n) }));
    };
    return (
      <div className="desk">
        <div className="modal">
          <div className="setup">
            <h2>{ui.setup_title}</h2>
            <div className="setup-field">
              <label>{ui.setup_country}</label>
              <input value={country} onChange={(e) => setCountry(e.target.value)} autoFocus />
            </div>
            <div className="setup-field">
              <label>{ui.setup_leader}</label>
              <input value={leader} onChange={(e) => setLeader(e.target.value)} />
            </div>
            <div className="setup-field">
              <label>{ui.setup_difficulty}</label>
              <div className="setup-diffs">
                {meta.setup.difficulties.map((d) => (
                  <button
                    key={d.id}
                    className={difficulty === d.id ? "primary" : ""}
                    onClick={() => setDifficulty(d.id)}
                  >
                    {d.name}
                  </button>
                ))}
              </div>
            </div>
            <div className="setup-field">
              <label>{ui.setup_points}</label>
              <p className={left < 0 ? "setup-note over" : "setup-note"}>
                {ui.setup_points_left} {left} / {meta.setup.points_total}
              </p>
              <div className="setup-points">
                <label>
                  {ui.stat_army}（1点={meta.setup.army_per_point}）
                  <input
                    type="number"
                    min={0}
                    value={points.army}
                    onChange={(e) => setPoint("army", e.target.value)}
                  />
                </label>
                <label>
                  {ui.stat_economy}
                  <input
                    type="number"
                    min={0}
                    value={points.economy}
                    onChange={(e) => setPoint("economy", e.target.value)}
                  />
                </label>
                <label>
                  {ui.stat_population}（1点={meta.setup.population_per_point}）
                  <input
                    type="number"
                    min={0}
                    value={points.population}
                    onChange={(e) => setPoint("population", e.target.value)}
                  />
                </label>
                <label>
                  {ui.stat_stability}（最高{meta.setup.stability_max}）
                  <input
                    type="number"
                    min={0}
                    max={meta.setup.stability_max}
                    value={points.stability}
                    onChange={(e) => setPoint("stability", e.target.value)}
                  />
                </label>
              </div>
            </div>
            <button
              className="primary"
              disabled={busy || !pointsOk}
              onClick={() => run(async () => {
                setView((await api.newGame(country, leader, difficulty, points)).state);
              })}
            >
              {ui.setup_start}
            </button>
            {saves.length > 0 && (
              <>
                <p className="setup-note">{ui.setup_load}</p>
                {saves.map((s) => (
                  <div className="save-row" key={s.name}>
                    <button
                      disabled={busy}
                      onClick={() => run(async () => {
                        setView((await api.load(s.name)).state);
                      })}
                    >
                      {s.date} · {s.name}
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => run(async () => {
                        await api.deleteSave(s.name);
                        setSaves(await api.saves());
                      })}
                    >
                      {ui.menu_delete}
                    </button>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
        {err && <p className="err float">{ui.err_prefix}{err}</p>}
      </div>
    );
  }

  const p = view.player;
  const lockMs = meta.map_style.hover_lock_ms;

  return (
    <div className="desk">
      <header className="game-head">
        <div className="who">
          <em>{p.name}</em>
          <span className="who-date">{view.date}</span>
          <span className="who-leader">{p.leader}</span>
        </div>
        <div className="map-mode">
          <MapModeBtn
            active={mapMode === "political"}
            label={ui.map_political}
            lockMs={lockMs}
            onClick={() => setMapMode("political")}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 6h6v12H4V6zm10 0h6v8h-6V6zM4 4h16v2H4V4zm10 8h6v6h-6v-6z" fill="currentColor" />
            </svg>
          </MapModeBtn>
          <MapModeBtn
            active={mapMode === "threat"}
            label={ui.map_threat}
            lockMs={lockMs}
            onClick={() => setMapMode("threat")}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 3 2 20h20L12 3zm0 5 6.2 10H5.8L12 8zm-1 4h2v4h-2v-4zm0 5h2v2h-2v-2z" fill="currentColor" />
            </svg>
          </MapModeBtn>
        </div>
        <div className="stats">
          <div className="stat-cell"><b>{ui.stat_army}<strong>{p.army}</strong></b></div>
          <div className="stat-cell"><b>{ui.stat_economy}<strong>{p.economy}</strong></b></div>
          <div className="stat-cell"><b>{ui.stat_money}<strong>{fmtMoney(p.money)}</strong></b></div>
          <div className="stat-cell"><b>{ui.stat_population}<strong>{p.population}</strong></b></div>
          <div className="stat-cell"><b>{ui.stat_stability}<strong>{p.stability}/{meta.setup.stability_max}</strong></b></div>
        </div>
        <button
          className="primary head-play"
          disabled={busy || view.ended}
          onClick={() => run(async () => {
            setView((await api.pause(!view.paused)).state);
          })}
        >
          {view.paused ? ui.resume : ui.pause}
        </button>
      </header>
      <div className="stage">
        <MapBoard
          view={view}
          ui={ui}
          busy={busy}
          mapMode={mapMode}
          mapStyle={meta.map_style}
          nations={meta.nations_paint}
          recruitMoneyPerArmy={meta.army.recruit_money_per_army}
          onAct={(action, province) => run(async () => {
            setView((await api.domestic(action, province)).state);
          })}
          onMarch={(src, dst, amount) => run(async () => {
            setView((await api.moveArmy(src, dst, amount)).state);
          })}
          onColonize={(province, amount) => run(async () => {
            setView((await api.colonize(province, amount)).state);
          })}
          onDemobilize={(province, amount) => run(async () => {
            setView((await api.demobilize(province, amount)).state);
          })}
          onRecruit={(province, amount) => run(async () => {
            setView((await api.recruit(province, amount)).state);
          })}
        />
        <aside className="hud">
          <div className="card advisor">
            <h2>{ui.advisor_title}</h2>
            {view.last_advisor && <p className="advisor-reply">{view.last_advisor}</p>}
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder={ui.ask_placeholder}
              rows={2}
            />
            <div className="row">
              <button className="primary" disabled={busy} onClick={() => run(async () => {
                setView((await api.advisor(question)).state);
              })}>{ui.ask_advisor}</button>
              <button disabled={busy} onClick={() => run(async () => {
                const cfg = await api.advisorConfig();
                setPresets(cfg.presets);
                setProvider(cfg.provider);
                setApiKey("");
                setMenu("api");
              })}>{ui.configure_api}</button>
            </div>
          </div>
          <div className="card paper">
            <h2>{ui.paper_title}</h2>
            {[...view.news].reverse().map((n) => (
              <article key={`${n.event_id}-${n.turn}-${n.title}`}>
                <h3>{n.title}</h3>
                <p>{n.text}</p>
              </article>
            ))}
          </div>
        </aside>
      </div>
      {view.pending.map((d) => (
        <div key={d.event_id} className="modal">
          <div>
            <h2>{d.title}</h2>
            <p>{d.text}</p>
            {d.options.map((o) => (
              <button key={o.id} className="primary" disabled={busy} onClick={() => run(async () => {
                setView((await api.choice(d.event_id, o.id)).state);
              })}>{o.text}</button>
            ))}
          </div>
        </div>
      ))}
      {view.ended && (
        <div className="modal">
          <div>
            <h2>{ui.ended_title}</h2>
            <p>{view.ending}</p>
          </div>
        </div>
      )}
      {menu !== "none" && (
        <div className="modal menu" onClick={() => setMenu("none")}>
          <div onClick={(e) => e.stopPropagation()}>
            {menu === "esc" && (
              <>
                <button onClick={() => setMenu("none")}>{ui.menu_continue}</button>
                <button disabled={busy} onClick={() => run(async () => {
                  await api.save();
                  setMenu("none");
                })}>{ui.menu_save}</button>
                <button disabled={busy} onClick={() => run(async () => {
                  setSaves(await api.saves());
                  setMenu("load");
                })}>{ui.menu_load}</button>
                <button onClick={() => {
                  setMapMode("political");
                  setPoints(meta.setup.points);
                  setView(null);
                  setMenu("none");
                }}>{ui.menu_restart}</button>
                <button disabled={busy} onClick={() => run(async () => {
                  await api.exit();
                  window.close();
                })}>{ui.menu_quit}</button>
              </>
            )}
            {menu === "load" && (
              <>
                {saves.length === 0 && <p>{ui.saves_empty}</p>}
                {saves.map((s) => (
                  <div className="save-row" key={s.name}>
                    <button disabled={busy} onClick={() => run(async () => {
                      const r = await api.load(s.name);
                      setView(r.state);
                      setMenu("none");
                    })}>{s.date} · {s.name}</button>
                    <button disabled={busy} onClick={() => run(async () => {
                      await api.deleteSave(s.name);
                      setSaves(await api.saves());
                    })}>{ui.menu_delete}</button>
                  </div>
                ))}
                <button onClick={() => setMenu("esc")}>{ui.menu_continue}</button>
              </>
            )}
            {menu === "api" && (
              <>
                {presets.map((pr) => (
                  <button
                    key={pr.id}
                    className={provider === pr.id ? "primary" : ""}
                    onClick={() => setProvider(pr.id)}
                  >{pr.name}</button>
                ))}
                {presets.find((x) => x.id === provider)?.needs_key && (
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                  />
                )}
                <button className="primary" disabled={busy} onClick={() => run(async () => {
                  await api.setAdvisorConfig(provider, apiKey);
                  setMenu("none");
                })}>{ui.api_save}</button>
              </>
            )}
          </div>
        </div>
      )}
      {err && <p className="err float">{ui.err_prefix}{err}</p>}
    </div>
  );
}
