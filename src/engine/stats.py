"""各省合计、扣费、数值上下限。"""

from __future__ import annotations

from src.engine.config import GameData
from src.engine.state import GameState, ProvinceRuntime


def owned_provinces(state: GameState) -> list[ProvinceRuntime]:
    if state.player is None:
        raise RuntimeError("没有玩家")
    return [pr for pr in state.provinces.values() if pr.controller == state.player.id]


def totals(state: GameState) -> tuple[int, int, int]:
    army = economy = population = 0
    for pr in owned_provinces(state):
        army += pr.army
        economy += pr.economy
        population += pr.population
    return army, economy, population


def economy_total(state: GameState) -> int:
    return totals(state)[1]


def capital_id(data: GameData) -> str:
    found = [p.id for p in data.map.provinces if p.capital and p.kind == "home"]
    if len(found) != 1:
        raise ValueError("地图必须恰好有一个本国首都")
    return found[0]


def clamp_floor(data: GameData, value: int) -> int:
    return max(data.game.stat.min, value)


def clamp_stability(data: GameData, value: int) -> int:
    s = data.game.stat
    return max(s.min, min(s.stability_max, value))


def clamp_relation(data: GameData, value: int) -> int:
    s = data.game.stat
    return max(s.min, min(s.relation_max, value))


def spend_money(state: GameState, amount: float, words) -> None:
    if amount <= 0:
        return
    if state.player is None:
        raise RuntimeError("没有玩家")
    if state.player.money + 1e-9 < amount:
        raise ValueError(words.err_money)
    state.player.money -= amount


def monthly_money_income(data: GameData, state: GameState) -> float:
    return economy_total(state) * data.game.stat.money_per_economy


def fmt_army(n: int) -> str:
    return str(n)


def fmt_population(n: int) -> str:
    return str(n)


def fmt_money(n: float) -> str:
    return f"{n:.1f}"
