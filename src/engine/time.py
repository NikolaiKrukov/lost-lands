"""回合与译文。引擎只认回合（月）；日用于暂停推进与按日冷却。"""

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


def format_date(time: TimeConfig, turn: int, day: int) -> str:
    if time.days_per_month <= 1:
        return format_turn(time, turn)
    return f"{format_turn(time, turn)}{day}日"


def display_parts(time: TimeConfig, turn: int, day: int) -> tuple[int, int, int, str]:
    return year_of(time, turn), unit_of(time, turn), day, format_date(time, turn, day)
