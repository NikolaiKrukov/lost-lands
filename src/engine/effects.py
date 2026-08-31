"""事件与内政的效果。"""

from __future__ import annotations

from src.engine.config import GameData
from src.engine.state import GameState
from src.engine.stats import (
    capital_id,
    clamp_floor,
    clamp_relation,
    clamp_stability,
)

_PROVINCE_STAT = {
    "army": "stat_army",
    "economy": "stat_economy",
    "population": "stat_population",
}


def apply_effects(
    data: GameData,
    state: GameState,
    effects: list[dict],
    desc: str,
    province_id: str | None = None,
) -> list[str]:
    if state.player is None:
        raise RuntimeError("没有玩家")
    msgs: list[str] = []
    p = state.player
    for eff in effects:
        etype = eff["type"]
        if etype == "set_flag":
            flag = eff["flag"]
            owner = None if eff.get("global") else eff.get("nation") or p.id
            state.flags.set_flag(owner, flag)
        elif etype == "clr_flag":
            flag = eff["flag"]
            owner = None if eff.get("global") else eff.get("nation") or p.id
            state.flags.clr_flag(owner, flag)
        elif etype in _PROVINCE_STAT:
            pid = eff.get("province") or province_id or capital_id(data)
            if pid not in state.provinces:
                raise KeyError(f"{desc} 未知政区 {pid}")
            pr = state.provinces[pid]
            if pr.controller != p.id:
                raise ValueError(f"{desc} 只能改本国省份的{_PROVINCE_STAT[etype]}")
            delta = int(eff["delta"])
            setattr(pr, etype, clamp_floor(data, getattr(pr, etype) + delta))
            label = getattr(data.ui, _PROVINCE_STAT[etype])
            msgs.append(f"{data.province(pid).name}{label} {delta:+d}。{desc}。")
        elif etype == "stability":
            delta = int(eff["delta"])
            p.stability = clamp_stability(data, p.stability + delta)
            msgs.append(f"{data.ui.stat_stability} {delta:+d}。{desc}。")
        elif etype == "occupy":
            pid = eff["province"]
            if pid not in state.provinces:
                raise KeyError(f"{desc} 占领未知政区 {pid}")
            state.provinces[pid].controller = eff["controller"]
            name = data.province(pid).name
            who = data.nation(eff["controller"]).short_name
            msgs.append(f"{who}占领{name}。")
        elif etype == "relation":
            nid = eff.get("nation")
            if not nid:
                raise ValueError(f"{desc} relation 必须写 nation")
            if nid not in state.relations:
                raise KeyError(f"{desc} 没有与{nid}的关系")
            delta = int(eff["delta"])
            state.relations[nid] = clamp_relation(data, state.relations[nid] + delta)
            who = data.nation(nid).short_name
            msgs.append(f"对{who}{data.ui.stat_relation} {delta:+d}。{desc}。")
        elif etype == "fort":
            pid = eff.get("province") or province_id
            if not pid:
                raise ValueError(f"{desc} fort 必须写 province")
            if pid not in state.provinces:
                raise KeyError(f"{desc} 未知政区 {pid}")
            if data.province(pid).kind != "home":
                raise ValueError(f"{desc} 只能在本国省份修要塞")
            state.provinces[pid].fort += int(eff["delta"])
            msgs.append(f"{data.province(pid).name}{data.ui.place_fort}{int(eff['delta']):+d}。")
        else:
            raise ValueError(f"{desc} 未知效果 {etype}")
    return msgs
