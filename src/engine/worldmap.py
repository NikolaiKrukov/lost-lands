"""从 src/maps 的美加一级政区生成游戏用地图。python -m src.engine.worldmap

extract：从 Natural Earth 抽出美加省界，写入 source。
默认：读 source，按 worldmap.yaml 写成 output。
"""

from __future__ import annotations

import json
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from src.engine.config import CONFIG_DIR, SRC_ROOT, MapStyleConfig, _load_yaml, map_geojson_path

ADMIN1_URL = "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_1_states_provinces.zip"
ADMIN1_STEM = "ne_10m_admin_1_states_provinces"


def _shapely():
    from shapely.geometry import box, mapping, shape
    from shapely.ops import unary_union

    return shape, unary_union, mapping, box


def _pyshp():
    import shapefile

    return shapefile


def _recipe(config_dir: Path) -> dict:
    return _load_yaml(config_dir / "worldmap.yaml")


def _src_file(rel: str) -> Path:
    return SRC_ROOT / rel


def _download_zip(url: str, dest: Path, timeout: int = 120) -> None:
    print(f"下载 {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "country-agents-map/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        dest.write_bytes(r.read())


def _extract_shp(zip_path: Path, dest_dir: Path, stem: str) -> Path:
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            name = Path(info.filename).name
            if name.startswith(stem) and name.endswith((".shp", ".shx", ".dbf", ".prj", ".cpg")):
                (dest_dir / name).write_bytes(z.read(info))
    shp = dest_dir / f"{stem}.shp"
    if not shp.is_file():
        raise FileNotFoundError(f"{zip_path} 里没有 {stem}.shp")
    return shp


def _records(shp_path: Path, encoding: str = "utf-8") -> list[tuple[dict, dict]]:
    shapefile = _pyshp()
    reader = shapefile.Reader(str(shp_path), encoding=encoding)
    try:
        names = [f[0].lower() for f in reader.fields[1:]]
        rows = []
        for sr in reader.iterShapeRecords():
            rec = {names[i]: sr.record[i] for i in range(len(names))}
            geo = sr.shape.__geo_interface__
            if geo is None or geo.get("type") in (None, "Null"):
                continue
            rows.append((rec, geo))
        return rows
    finally:
        reader.close()


def _text(rec: dict, *keys: str) -> str:
    for k in keys:
        v = rec.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s and s not in ("None", "nan", "-99"):
            return s
    return ""


def _iso2(rec: dict) -> str:
    return _text(rec, "iso_a2", "iso_a2_eh", "iso_a2_hr").upper()


def _adm1_iso(rec: dict) -> str:
    return _text(rec, "iso_3166_2", "iso_31662", "code_hasc").upper()


def _fills(kind: str, nation: str, style: MapStyleConfig, nations: dict) -> tuple[str, str]:
    if kind == "home":
        n = nations[nation]
        return n["fill"], n["fill_hover"]
    return style.unowned.fill, style.unowned.hover


def _round_coords(obj, digits: int):
    if type(obj) is float or type(obj) is int:
        return round(float(obj), digits)
    if type(obj) is list:
        return [_round_coords(x, digits) for x in obj]
    return obj


def _split_dateline(geom, box):
    """日界线两侧拆开，避免阿拉斯加把整张地图涂满。"""
    world = box(-180, -90, 180, 90)
    g = geom.intersection(world)
    if g.is_empty:
        return geom
    minx, _, maxx, _ = g.bounds
    if maxx - minx < 180:
        return g
    west = g.intersection(box(-180, -90, 0, 90))
    east = g.intersection(box(0, -90, 180, 90))
    parts = [p for p in (west, east) if p is not None and not p.is_empty]
    if not parts:
        return g
    if len(parts) == 1:
        return parts[0]
    from shapely.ops import unary_union
    return unary_union(parts)


def _attach_neighbors(features, shape) -> None:
    from shapely.prepared import prep

    geoms = [shape(f["geometry"]) for f in features]
    ids = [f["properties"]["id"] for f in features]
    ready = [prep(g) for g in geoms]
    for i, g in enumerate(geoms):
        nbs = [ids[j] for j, p in enumerate(ready) if i != j and p.intersects(g)]
        features[i]["properties"]["neighbors"] = nbs
        pt = g.representative_point()
        features[i]["properties"]["label_lon"] = round(float(pt.x), 4)
        features[i]["properties"]["label_lat"] = round(float(pt.y), 4)


def _clean(geom, simplify: float, overlap: float, box):
    if geom is None or geom.is_empty:
        return None
    g = geom
    if not g.is_valid:
        g = g.buffer(0)
    if g.is_empty:
        return None
    simple = g.simplify(simplify, preserve_topology=True)
    if simple.is_empty:
        simple = g.simplify(simplify / 4, preserve_topology=True)
    if simple.is_empty:
        simple = g
    if overlap > 0 and not simple.is_empty:
        padded = simple.buffer(overlap)
        if not padded.is_empty:
            tight = padded.simplify(simplify, preserve_topology=True)
            if not tight.is_empty:
                simple = tight
            else:
                simple = padded
    split = _split_dateline(simple, box)
    if split is None or split.is_empty:
        return None
    return split


def _slug(rec: dict, used: set[str]) -> str:
    raw = _adm1_iso(rec) or _text(rec, "adm1_code") or _text(rec, "name")
    pid = raw.lower().replace(" ", "_").replace("/", "_")
    pid = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in pid)
    if not pid:
        pid = "p"
    base = pid
    n = 2
    while pid in used:
        pid = f"{base}_{n}"
        n += 1
    used.add(pid)
    return pid


def _feature(fid: int, pid: str, name: str, kind: str, nation: str, port: bool, capital: bool, geom, mapping, style, nations, digits: int) -> dict:
    fill, hover = _fills(kind, nation, style, nations)
    geo = mapping(geom)
    geo["coordinates"] = _round_coords(geo["coordinates"], digits)
    return {
        "type": "Feature",
        "id": fid,
        "properties": {
            "id": pid,
            "fid": fid,
            "name": name,
            "kind": kind,
            "nation": nation,
            "port": port,
            "capital": capital,
            "fill": fill,
            "fill_hover": hover,
        },
        "geometry": geo,
    }


def extract() -> Path:
    """下载 Natural Earth 一级政区，只留下 worldmap.yaml 里的国家，写入 source。"""
    shape, _, mapping, box = _shapely()
    recipe = _recipe(CONFIG_DIR)
    countries = {c.upper() for c in recipe["countries"]}
    exclude = {c.upper() for c in (recipe.get("exclude") or [])}
    simplify = float(recipe["simplify"])
    digits = int(recipe["coord_digits"])
    out = _src_file(recipe["source"])
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ne_admin1_") as tmp:
        tmp_path = Path(tmp)
        zpath = tmp_path / "admin1.zip"
        _download_zip(ADMIN1_URL, zpath)
        shp = _extract_shp(zpath, tmp_path, ADMIN1_STEM)
        features = []
        for rec, geo in _records(shp):
            if _iso2(rec) not in countries:
                continue
            if _adm1_iso(rec) in exclude:
                continue
            geom = shape(geo)
            if geom.is_empty:
                continue
            if not geom.is_valid:
                geom = geom.buffer(0)
            geom = geom.simplify(simplify, preserve_topology=True)
            geom = _split_dateline(geom, box)
            if geom is None or geom.is_empty:
                continue
            mapped = mapping(geom)
            mapped["coordinates"] = _round_coords(mapped["coordinates"], digits)
            features.append({
                "type": "Feature",
                "properties": {
                    "iso_a2": _iso2(rec),
                    "iso_3166_2": _adm1_iso(rec),
                    "name": _text(rec, "name_zh", "name", "name_en"),
                },
                "geometry": mapped,
            })
    if not features:
        raise ValueError(f"Natural Earth 里没有这些国家的一级政区：{sorted(countries)}")
    raw = {"type": "FeatureCollection", "features": features}
    out.write_text(json.dumps(raw, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"写入 {out}，{len(features)} 个政区")
    return out


def build(config_dir: Path) -> dict:
    shape, unary_union, mapping, box = _shapely()
    recipe = _recipe(config_dir)
    simplify = float(recipe["simplify"])
    overlap = float(recipe["overlap"])
    digits = int(recipe["coord_digits"])
    default_nation = recipe["default_nation"]
    kinds = recipe["kinds"]
    named = recipe["provinces"]
    exclude = {c.upper() for c in (recipe.get("exclude") or [])}
    style = MapStyleConfig.model_validate(_load_yaml(config_dir / "map.yaml"))
    nations = _load_yaml(config_dir / "nations.yaml")["nations"]
    source = _src_file(recipe["source"])
    if not source.is_file():
        raise FileNotFoundError(f"缺少 {source}，先运行 python -m src.engine.worldmap extract")

    iso_to_named: dict[str, str] = {}
    for pid, spec in named.items():
        raw_iso = spec["iso"]
        codes = [raw_iso] if isinstance(raw_iso, str) else list(raw_iso)
        for code in codes:
            iso_to_named[code.upper()] = pid

    src = json.loads(source.read_text(encoding="utf-8"))
    buckets: dict[str, list] = {pid: [] for pid in named}
    auto: list[tuple[dict, object]] = []
    for feat in src["features"]:
        rec = feat["properties"]
        geom = shape(feat["geometry"])
        if geom.is_empty:
            continue
        code = _adm1_iso(rec)
        if code in exclude:
            continue
        if code in iso_to_named:
            buckets[iso_to_named[code]].append(geom)
            continue
        auto.append((rec, geom))

    missing = [pid for pid, geoms in buckets.items() if not geoms]
    if missing:
        raise ValueError(f"worldmap.yaml 的 iso 在 {source.name} 里找不到：{missing}")

    features = []
    used_ids: set[str] = set(named)
    fid = 1

    for pid, spec in named.items():
        geom = _clean(unary_union(buckets[pid]), simplify, overlap, box)
        if geom is None:
            raise ValueError(f"{pid} 合并后是空几何")
        nation = spec["nation"]
        features.append(_feature(
            fid, pid, spec["name"], kinds[nation], nation,
            bool(spec["port"]), bool(spec["capital"]), geom, mapping, style, nations, digits,
        ))
        fid += 1

    for rec, geom in auto:
        geom = _clean(geom, simplify, overlap, box)
        if geom is None:
            continue
        nation = default_nation
        pid = _slug(rec, used_ids)
        name = _text(rec, "name", "name_en") or pid
        features.append(_feature(
            fid, pid, name, kinds[nation], nation, False, False, geom, mapping, style, nations, digits,
        ))
        fid += 1

    empty = [f["properties"]["id"] for f in features if not f.get("geometry")]
    if empty:
        raise ValueError(f"这些政区没有轮廓：{empty[:12]}")
    _attach_neighbors(features, shape)

    return {
        "type": "FeatureCollection",
        "camera": recipe["camera"],
        "attribution": recipe["attribution"],
        "features": features,
    }


def recolor() -> Path:
    style = MapStyleConfig.model_validate(_load_yaml(CONFIG_DIR / "map.yaml"))
    nations = _load_yaml(CONFIG_DIR / "nations.yaml")["nations"]
    path = map_geojson_path(CONFIG_DIR)
    raw = json.loads(path.read_text(encoding="utf-8"))
    for feat in raw["features"]:
        p = feat["properties"]
        fill, hover = _fills(p["kind"], p["nation"], style, nations)
        p["fill"] = fill
        p["fill_hover"] = hover
    path.write_text(json.dumps(raw, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"重着色 {path}，{len(raw['features'])} 个政区")
    return path


def write() -> Path:
    raw = build(CONFIG_DIR)
    out = map_geojson_path(CONFIG_DIR)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(raw, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"写入 {out}，{len(raw['features'])} 个政区")
    return out


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["recolor"]:
        recolor()
    elif sys.argv[1:] == ["extract"]:
        extract()
        write()
    else:
        write()
