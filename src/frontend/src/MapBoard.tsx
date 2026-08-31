import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Map as MapGL, Source, Layer, type MapLayerMouseEvent, type MapRef } from "react-map-gl/maplibre";
import type { FillLayerSpecification, LineLayerSpecification, StyleSpecification } from "maplibre-gl";
import { api, fmtMoney, type DomesticAction, type GameView, type MapGeojson, type MapStyle, type Province, type Ui } from "./api";

const STYLE: StyleSpecification = {
  version: 8,
  name: "blank",
  sources: {},
  layers: [{ id: "background", type: "background", paint: { "background-color": "#0e1214" } }],
};

const FILL: FillLayerSpecification = {
  id: "provinces-fill",
  type: "fill",
  source: "provinces",
  paint: {
    "fill-antialias": true,
    "fill-color": [
      "case",
      ["boolean", ["feature-state", "hover"], false],
      ["coalesce", ["feature-state", "hover_color"], ["get", "fill_hover"]],
      ["coalesce", ["feature-state", "fill_color"], ["get", "fill"]],
    ],
  },
};

const LINE: LineLayerSpecification = {
  id: "provinces-line",
  type: "line",
  source: "provinces",
  paint: {
    "line-color": ["case", ["==", ["get", "capital"], true], "#d8c98a", "rgba(12,10,8,0.45)"],
    "line-width": ["interpolate", ["linear"], ["zoom"], 1, 0.25, 5, 0.7, 9, 1.1],
  },
};

const MARCH_FILL: FillLayerSpecification = {
  id: "provinces-march-fill",
  type: "fill",
  source: "provinces",
  paint: {
    "fill-color": "#e8c858",
    "fill-opacity": [
      "case",
      ["boolean", ["feature-state", "march_target"], false],
      0.22,
      0,
    ],
  },
};

const MARCH_LINE: LineLayerSpecification = {
  id: "provinces-march",
  type: "line",
  source: "provinces",
  layout: { "line-join": "round", "line-cap": "round" },
  paint: {
    "line-color": [
      "case",
      ["boolean", ["feature-state", "march_target"], false],
      "#e8c858",
      "rgba(0,0,0,0)",
    ],
    "line-width": [
      "case",
      ["boolean", ["feature-state", "march_target"], false],
      ["interpolate", ["linear"], ["zoom"], 2, 2.5, 6, 4, 10, 6],
      0,
    ],
  },
};

function cooldownKey(a: DomesticAction, p: Province): string {
  if (a.needs_kind === "foreign") return `${a.id}:${p.nation}`;
  return a.id;
}

function marchCdKey(provinceId: string): string {
  return `march:${provinceId}`;
}

function hasFriendlyArmy(p: Province, playerId: string): boolean {
  return p.army > 0 && p.army_owner === playerId;
}

function showArmyInput(p: Province, playerId: string, unownedNation: string): boolean {
  if (p.controller === playerId) return true;
  return p.controller === unownedNation && hasFriendlyArmy(p, playerId);
}

function canColonize(p: Province, playerId: string, unownedNation: string): boolean {
  return p.controller === unownedNation && hasFriendlyArmy(p, playerId);
}

function canMarchFrom(p: Province, playerId: string, unownedNation: string): boolean {
  if (p.army <= 0) return false;
  if (p.controller === playerId) return true;
  return p.controller === unownedNation && p.army_owner === playerId;
}

function visible(a: DomesticAction, p: Province, playerId: string): boolean {
  if (!a.needs_province) return false;
  if (p.controller !== playerId) return false;
  if (a.needs_port && !p.port) return false;
  return true;
}

function canUse(
  a: DomesticAction,
  p: Province,
  money: number,
  ended: boolean,
  cooldowns: Record<string, number>,
): boolean {
  if (ended || (cooldowns[cooldownKey(a, p)] ?? 0) > 0) return false;
  if (a.cost_money > money + 1e-9) return false;
  return true;
}

const DEFAULT_ARMY_AMT = 100;

function recruitCap(population: number): number {
  return Math.floor(population / 2);
}

function recruitCost(amount: number, rate: number): number {
  return amount * rate;
}

function recruitLabel(ui: Ui, amount: number, rate: number): string {
  if (amount <= 0) return ui.recruit;
  const cost = fmtMoney(recruitCost(amount, rate));
  return `${ui.recruit}（${ui.stat_money}-${cost}）（${ui.stat_army}+${amount}）（${ui.stat_population}-${amount}）`;
}

function demobilizeLabel(ui: Ui, amount: number): string {
  if (amount <= 0) return ui.demobilize;
  return `${ui.demobilize}（${ui.stat_army}-${amount}）（${ui.stat_population}+${amount}）`;
}

function actLabel(a: DomesticAction, p: Province): string {
  if (a.needs_kind === "foreign") return `${a.title}（${p.nation_name}）`;
  return a.title;
}

function hold(p: Province, playerId: string, unownedNation: string, ui: Ui): string {
  if (p.controller === unownedNation) return ui.place_unowned;
  if (p.kind === "home") {
    return p.controller === playerId ? ui.place_ours : `${ui.place_lost} ${p.controller_name}`;
  }
  return p.controller_name;
}

export type MapMode = "political" | "threat";

function nationPaint(
  nations: Record<string, { fill: string; hover: string }>,
  nid: string,
): { fill: string; hover: string } {
  const pair = nations[nid];
  if (!pair) throw new Error(`没有国家颜色 ${nid}`);
  return pair;
}

function pairFor(
  p: Province,
  mode: MapMode,
  style: MapStyle,
  nations: Record<string, { fill: string; hover: string }>,
  playerId: string,
): { fill: string; hover: string } {
  const owned = p.controller !== style.unowned_nation;
  if (mode === "threat") {
    if (owned) return nationPaint(nations, p.controller);
    const band = style.threat.bands.find((b) => p.threat >= b.min && p.threat <= b.max);
    if (!band) throw new Error(`威胁度 ${p.threat} 没有对应颜色`);
    return { fill: band.fill, hover: band.hover };
  }
  if (p.kind === "home" && p.controller !== playerId) return style.lost;
  if (owned) return nationPaint(nations, p.controller);
  return style.unowned;
}

type Props = {
  view: GameView;
  ui: Ui;
  busy: boolean;
  mapMode: MapMode;
  mapStyle: MapStyle;
  nations: Record<string, { fill: string; hover: string }>;
  recruitMoneyPerArmy: number;
  onAct: (action: string, province?: string) => void;
  onMarch: (src: string, dst: string, amount: number) => void;
  onColonize: (province: string, amount: number) => void;
  onDemobilize: (province: string, amount: number) => void;
  onRecruit: (province: string, amount: number) => void;
};

export default function MapBoard({
  view,
  ui,
  busy,
  mapMode,
  mapStyle,
  nations,
  recruitMoneyPerArmy,
  onAct,
  onMarch,
  onColonize,
  onDemobilize,
  onRecruit,
}: Props) {
  const mapRef = useRef<MapRef>(null);
  const hoverFid = useRef<number | null>(null);
  const leave = useRef<number>(0);
  const pinTimer = useRef<number>(0);
  const switchTimer = useRef<number>(0);
  const pinned = useRef(false);
  const shownId = useRef<string | null>(null);
  const pending = useRef<{ x: number; y: number; p: Province; fid: number } | null>(null);
  const marchFromRef = useRef<string | null>(null);
  const [geo, setGeo] = useState<MapGeojson | null>(null);
  const [ready, setReady] = useState(false);
  const [tip, setTip] = useState<{ x: number; y: number; p: Province } | null>(null);
  const [armyAmount, setArmyAmount] = useState(0);
  const [marchFrom, setMarchFrom] = useState<string | null>(null);
  const [marks, setMarks] = useState<{ x: number; y: number; id: string; text: string }[]>([]);
  const tipEl = useRef<HTMLDivElement>(null);
  const marksSig = useRef("");

  marchFromRef.current = marchFrom;

  const lockMs = mapStyle.hover_lock_ms;
  const seamStops = mapStyle.seam.zooms.flatMap((z, i) => [z, mapStyle.seam.widths[i]]);
  const seam: LineLayerSpecification = {
    id: "provinces-seam",
    type: "line",
    source: "provinces",
    layout: { "line-join": "round" },
    paint: {
      "line-color": ["coalesce", ["feature-state", "fill_color"], ["get", "fill"]],
      "line-width": ["interpolate", ["linear"], ["zoom"], ...seamStops],
    },
  };

  useEffect(() => {
    api.mapGeojson().then(setGeo).catch((e) => {
      console.error(e);
    });
  }, []);

  useEffect(() => {
    setArmyAmount(DEFAULT_ARMY_AMT);
    setMarchFrom(null);
  }, [tip?.p.id]);

  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key !== "Escape" || marchFromRef.current) return;
      resetTipRef.current();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const byId = useMemo(() => {
    const m: Record<string, Province> = {};
    for (const p of view.map.provinces) m[p.id] = p;
    return m;
  }, [view.map.provinces]);

  const paintKey = view.map.provinces
    .map((p) => `${p.id}:${p.controller}:${p.army_owner}:${p.threat}:${p.army}`)
    .join("|");

  useEffect(() => {
    const map = mapRef.current?.getMap();
    if (!ready || !map || !geo || !map.getSource("provinces")) return;
    const targets = new Set<string>();
    if (marchFrom) {
      const src = byId[marchFrom];
      if (src) for (const nid of src.neighbors) targets.add(nid);
    }
    for (const feat of geo.features) {
      const props = feat.properties;
      if (!props) continue;
      const pid = String(props.id);
      const p = byId[pid];
      if (!p) continue;
      const pair = pairFor(p, mapMode, mapStyle, nations, view.player.id);
      map.setFeatureState(
        { source: "provinces", id: Number(props.fid) },
        {
          fill_color: pair.fill,
          hover_color: pair.hover,
          march_target: targets.has(pid),
        },
      );
    }
  }, [ready, geo, byId, paintKey, mapMode, mapStyle, nations, view.player.id, marchFrom]);

  useEffect(() => {
    setTip((cur) => {
      if (!cur) return cur;
      const p = byId[cur.p.id];
      return p ? { ...cur, p } : cur;
    });
  }, [byId]);

  const refreshMarks = () => {
    const map = mapRef.current?.getMap();
    if (!map || !geo) return;
    const next: { x: number; y: number; id: string; text: string }[] = [];
    for (const feat of geo.features) {
      const props = feat.properties;
      if (!props) continue;
      const pr = byId[String(props.id)];
      if (!pr || pr.army <= 0) continue;
      const lon = props.label_lon as number | undefined;
      const lat = props.label_lat as number | undefined;
      if (lon == null || lat == null) continue;
      const pt = map.project([lon, lat]);
      next.push({ x: Math.round(pt.x), y: Math.round(pt.y), id: pr.id, text: String(pr.army) });
    }
    const sig = next.map((m) => `${m.id}:${m.x}:${m.y}:${m.text}`).join("|");
    if (sig === marksSig.current) return;
    marksSig.current = sig;
    setMarks(next);
  };
  const refreshMarksRef = useRef(refreshMarks);
  refreshMarksRef.current = refreshMarks;
  const onCamera = useCallback(() => {
    refreshMarksRef.current();
  }, []);

  useEffect(() => {
    if (!ready) return;
    refreshMarks();
  }, [ready, geo, byId, paintKey]);

  const setHover = (fid: number | null) => {
    const map = mapRef.current?.getMap();
    if (!map) return;
    if (hoverFid.current !== null) {
      map.setFeatureState({ source: "provinces", id: hoverFid.current }, { hover: false });
    }
    hoverFid.current = fid;
    if (fid !== null) {
      map.setFeatureState({ source: "provinces", id: fid }, { hover: true });
    }
  };

  const show = (x: number, y: number, p: Province, fid: number, freeze: boolean) => {
    pinned.current = freeze;
    shownId.current = p.id;
    pending.current = null;
    setHover(fid);
    setTip({ x, y, p });
  };

  const armPin = () => {
    window.clearTimeout(pinTimer.current);
    pinTimer.current = window.setTimeout(() => {
      pinned.current = true;
      const el = tipEl.current;
      if (el) {
        const x = Number.parseFloat(el.style.left);
        const y = Number.parseFloat(el.style.top);
        if (Number.isFinite(x) && Number.isFinite(y)) {
          setTip((cur) => (cur ? { ...cur, x, y } : cur));
        }
      }
    }, lockMs);
  };

  const resetTip = () => {
    window.clearTimeout(pinTimer.current);
    window.clearTimeout(switchTimer.current);
    window.clearTimeout(leave.current);
    pinned.current = false;
    shownId.current = null;
    pending.current = null;
    setHover(null);
    setTip(null);
  };
  const resetTipRef = useRef(resetTip);
  resetTipRef.current = resetTip;

  const switchProvince = (x: number, y: number, p: Province, fid: number) => {
    show(x, y, p, fid, false);
    armPin();
  };

  const onMove = (ev: MapLayerMouseEvent) => {
    if (ev.originalEvent.buttons) return;
    window.clearTimeout(leave.current);
    const feat = ev.features?.[0];
    const pid = feat?.properties?.id as string | undefined;
    const p = pid ? byId[pid] : undefined;
    const x = ev.point.x + 14;
    const y = ev.point.y + 14;

    if (marchFromRef.current) {
      const src = byId[marchFromRef.current];
      if (feat && p && src?.neighbors.includes(p.id)) {
        setHover(feat.properties.fid as number);
      }
      return;
    }

    if (!feat || !p) {
      if (!pinned.current) {
        leave.current = window.setTimeout(resetTip, lockMs);
      }
      return;
    }
    const fid = feat.properties.fid as number;
    if (shownId.current === p.id) {
      pending.current = null;
      window.clearTimeout(switchTimer.current);
      if (!pinned.current && tipEl.current) {
        tipEl.current.style.left = `${x}px`;
        tipEl.current.style.top = `${y}px`;
      }
      return;
    }
    if (!pinned.current) {
      show(x, y, p, fid, false);
      armPin();
      return;
    }
    if (pending.current?.p.id !== p.id) {
      setHover(fid);
      window.clearTimeout(switchTimer.current);
      switchTimer.current = window.setTimeout(() => {
        const n = pending.current;
        if (n) switchProvince(n.x, n.y, n.p, n.fid);
      }, lockMs);
    }
    pending.current = { x, y, p, fid };
  };

  const onClick = (ev: MapLayerMouseEvent) => {
    if (marchFromRef.current) {
      onMarchClick(ev);
      return;
    }
    if (pinned.current) {
      const feat = ev.features?.[0];
      const pid = feat?.properties?.id as string | undefined;
      const p = pid ? byId[pid] : undefined;
      if (feat && p && shownId.current !== p.id) {
        window.clearTimeout(switchTimer.current);
        pending.current = null;
        switchProvince(ev.point.x + 14, ev.point.y + 14, p, feat.properties.fid as number);
      }
    }
  };

  const onMarchClick = (ev: MapLayerMouseEvent) => {
    const from = marchFromRef.current;
    if (!from || busy) return;
    const pid = ev.features?.[0]?.properties?.id as string | undefined;
    if (!pid) return;
    const src = byId[from];
    if (!src?.neighbors.includes(pid)) return;
    const cooling = (view.cooldowns[marchCdKey(from)] ?? 0) > 0;
    if (armyAmount < 1 || armyAmount > src.army || cooling || view.ended) return;
    setMarchFrom(null);
    onMarch(from, pid, armyAmount);
  };

  const closeSoon = () => {
    if (marchFromRef.current) return;
    leave.current = window.setTimeout(resetTip, lockMs);
  };

  const keep = () => window.clearTimeout(leave.current);

  if (!geo) return <div className="map-wrap" />;

  const playerId = view.player.id;
  const unowned = mapStyle.unowned_nation;
  const armyOk = armyAmount > 0;
  const marchSrc = marchFrom ? byId[marchFrom] : tip?.p;
  const marchCooling = marchSrc ? (view.cooldowns[marchCdKey(marchSrc.id)] ?? 0) > 0 : false;
  const armyInput = tip ? showArmyInput(tip.p, playerId, unowned) : false;

  return (
    <div className={`map-wrap${marchFrom ? " march-pick" : ""}`}>
      <MapGL
        ref={mapRef}
        mapStyle={STYLE}
        style={{ width: "100%", height: "100%" }}
        initialViewState={geo.camera}
        renderWorldCopies={true}
        minZoom={1.5}
        maxZoom={12}
        attributionControl={{ compact: true, customAttribution: geo.attribution }}
        interactiveLayerIds={["provinces-fill"]}
        onMouseMove={onMove}
        onClick={onClick}
        onMove={onCamera}
        onMouseLeave={closeSoon}
        onLoad={() => setReady(true)}
        cursor={marchFrom ? "crosshair" : "pointer"}
      >
        <Source id="provinces" type="geojson" data={{ type: "FeatureCollection", features: geo.features }} promoteId="fid">
          <Layer {...FILL} />
          <Layer {...MARCH_FILL} />
          <Layer {...seam} />
          <Layer {...LINE} />
          <Layer {...MARCH_LINE} />
        </Source>
      </MapGL>
      {marchFrom ? <div className="march-hint">点击高亮邻省开进</div> : null}
      {marks.map((m) => (
        <div key={m.id} className="army-mark" style={{ left: m.x, top: m.y }}>{m.text}</div>
      ))}
      {tip && (
        <div
          ref={tipEl}
          className="tooltip"
          style={{ left: tip.x, top: tip.y }}
          onMouseEnter={keep}
          onMouseLeave={closeSoon}
        >
          <div className="tip-head">
            <strong>{tip.p.name}</strong>
            {armyInput ? (
              <label className="tip-army-amt">
                {ui.stat_army}
                <input
                  type="number"
                  min={0}
                  step={1}
                  inputMode="numeric"
                  value={armyAmount}
                  onChange={(e) => {
                    const n = Number(e.target.value);
                    setArmyAmount(Number.isFinite(n) ? Math.max(0, Math.floor(n)) : 0);
                  }}
                />
              </label>
            ) : null}
          </div>
          {tip.p.kind !== "home" && tip.p.controller !== unowned ? <div>{tip.p.nation_name}</div> : null}
          {tip.p.capital ? <div>{ui.capital_mark}</div> : null}
          <div>{hold(tip.p, playerId, unowned, ui)}</div>
          <div>{ui.stat_army} {tip.p.army}</div>
          <div>{ui.stat_economy} {tip.p.economy}</div>
          <div>{ui.stat_population} {tip.p.population}</div>
          <div>{ui.stat_threat} {tip.p.threat}（{tip.p.threat_band_name}）</div>
          {tip.p.kind === "home" && tip.p.fort > 0 ? <div>{ui.place_fort} {tip.p.fort}</div> : null}
          {tip.p.kind === "foreign" && tip.p.relation !== null ? (
            <div>{ui.stat_relation} {tip.p.relation}</div>
          ) : null}
          <div className="tip-acts">
            {(() => {
              const domestic = view.domestic.filter((a) => visible(a, tip.p, playerId));
              const canMarch = !view.ended && canMarchFrom(tip.p, playerId, unowned);
              const marchDisabled = busy || !armyOk || armyAmount > tip.p.army || marchCooling;
              const armyCol = [
                canMarch && !marchFrom ? (
                  <button
                    key="march"
                    disabled={marchDisabled}
                    onClick={() => setMarchFrom(tip.p.id)}
                  >
                    {ui.march}
                  </button>
                ) : null,
                canMarch && marchFrom === tip.p.id ? (
                  <button
                    key="march-cancel"
                    type="button"
                    onClick={() => setMarchFrom(null)}
                  >
                    取消
                  </button>
                ) : null,
                canColonize(tip.p, playerId, unowned) ? (
                  <button
                    key="colonize"
                    disabled={busy || !armyOk || armyAmount > tip.p.army || view.ended}
                    onClick={() => onColonize(tip.p.id, armyAmount)}
                  >
                    {ui.colonize}
                  </button>
                ) : null,
                tip.p.controller === playerId ? (
                  <button
                    key="recruit"
                    disabled={
                      busy || !armyOk || view.ended
                      || armyAmount > recruitCap(tip.p.population)
                      || recruitCost(armyAmount, recruitMoneyPerArmy) > view.player.money + 1e-9
                      || (view.cooldowns.recruit ?? 0) > 0
                    }
                    onClick={() => onRecruit(tip.p.id, armyAmount)}
                  >
                    {recruitLabel(ui, armyAmount, recruitMoneyPerArmy)}
                  </button>
                ) : null,
                tip.p.army > 0 && tip.p.controller === playerId ? (
                  <button
                    key="demobilize"
                    disabled={
                      busy || !armyOk || armyAmount > tip.p.army || view.ended
                    }
                    onClick={() => onDemobilize(tip.p.id, armyAmount)}
                  >
                    {demobilizeLabel(ui, armyAmount)}
                  </button>
                ) : null,
              ].filter(Boolean);
              if (!domestic.length && !armyCol.length) return null;
              return (
                <>
                  <div className="tip-acts-col">
                    {domestic.map((a) => (
                      <button
                        key={a.id}
                        disabled={busy || !canUse(a, tip.p, view.player.money, view.ended, view.cooldowns)}
                        onClick={() => onAct(a.id, tip.p.id)}
                      >
                        {actLabel(a, tip.p)}
                      </button>
                    ))}
                  </div>
                  {armyCol.length > 0 ? (
                    <div className="tip-acts-col tip-acts-army">{armyCol}</div>
                  ) : null}
                </>
              );
            })()}
          </div>
        </div>
      )}
    </div>
  );
}
