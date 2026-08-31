"""运行时状态。只存在于内存和存档。"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.engine.flags import FlagState


@dataclass
class PlayerRuntime:
    id: str
    name: str
    short_name: str
    leader: str
    stability: int

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "short_name": self.short_name,
            "leader": self.leader,
            "stability": self.stability,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlayerRuntime":
        return cls(
            id=data["id"],
            name=data["name"],
            short_name=data["short_name"],
            leader=data["leader"],
            stability=int(data["stability"]),
        )


@dataclass
class ProvinceRuntime:
    id: str
    controller: str
    fort: int
    threat: int
    army: int
    economy: int
    population: int

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "controller": self.controller,
            "fort": self.fort,
            "threat": self.threat,
            "army": self.army,
            "economy": self.economy,
            "population": self.population,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProvinceRuntime":
        return cls(
            id=data["id"],
            controller=data["controller"],
            fort=int(data["fort"]),
            threat=int(data["threat"]),
            army=int(data["army"]),
            economy=int(data["economy"]),
            population=int(data["population"]),
        )


@dataclass
class NewsItem:
    turn: int
    event_id: str
    title: str
    text: str

    def to_dict(self) -> dict:
        return {"turn": self.turn, "event_id": self.event_id, "title": self.title, "text": self.text}

    @classmethod
    def from_dict(cls, data: dict) -> "NewsItem":
        return cls(turn=data["turn"], event_id=data["event_id"], title=data["title"], text=data["text"])


@dataclass
class PendingDecision:
    event_id: str
    title: str
    text: str
    options: list[dict]
    turn: int

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "title": self.title,
            "text": self.text,
            "options": list(self.options),
            "turn": self.turn,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PendingDecision":
        return cls(
            event_id=data["event_id"],
            title=data["title"],
            text=data["text"],
            options=list(data["options"]),
            turn=data["turn"],
        )


@dataclass
class ActiveSituation:
    id: str
    title: str
    started_turn: int
    timeout_turns: int | None = None
    progress_current: int = 0
    progress_total: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "started_turn": self.started_turn,
            "timeout_turns": self.timeout_turns,
            "progress_current": self.progress_current,
            "progress_total": self.progress_total,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ActiveSituation":
        return cls(
            id=data["id"],
            title=data["title"],
            started_turn=data["started_turn"],
            timeout_turns=data.get("timeout_turns"),
            progress_current=int(data.get("progress_current") or 0),
            progress_total=int(data.get("progress_total") or 0),
        )


@dataclass
class GameState:
    turn: int = 0
    ended: bool = False
    ending: str = ""
    player: PlayerRuntime | None = None
    provinces: dict[str, ProvinceRuntime] = field(default_factory=dict)
    flags: FlagState = field(default_factory=FlagState)
    news: list[NewsItem] = field(default_factory=list)
    pending: list[PendingDecision] = field(default_factory=list)
    situations: dict[str, ActiveSituation] = field(default_factory=dict)
    fired_events: set[str] = field(default_factory=set)
    event_resolved: set[str] = field(default_factory=set)
    event_armed: dict[str, int] = field(default_factory=dict)
    event_clock: dict[str, int] = field(default_factory=dict)
    cooldowns: dict[str, int] = field(default_factory=dict)
    last_advisor: str = ""
    relations: dict[str, int] = field(default_factory=dict)
    difficulty: str = ""
    log: list[str] = field(default_factory=list)
    archive: list[str] = field(default_factory=list)

    def archive_line(self, line: str) -> None:
        self.archive.append(line)
        self.log.append(line)

    def to_dict(self) -> dict:
        if self.player is None:
            raise RuntimeError("状态没有玩家")
        return {
            "turn": self.turn,
            "ended": self.ended,
            "ending": self.ending,
            "player": self.player.to_dict(),
            "provinces": {k: v.to_dict() for k, v in self.provinces.items()},
            "flags": self.flags.to_dict(),
            "news": [n.to_dict() for n in self.news],
            "pending": [p.to_dict() for p in self.pending],
            "situations": {k: v.to_dict() for k, v in self.situations.items()},
            "fired_events": sorted(self.fired_events),
            "event_resolved": sorted(self.event_resolved),
            "event_armed": dict(self.event_armed),
            "event_clock": dict(self.event_clock),
            "cooldowns": dict(self.cooldowns),
            "last_advisor": self.last_advisor,
            "relations": dict(self.relations),
            "difficulty": self.difficulty,
            "log": list(self.log),
            "archive": list(self.archive),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        st = cls()
        st.turn = data["turn"]
        st.ended = bool(data["ended"])
        st.ending = data.get("ending") or ""
        st.player = PlayerRuntime.from_dict(data["player"])
        st.provinces = {k: ProvinceRuntime.from_dict(v) for k, v in data["provinces"].items()}
        st.flags = FlagState.from_dict(data["flags"])
        st.news = [NewsItem.from_dict(n) for n in data["news"]]
        st.pending = [PendingDecision.from_dict(p) for p in data["pending"]]
        st.situations = {k: ActiveSituation.from_dict(v) for k, v in data["situations"].items()}
        st.fired_events = set(data["fired_events"])
        st.event_resolved = set(data["event_resolved"])
        st.event_armed = dict(data["event_armed"])
        st.event_clock = dict(data["event_clock"])
        st.cooldowns = dict(data["cooldowns"])
        st.last_advisor = data.get("last_advisor") or ""
        st.relations = {k: int(v) for k, v in (data.get("relations") or {}).items()}
        st.difficulty = data["difficulty"]
        st.log = list(data.get("log") or [])
        st.archive = list(data.get("archive") or [])
        return st
