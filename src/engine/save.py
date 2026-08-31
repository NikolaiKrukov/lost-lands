"""SQLite 存档。"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from src.engine.config import SaveConfig, TimeConfig
from src.engine.state import GameState
from src.engine.time import display_parts, format_date, format_turn


def suggest_save_name(save: SaveConfig, who: str, when: datetime | None = None) -> str:
    now = when or datetime.now()
    stamp = f"{now.month:02d}{now.day:02d}-{now.hour:02d}{now.minute:02d}"
    return f"{save.name_prefix}_{who}_{stamp}"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS saves (
    name        TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    turn        INTEGER,
    year        INTEGER,
    state_json  TEXT NOT NULL,
    rng_state   TEXT
);
"""


def _to_tuple(obj):
    if isinstance(obj, list):
        return tuple(_to_tuple(x) for x in obj)
    if isinstance(obj, tuple):
        return tuple(_to_tuple(x) for x in obj)
    if isinstance(obj, dict):
        return {k: _to_tuple(v) for k, v in obj.items()}
    return obj


class SaveManager:
    def __init__(self, db_path: Path | str, log_suffix: str, time: TimeConfig) -> None:
        self.db_path = Path(db_path)
        self.log_suffix = log_suffix
        self.time = time
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._lock, self._conn() as conn:
            conn.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.execute("PRAGMA journal_mode=DELETE")
        return conn

    def save(self, state: GameState, rng_state: tuple, name: str) -> None:
        data = state.to_dict()
        data["rng_state"] = list(rng_state) if rng_state else None
        state_json = json.dumps(data, ensure_ascii=False)
        rng_text = json.dumps(data["rng_state"]) if data["rng_state"] is not None else None
        now = datetime.now().isoformat(timespec="seconds")
        year, _, _, _ = display_parts(self.time, state.turn, state.day)
        with self._lock, self._conn() as conn:
            conn.execute(
                """INSERT INTO saves (name, created_at, updated_at, turn, year, state_json, rng_state)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET
                     updated_at=excluded.updated_at,
                     turn=excluded.turn, year=excluded.year,
                     state_json=excluded.state_json, rng_state=excluded.rng_state""",
                (name, now, now, state.turn, year, state_json, rng_text),
            )
        self.write_log(name, state)

    def log_path(self, name: str) -> Path:
        return self.db_path.parent / f"{name}{self.log_suffix}"

    def write_log(self, name: str, state: GameState) -> None:
        ended = "已终局" if state.ended else "进行中"
        parts = [
            f"======== 对局日志：{name} ========",
            f"{format_date(self.time, state.turn, state.day)}｜{ended}",
            "",
            "======== 对局记录 ========",
        ]
        parts.extend(state.archive or ["（尚无记录）"])
        parts.append("")
        self.log_path(name).write_text("\n".join(parts), encoding="utf-8")

    def load(self, name: str) -> tuple[GameState, tuple | None]:
        with self._lock, self._conn() as conn:
            row = conn.execute("SELECT state_json FROM saves WHERE name = ?", (name,)).fetchone()
        if row is None:
            raise FileNotFoundError(f"存档不存在: {name}")
        data = json.loads(row[0])
        rng_raw = data.pop("rng_state", None)
        rng_state = _to_tuple(rng_raw) if rng_raw else None
        return GameState.from_dict(data), rng_state

    def list_saves_meta(self) -> list[dict]:
        with self._lock, self._conn() as conn:
            rows = conn.execute(
                "SELECT name, turn, year FROM saves ORDER BY updated_at DESC"
            ).fetchall()
        out = []
        for r in rows:
            turn = r[1] if r[1] is not None else 0
            year, _, _, date = display_parts(self.time, turn, 1)
            out.append({"name": r[0], "turn": turn, "year": r[2] if r[2] is not None else year, "date": date})
        return out

    def delete(self, name: str) -> bool:
        with self._lock, self._conn() as conn:
            cur = conn.execute("DELETE FROM saves WHERE name = ?", (name,))
            ok = cur.rowcount > 0
        log = self.log_path(name)
        if log.is_file():
            log.unlink()
        return ok
