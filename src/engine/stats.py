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


def spend_economy(data: GameData, state: GameState, amount: int, prefer_id: str | None) -> None:
    if amount == 0:
        return
    owned = owned_provinces(state)
    if sum(p.economy for p in owned) < amount:
        raise ValueError(data.ui.err_money)
    remaining = amount
    order: list[ProvinceRuntime] = []
    if prefer_id is not None and state.provinces[prefer_id].controller == state.player.id:
        order.append(state.provinces[prefer_id])
    for p in owned:
        if p not in order:
            order.append(p)
    for p in order:
        take = min(p.economy, remaining)
        p.economy -= take
        remaining -= take
        if remaining == 0:
            return
    raise RuntimeError("扣费未扣完")


def fmt_army(n: int) -> str:
    return str(n)


def fmt_population(n: int) -> str:
    return str(n)
