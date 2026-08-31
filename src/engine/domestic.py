"""玩家内政。种类在场景 domestic.yaml。"""

from __future__ import annotations

from src.engine.config import DomesticActionConfig, GameData, UiConfig
from src.engine.effects import apply_effects
from src.engine.state import GameState
from src.engine.stats import fmt_money, spend_money

_STAT = {
    "army": "stat_army",
    "economy": "stat_economy",
    "population": "stat_population",
    "stability": "stat_stability",
}


def tick_cooldowns(state: GameState) -> None:
    dead = [k for k, v in state.cooldowns.items() if v <= 1]
    for k in list(state.cooldowns):
        state.cooldowns[k] -= 1
    for k in dead:
        del state.cooldowns[k]


def action_title(ui: UiConfig, act: DomesticActionConfig) -> str:
    bits = [act.name]
    if act.cost_money:
        shown = fmt_money(act.cost_money)
        bits.append(f"（{ui.stat_money}-{shown}）")
    for e in act.effects:
        t = e["type"]
        if t in _STAT:
            bits.append(f"（{getattr(ui, _STAT[t])}{int(e['delta']):+d}）")
        elif t == "fort":
            bits.append(f"（{ui.place_fort}{int(e['delta']):+d}）")
        elif t == "relation":
            bits.append(f"（{ui.stat_relation}{int(e['delta']):+d}）")
    return "".join(bits)


def province_usable(data: GameData, state: GameState, act: DomesticActionConfig, province_id: str) -> bool:
    if state.provinces[province_id].controller != state.player.id:
        return False
    if act.needs_port and not data.province(province_id).port:
        return False
    return True


def can_afford(state: GameState, act: DomesticActionConfig) -> bool:
    if state.player is None:
        return False
    return state.player.money + 1e-9 >= act.cost_money


def do_domestic(data: GameData, state: GameState, action_id: str, province_id: str | None) -> list[str]:
    words = data.ui
    if state.ended:
        raise ValueError(words.err_ended)
    if state.player is None:
        raise RuntimeError("没有玩家")
    if action_id not in data.domestic:
        raise KeyError(words.err_unknown)
    act = data.domestic[action_id]
    cd_key = action_id
    if act.needs_province and province_id:
        spec = data.province(province_id)
        if act.needs_kind == "foreign":
            cd_key = f"{action_id}:{spec.nation}"
    if cd_key in state.cooldowns:
        raise ValueError(words.err_cooling)
    if not can_afford(state, act):
        raise ValueError(words.err_money)
    if act.needs_province:
        if not province_id:
            raise ValueError(words.err_need_place)
        if not province_usable(data, state, act, province_id):
            raise ValueError(words.err_lost)
    spend_money(state, act.cost_money, words)
    effects = [dict(e) for e in act.effects]
    if act.needs_province and province_id:
        spec = data.province(province_id)
        for e in effects:
            if e["type"] in ("fort", "army", "economy", "population"):
                e["province"] = province_id
            if e["type"] == "relation":
                e["nation"] = spec.nation
    if act.cooldown_days:
        state.cooldowns[cd_key] = act.cooldown_days
    label = action_title(words, act)
    if province_id:
        spec = data.province(province_id)
        if act.needs_kind == "foreign":
            label = f"{label}（{data.nation(spec.nation).short_name}）"
        else:
            label = f"{label}（{spec.name}）"
    msgs = apply_effects(data, state, effects, label, province_id)
    return [label] + msgs
