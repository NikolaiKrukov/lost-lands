import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Map as MapGL, Source, Layer, type MapLayerMouseEvent, type MapRef } from "react-map-gl/maplibre";
import type { FillLayerSpecification, LineLayerSpecification, StyleSpecification } from "maplibre-gl";
import { api, type DomesticAction, type GameView, type MapGeojson, type MapStyle, type Province, type Ui } from "./api";

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

function cooldownKey(a: DomesticAction, p: Province): string {
  if (a.needs_kind === "foreign") return `${a.id}:${p.nation}`;
  return a.id;
}

function canUse(
  a: DomesticAction,
  p: Province,
  playerId: string,
  economy: number,
  ended: boolean,
  cooldowns: Record<string, number>,
): boolean {
  if (ended || (cooldowns[cooldownKey(a, p)] ?? 0) > 0 || a.cost_economy > economy) return false;
  if (a.needs_province) {
    if (a.needs_kind && p.kind !== a.needs_kind) return false;
    if (a.needs_port && !p.port) return false;
    if (!a.needs_kind) {
      if (p.controller !== playerId) return false;
    } else if (p.kind === "home" && p.controller !== playerId) {
      return false;
    }
  } else if (p.kind !== "home" || p.controller !== playerId) {
    return false;
  }
  return true;
}

function visible(a: DomesticAction, p: Province, playerId: string): boolean {
  if (a.needs_kind === "foreign" && p.relation === null) return false;
  if (!a.needs_province) return p.kind === "home";
  if (!a.needs_kind) return p.controller === playerId;
  if (a.needs_kind && p.kind !== a.needs_kind) return false;
  if (a.needs_port && !p.port) return false;
  return true;
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
  onAct: (action: string, province?: string) => void;
  onMarch: (src: string, dst: string) => void;
};

export default function MapBoard({ view, ui, busy, mapMode, mapStyle, nations, onAct, onMarch }: Props) {
  const mapRef = useRef<MapRef>(null);
  const hoverFid = useRef<number | null>(null);
  const leave = useRef<number>(0);
  const lockTimer = useRef<number>(0);
  const pinned = useRef(false);
  const shownId = useRef<string | null>(null);
  const pending = useRef<{ x: number; y: number; p: Province; fid: number } | null>(null);
  const [geo, setGeo] = useState<MapGeojson | null>(null);
  const [ready, setReady] = useState(false);
  const [tip, setTip] = useState<{ x: number; y: number; p: Province } | null>(null);
  const [marks, setMarks] = useState<{ x: number; y: number; id: string; text: string }[]>([]);
  const tipEl = useRef<HTMLDivElement>(null);
  const marksSig = useRef("");

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

  const byId = useMemo(() => {
    const m: Record<string, Province> = {};
    for (const p of view.map.provinces) m[p.id] = p;
    return m;
  }, [view.map.provinces]);

  const paintKey = view.map.provinces
    .map((p) => `${p.id}:${p.controller}:${p.threat}:${p.army}`)
    .join("|");

  useEffect(() => {
    const map = mapRef.current?.getMap();
    if (!ready || !map || !geo || !map.getSource("provinces")) return;
    for (const feat of geo.features) {
      const props = feat.properties;
      if (!props) continue;
      const p = byId[String(props.id)];
      if (!p) continue;
      const pair = pairFor(p, mapMode, mapStyle, nations, view.player.id);
      map.setFeatureState(
        { source: "provinces", id: Number(props.fid) },
        { fill_color: pair.fill, hover_color: pair.hover },
      );
    }
  }, [ready, geo, byId, paintKey, mapMode, mapStyle, nations, view.player.id]);

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
    window.clearTimeout(lockTimer.current);
    lockTimer.current = window.setTimeout(() => {
      pinned.current = true;
    }, lockMs);
  };

  const onMove = (ev: MapLayerMouseEvent) => {
    if (ev.originalEvent.buttons) return;
    window.clearTimeout(leave.current);
    const feat = ev.features?.[0];
    const pid = feat?.properties?.id as string | undefined;
    const p = pid ? byId[pid] : undefined;
    const x = ev.point.x + 14;
    const y = ev.point.y + 14;
    if (!feat || !p) {
      if (!pinned.current) {
        leave.current = window.setTimeout(() => {
          window.clearTimeout(lockTimer.current);
          pinned.current = false;
          shownId.current = null;
          pending.current = null;
          setHover(null);
          setTip(null);
        }, lockMs);
      }
      return;
    }
    const fid = feat.properties.fid as number;
    if (shownId.current === p.id) {
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
      window.clearTimeout(lockTimer.current);
      lockTimer.current = window.setTimeout(() => {
        const n = pending.current;
        if (n) show(n.x, n.y, n.p, n.fid, true);
      }, lockMs);
    }
    pending.current = { x, y, p, fid };
  };

  const closeSoon = () => {
    leave.current = window.setTimeout(() => {
      window.clearTimeout(lockTimer.current);
      pinned.current = false;
      shownId.current = null;
      pending.current = null;
      setHover(null);
      setTip(null);
    }, lockMs);
  };

  const keep = () => window.clearTimeout(leave.current);

  if (!geo) return <div className="map-wrap" />;

  return (
    <div className="map-wrap">
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
        onMove={onCamera}
        onMouseLeave={closeSoon}
        onLoad={() => setReady(true)}
        cursor="pointer"
      >
        <Source id="provinces" type="geojson" data={{ type: "FeatureCollection", features: geo.features }} promoteId="fid">
          <Layer {...FILL} />
          <Layer {...seam} />
          <Layer {...LINE} />
        </Source>
      </MapGL>
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
          <strong>{tip.p.name}</strong>
          {tip.p.kind !== "home" && tip.p.controller !== mapStyle.unowned_nation ? <div>{tip.p.nation_name}</div> : null}
          {tip.p.capital ? <div>{ui.capital_mark}</div> : null}
          <div>{hold(tip.p, view.player.id, mapStyle.unowned_nation, ui)}</div>
          {tip.p.controller === view.player.id || tip.p.army > 0 ? (
            <div>{ui.stat_army} {tip.p.army}</div>
          ) : null}
          {tip.p.controller === view.player.id ? (
            <>
              <div>{ui.stat_economy} {tip.p.economy}</div>
              <div>{ui.stat_population} {tip.p.population}</div>
            </>
          ) : null}
          <div>{ui.stat_threat} {tip.p.threat}（{tip.p.threat_band_name}）</div>
          {tip.p.kind === "home" && tip.p.fort > 0 ? <div>{ui.place_fort} {tip.p.fort}</div> : null}
          {tip.p.kind === "foreign" && tip.p.relation !== null ? (
            <div>{ui.stat_relation} {tip.p.relation}</div>
          ) : null}
          <div className="tip-acts">
            {tip.p.controller === view.player.id && tip.p.army > 0 && !view.ended
              ? tip.p.neighbors.map((nid) => {
                  const nb = byId[nid];
                  if (!nb) return null;
                  return (
                    <button key={nid} disabled={busy} onClick={() => onMarch(tip.p.id, nid)}>
                      {ui.march}{nb.name}
                    </button>
                  );
                })
              : null}
            {view.domestic.filter((a) => visible(a, tip.p, view.player.id)).map((a) => (
              <button
                key={a.id}
                disabled={busy || !canUse(a, tip.p, view.player.id, view.player.economy, view.ended, view.cooldowns)}
                onClick={() => onAct(a.id, a.needs_province ? tip.p.id : undefined)}
              >
                {actLabel(a, tip.p)}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
