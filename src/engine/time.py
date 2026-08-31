"""回合与译文。引擎只认回合。一回合多长只看 TimeConfig.turns_per_year。"""

from __future__ import annotations

from src.engine.config import TimeConfig


def year_of(time: TimeConfig, turn: int) -> int:
    return time.display_era_year + turn // time.turns_per_year


def unit_of(time: TimeConfig, turn: int) -> int:
    return turn % time.turns_per_year + 1


def format_turn(time: TimeConfig, turn: int) -> str:
    year = year_of(time, turn)
    if time.turns_per_year == 1:
        return f"{year}年"
    return f"{year}年{unit_of(time, turn)}月"


def display_parts(time: TimeConfig, turn: int) -> tuple[int, int, str]:
    return year_of(time, turn), unit_of(time, turn), format_turn(time, turn)
