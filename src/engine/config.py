"""加载 src/config，组装只读 GameData。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


if frozen():
    SRC_ROOT = Path(sys._MEIPASS) / "src"
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    SRC_ROOT = Path(__file__).resolve().parents[1]
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = SRC_ROOT / "config"


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"缺少配置：{path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        raise ValueError(f"空配置：{path}")
    if not isinstance(raw, dict):
        raise ValueError(f"配置必须是映射：{path}")
    return raw


def map_geojson_path(config_dir: Path | None = None) -> Path:
    d = config_dir or CONFIG_DIR
    recipe = _load_yaml(d / "worldmap.yaml")
    return SRC_ROOT / recipe["output"]


def _load_map(config_dir: Path) -> dict:
    path = map_geojson_path(config_dir)
    if not path.is_file():
        raise FileNotFoundError(f"缺少 {path}，先运行 python -m src.engine.worldmap")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("type") != "FeatureCollection":
        raise ValueError(f"地图必须是 GeoJSON FeatureCollection：{path}")
    provinces = []
    for feat in raw["features"]:
        p = feat["properties"]
        provinces.append({
            "id": p["id"],
            "name": p["name"],
            "kind": p["kind"],
            "port": bool(p["port"]),
            "nation": p["nation"],
            "capital": bool(p["capital"]),
            "neighbors": list(p["neighbors"]),
        })
    return {"provinces": provinces}


class TimeConfig(BaseModel):
    start_turn: int
    end_turn: int
    display_era_year: int
    turns_per_year: int
    days_per_month: int
    day_tick_ms: int


class MetaConfig(BaseModel):
    name: str
    version: str


class ServerConfig(BaseModel):
    host: str
    port: int


class StatConfig(BaseModel):
    min: int
    stability_max: int
    relation_max: int
    money_per_economy: float
    start_money: float


class ArmyConfig(BaseModel):
    march_cooldown_days: int
    recruit_money_per_army: float
    recruit_cooldown_days: int


class UiConfig(BaseModel):
    pause: str
    resume: str
    ask_advisor: str
    ask_placeholder: str
    configure_api: str
    advisor_title: str
    paper_title: str
    stat_army: str
    stat_economy: str
    stat_money: str
    stat_population: str
    stat_stability: str
    stat_relation: str
    menu_continue: str
    menu_save: str
    menu_load: str
    menu_restart: str
    menu_quit: str
    menu_delete: str
    saves_empty: str
    ended_title: str
    ending_intact: str
    ending_occupied: str
    ending_fallen: str
    place_fort: str
    place_ours: str
    place_lost: str
    place_unowned: str
    capital_mark: str
    stat_threat: str
    map_political: str
    map_threat: str
    api_save: str
    category_order: list[str]
    err_prefix: str
    err_ended: str
    err_cooling: str
    err_money: str
    err_need_place: str
    err_border: str
    err_lost: str
    err_unknown: str
    err_port: str
    setup_title: str
    setup_country: str
    setup_leader: str
    setup_difficulty: str
    setup_points: str
    setup_points_left: str
    setup_start: str
    setup_load: str
    err_no_game: str
    err_setup_blank: str
    err_setup_difficulty: str
    err_setup_points: str
    err_setup_stability: str
    err_no_army: str
    err_not_adjacent: str
    err_move_self: str
    err_paused: str
    err_march_amount: str
    err_march_cooling: str
    colonize: str
    demobilize: str
    recruit: str
    err_recruit_cap: str
    march: str


class SaveConfig(BaseModel):
    auto_save_every_turn: bool
    save_dir: str
    db_name: str
    log_suffix: str
    rng_seed: int
    name_prefix: str


class AdvisorPresetConfig(BaseModel):
    name: str
    site: str
    base_url: str
    model: str
    needs_key: bool
    max_retries: int
    temperature: float
    order: int
    api_key: str = ""


class AdvisorConfig(BaseModel):
    settings_dir: str
    api_dir: str
    last_file: str
    provider: str
    prompt: str
    presets: dict[str, AdvisorPresetConfig] = Field(default_factory=dict)

    def default_api_dir(self) -> Path:
        return SRC_ROOT / self.api_dir

    def user_settings_dir(self) -> Path:
        return PROJECT_ROOT / self.settings_dir

    def user_api_dir(self) -> Path:
        return self.user_settings_dir() / "api"

    def last_path(self) -> Path:
        return self.user_settings_dir() / self.last_file


class PlayerConfig(BaseModel):
    id: str
    name: str
    short_name: str
    leader: str


class NationConfig(BaseModel):
    name: str
    short_name: str
    player: bool
    relation: int
    fill: str
    fill_hover: str


class GameConfig(BaseModel):
    meta: MetaConfig
    time: TimeConfig
    server: ServerConfig
    save: SaveConfig
    advisor: AdvisorConfig
    player: PlayerConfig
    stat: StatConfig
    army: ArmyConfig


class ProvinceConfig(BaseModel):
    id: str
    name: str
    kind: str
    port: bool
    nation: str
    capital: bool = False
    neighbors: list[str]


class MapConfig(BaseModel):
    provinces: list[ProvinceConfig]


class DomesticActionConfig(BaseModel):
    name: str
    category: str
    cost_money: float
    cooldown_days: int
    effects: list[dict[str, Any]]
    needs_province: bool
    needs_kind: str
    needs_port: bool


class DifficultyConfig(BaseModel):
    id: str
    name: str


class SetupPointsConfig(BaseModel):
    army: int
    economy: int
    population: int
    stability: int


class SetupConfig(BaseModel):
    difficulties: list[DifficultyConfig]
    default_difficulty: str
    default_country: str
    default_leader: str
    points_total: int
    army_per_point: int
    economy_per_point: int
    population_per_point: int
    points: SetupPointsConfig


class FillPair(BaseModel):
    fill: str
    hover: str


class ThreatBandConfig(BaseModel):
    id: str
    min: int
    max: int
    name: str
    fill: str
    hover: str


class ThreatScaleConfig(BaseModel):
    min: int
    max: int
    default: int
    bands: list[ThreatBandConfig]


class SeamConfig(BaseModel):
    zooms: list[float]
    widths: list[float]


class MapStyleConfig(BaseModel):
    unowned_nation: str
    hover_lock_ms: int
    seam: SeamConfig
    unowned: FillPair
    lost: FillPair
    threat: ThreatScaleConfig

    def band_at(self, value: int) -> ThreatBandConfig:
        for band in self.threat.bands:
            if band.min <= value <= band.max:
                return band
        raise ValueError(f"威胁度 {value} 不在任何区间")


class FlagsFileConfig(BaseModel):
    namespaces: list[str]


class GameData:
    def __init__(
        self,
        game: GameConfig,
        map: MapConfig,
        domestic: dict[str, DomesticActionConfig],
        events: list[dict],
        nations: dict[str, NationConfig],
        flags: FlagsFileConfig,
        ui: UiConfig,
        setup: SetupConfig,
        map_style: MapStyleConfig,
        config_dir: Path,
        map_path: Path,
    ) -> None:
        self.game = game
        self.player = game.player
        self.map = map
        self.domestic = domestic
        self.events = events
        self.nations = nations
        self.flags = flags
        self.ui = ui
        self.setup = setup
        self.map_style = map_style
        self.config_dir = config_dir
        self.map_path = map_path
        self._province = {p.id: p for p in map.provinces}

    def save_db_path(self) -> Path:
        return PROJECT_ROOT / self.game.save.save_dir / self.game.save.db_name

    def nation(self, nid: str) -> NationConfig:
        if nid not in self.nations:
            raise KeyError(f"未知国家 {nid}")
        return self.nations[nid]

    def province(self, pid: str) -> ProvinceConfig:
        if pid not in self._province:
            raise KeyError(f"未知政区 {pid}")
        return self._province[pid]

    def event(self, eid: str) -> dict:
        for ev in self.events:
            if ev["id"] == eid:
                return ev
        raise KeyError(f"未知事件 {eid}")


_FORBIDDEN_EVENT_KEYS = (
    "earliest_year",
    "latest_year",
    "earliest_quarter",
    "latest_quarter",
    "earliest_turn",
    "latest_turn",
    "random_shift",
    "prerequisites",
    "prerequisite_interval",
    "mtth",
    "repeat",
    "deciding_nation",
)


def _after_ids(ev: dict) -> list[str]:
    raw = ev.get("after") or []
    if isinstance(raw, str):
        return [raw]
    return list(raw)


def _parse_turn_field(eid: str, field: str, raw, *, min_allowed: int) -> tuple[int, int]:
    if isinstance(raw, int):
        if raw < min_allowed:
            raise ValueError(f"{eid} {field} 必须 ≥ {min_allowed}")
        return raw, raw
    if isinstance(raw, dict):
        if "min" not in raw or "max" not in raw:
            raise ValueError(f"{eid} {field} 的 min 与 max 必须都写")
        lo, hi = int(raw["min"]), int(raw["max"])
        if lo < min_allowed:
            raise ValueError(f"{eid} {field}.min 必须 ≥ {min_allowed}")
        if hi < lo:
            raise ValueError(f"{eid} {field}.max 不得小于 min")
        if lo == hi:
            raise ValueError(f"{eid} {field} min=max 时请写成 {field}: {lo}")
        return lo, hi
    raise ValueError(f"{eid} {field} 无法解析: {raw!r}")


def _validate_event(ev: dict) -> None:
    eid = ev.get("id", "?")
    if not eid or eid == "?":
        raise ValueError("事件必须写 id")
    for key in _FORBIDDEN_EVENT_KEYS:
        if ev.get(key) is not None:
            raise ValueError(f"{eid} 已取消字段 {key}，见 src/rules.md")
    if ev.get("once") is False:
        raise ValueError(f"{eid} 本版本禁止脉冲")
    if ev.get("delay") is False or ev.get("delay") is True:
        raise ValueError(f"{eid} delay 必须写成数字或 {{min, max}}")
    if ev.get("delay") is not None:
        _parse_turn_field(eid, "delay", ev["delay"], min_allowed=1)
    if ev.get("at_turn") is not None:
        if not isinstance(ev["at_turn"], int) or ev["at_turn"] < 0:
            raise ValueError(f"{eid} at_turn 只写非负整数")

    audience = ev.get("audience")
    if audience not in ("world", "player"):
        raise ValueError(f"{eid} audience 必须是 world 或 player")
    if audience == "world" and ev.get("options"):
        raise ValueError(f"{eid} 世界简报不要写选项")

    at_start = bool(ev.get("at_start"))
    has_at = ev.get("at_turn") is not None
    has_after = bool(_after_ids(ev) or ev.get("progress_complete"))
    has_delay = ev.get("delay") is not None
    calendar = has_at and not has_delay
    causal = has_after or (has_at and has_delay)

    if at_start:
        if has_at or has_after or has_delay:
            raise ValueError(f"{eid} at_start 局势不要再写触发或 delay")
        return
    if ev.get("timeout_turns") is not None:
        if not isinstance(ev["timeout_turns"], int) or ev["timeout_turns"] < 1:
            raise ValueError(f"{eid} timeout_turns 必须是大于 0 的整数")
        if not ev.get("timeout_option"):
            raise ValueError(f"{eid} 写了 timeout_turns 就必须写 timeout_option")

    if not calendar and not causal:
        if ev.get("type") not in ("situation", "progress"):
            raise ValueError(f"{eid} 必须是日历或因果（或 at_start）")
    if has_after and has_at and not has_delay:
        raise ValueError(f"{eid} after/progress_complete 不要再叠日历 at_turn")
    if causal and not has_delay:
        raise ValueError(f"{eid} 因果事件必须写 delay，且 delay > 0")
    if ev.get("type") == "progress":
        prog = ev.get("progress") or {}
        if not prog.get("total"):
            raise ValueError(f"{eid} type: progress 必须写 progress.total")
    if ev.get("type") == "situation" and ev.get("progress"):
        raise ValueError(f"{eid} type: situation 不能写 progress")


def _load_advisor(config_dir: Path) -> AdvisorConfig:
    raw = _load_yaml(config_dir / "advisor.yaml")
    cfg = AdvisorConfig.model_validate(raw)
    default_dir = cfg.default_api_dir()
    if default_dir.is_dir():
        for path in default_dir.glob("*.yaml"):
            pid = path.stem
            if pid in cfg.presets:
                file_raw = _load_yaml(path)
                merged = {**cfg.presets[pid].model_dump(), **file_raw}
                cfg.presets[pid] = AdvisorPresetConfig.model_validate(merged)
    last = cfg.last_path()
    if last.is_file():
        cfg.provider = _load_yaml(last)["provider"]
    user_api = cfg.user_api_dir()
    if user_api.is_dir():
        for path in user_api.glob("*.yaml"):
            pid = path.stem
            file_raw = _load_yaml(path)
            if pid in cfg.presets:
                merged = {**cfg.presets[pid].model_dump(), **file_raw}
                cfg.presets[pid] = AdvisorPresetConfig.model_validate(merged)
    return cfg


def _load_events(config_dir: Path) -> list[dict]:
    folder = config_dir / "events"
    events: list[dict] = []
    seen: set[str] = set()
    for name in ("world.yaml", "player.yaml"):
        raw = _load_yaml(folder / name)
        for ev in raw.get("events") or []:
            _validate_event(ev)
            eid = ev["id"]
            if eid in seen:
                raise ValueError(f"重复事件 id：{eid}")
            seen.add(eid)
            events.append(ev)
    return events


def _validate_map_style(style: MapStyleConfig, nations: dict[str, NationConfig]) -> None:
    if style.unowned_nation not in nations:
        raise ValueError(f"map.yaml unowned_nation 不在 nations.yaml：{style.unowned_nation}")
    if style.hover_lock_ms < 1:
        raise ValueError("map.yaml hover_lock_ms 必须 ≥ 1")
    if len(style.seam.zooms) != len(style.seam.widths) or not style.seam.zooms:
        raise ValueError("map.yaml seam.zooms 与 seam.widths 必须等长且非空")
    t = style.threat
    if t.min > t.max:
        raise ValueError("map.yaml threat.min 不得大于 max")
    if not t.min <= t.default <= t.max:
        raise ValueError("map.yaml threat.default 必须落在 min~max")
    covered: list[int] = []
    seen_id: set[str] = set()
    for band in t.bands:
        if band.id in seen_id:
            raise ValueError(f"重复威胁区间 id：{band.id}")
        seen_id.add(band.id)
        if band.min > band.max:
            raise ValueError(f"威胁区间 {band.id} 的 min 不得大于 max")
        covered.extend(range(band.min, band.max + 1))
    if sorted(covered) != list(range(t.min, t.max + 1)):
        raise ValueError("map.yaml threat.bands 必须覆盖 min~max 且互不重叠")


def load_game_data(config_dir: Path | None = None) -> GameData:
    d = config_dir or CONFIG_DIR
    game_raw = _load_yaml(d / "game.yaml")
    game_raw["save"] = _load_yaml(d / "save.yaml")
    game_raw["advisor"] = _load_advisor(d).model_dump()
    game_cfg = GameConfig.model_validate(game_raw)

    domestic_raw = _load_yaml(d / "domestic.yaml")
    domestic = {
        key: DomesticActionConfig.model_validate(val)
        for key, val in (domestic_raw.get("actions") or {}).items()
    }
    if not domestic:
        raise ValueError("domestic.yaml 必须写 actions")

    ui = UiConfig.model_validate(_load_yaml(d / "ui.yaml"))
    known_cats = set(ui.category_order)
    for aid, act in domestic.items():
        if act.category not in known_cats:
            raise ValueError(f"{aid} category 必须写在 ui.yaml category_order 里")

    for key in ("ending_intact", "ending_occupied", "ending_fallen"):
        if not getattr(ui, key).strip():
            raise ValueError(f"ui.yaml 必须写 {key}")

    nations_raw = _load_yaml(d / "nations.yaml")
    nations = {
        nid: NationConfig.model_validate(val)
        for nid, val in (nations_raw.get("nations") or {}).items()
    }
    players = [nid for nid, n in nations.items() if n.player]
    if len(players) != 1:
        raise ValueError("nations.yaml 必须恰好有一个 player: true")
    if players[0] != game_cfg.player.id:
        raise ValueError(f"玩家 {game_cfg.player.id} 与 nations.yaml 不一致")

    map_path = map_geojson_path(d)
    mmap = MapConfig.model_validate(_load_map(d))
    for spec in mmap.provinces:
        if spec.nation not in nations:
            raise ValueError(f"政区 {spec.id} 的 nation {spec.nation} 不在 nations.yaml")

    setup = SetupConfig.model_validate(_load_yaml(d / "setup.yaml"))
    if len(setup.difficulties) != 3:
        raise ValueError("setup.yaml 必须恰好写三项难度")
    seen_diff = set()
    for item in setup.difficulties:
        if item.id in seen_diff:
            raise ValueError(f"重复难度 id：{item.id}")
        seen_diff.add(item.id)
    if setup.default_difficulty not in seen_diff:
        raise ValueError(f"setup.yaml default_difficulty 必须是已有难度：{setup.default_difficulty}")
    if not setup.default_country.strip() or not setup.default_leader.strip():
        raise ValueError("setup.yaml 必须写 default_country 与 default_leader")
    if game_cfg.stat.money_per_economy <= 0:
        raise ValueError("game.yaml stat.money_per_economy 必须 > 0")
    if game_cfg.stat.start_money < 0:
        raise ValueError("game.yaml stat.start_money 不能为负")
    if game_cfg.army.march_cooldown_days < 1:
        raise ValueError("game.yaml army.march_cooldown_days 必须 ≥ 1")
    if game_cfg.army.recruit_money_per_army <= 0:
        raise ValueError("game.yaml army.recruit_money_per_army 必须 > 0")
    if game_cfg.army.recruit_cooldown_days < 1:
        raise ValueError("game.yaml army.recruit_cooldown_days 必须 ≥ 1")
    if game_cfg.time.days_per_month < 1:
        raise ValueError("game.yaml time.days_per_month 必须 ≥ 1")
    if game_cfg.time.day_tick_ms < 100:
        raise ValueError("game.yaml time.day_tick_ms 必须 ≥ 100")
    if setup.army_per_point < 1 or setup.economy_per_point < 1 or setup.population_per_point < 1:
        raise ValueError("setup.yaml 每点对应数值必须 ≥ 1")
    pts = setup.points
    if min(pts.army, pts.economy, pts.population, pts.stability) < 0:
        raise ValueError("setup.yaml 默认点数不能为负")
    if pts.stability > game_cfg.stat.stability_max:
        raise ValueError("setup.yaml 默认稳定不能超过 stability_max")
    if pts.army + pts.economy + pts.population + pts.stability > setup.points_total:
        raise ValueError("setup.yaml 默认点数之和不能超过 points_total")
    homes = [p for p in mmap.provinces if p.kind == "home"]
    caps = [p for p in homes if p.capital]
    if len(caps) != 1:
        raise ValueError("地图必须恰好有一个本国首都")

    map_style = MapStyleConfig.model_validate(_load_yaml(d / "map.yaml"))
    _validate_map_style(map_style, nations)

    return GameData(
        game=game_cfg,
        map=mmap,
        domestic=domestic,
        events=_load_events(d),
        nations=nations,
        flags=FlagsFileConfig.model_validate(_load_yaml(d / "flags.yaml")),
        ui=ui,
        setup=setup,
        map_style=map_style,
        config_dir=d,
        map_path=map_path,
    )
