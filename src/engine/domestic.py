"""玩家内政。种类在场景 domestic.yaml。"""

from __future__ import annotations

from src.engine.config import DomesticActionConfig, GameData, UiConfig
from src.engine.effects import apply_effects
from src.engine.state import GameState
from src.engine.stats import spend_economy, totals

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
    if act.cost_economy:
        bits.append(f"（{ui.stat_economy}-{act.cost_economy}）")
    for e in act.effects:
        t = e["type"]
        if t in _STAT:
            bits.append(f"（{getattr(ui, _STAT[t])}{int(e['delta']):+d}）")
        elif t == "fort":
            bits.append(f"（{ui.place_fort}{int(e['delta']):+d}）")
        elif t == "relation":
            bits.append(f"（{ui.stat_relation}{int(e['delta']):+d}）")
    return "".join(bits)


def action_available(data: GameData, state: GameState, act: DomesticActionConfig, province_id: str | None) -> bool:
    if state.ended or state.player is None:
        return False
    if act.cost_economy > totals(state)[1]:
        return False
    if not act.needs_province:
        return True
    if not province_id:
        return False
    spec = data.province(province_id)
    if act.needs_kind:
        if spec.kind != act.needs_kind:
            return False
        if act.needs_port and not spec.port:
            return False
        if spec.kind == "home" and state.provinces[province_id].controller != state.player.id:
            return False
        return True
    if act.needs_port and not spec.port:
        return False
    return state.provinces[province_id].controller == state.player.id


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
    if totals(state)[1] < act.cost_economy:
        raise ValueError(words.err_money)
    if act.needs_province:
        if not province_id:
            raise ValueError(words.err_need_place)
        spec = data.province(province_id)
        if act.needs_kind:
            if spec.kind != act.needs_kind:
                raise ValueError(words.err_border)
            if act.needs_port and not spec.port:
                raise ValueError(words.err_port)
            if spec.kind == "home" and state.provinces[province_id].controller != state.player.id:
                raise ValueError(words.err_lost)
        else:
            if act.needs_port and not spec.port:
                raise ValueError(words.err_port)
            if state.provinces[province_id].controller != state.player.id:
                raise ValueError(words.err_lost)
    spend_economy(data, state, act.cost_economy, province_id)
    effects = [dict(e) for e in act.effects]
    if act.needs_province and province_id:
        spec = data.province(province_id)
        for e in effects:
            if e["type"] in ("fort", "army", "economy", "population"):
                e["province"] = province_id
            if e["type"] == "relation":
                e["nation"] = spec.nation
    if act.cooldown_turns:
        state.cooldowns[cd_key] = act.cooldown_turns
    label = action_title(words, act)
    if province_id:
        spec = data.province(province_id)
        if act.needs_kind == "foreign":
            label = f"{label}（{data.nation(spec.nation).short_name}）"
        else:
            label = f"{label}（{spec.name}）"
    msgs = apply_effects(data, state, effects, label, province_id)
    return [label] + msgs
