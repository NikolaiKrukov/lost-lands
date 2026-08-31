"""给界面和顾问的同一份情报。"""

from __future__ import annotations

from src.engine.config import GameData
from src.engine.domestic import action_title
from src.engine.state import GameState
from src.engine.stats import fmt_army, fmt_population, totals
from src.engine.time import format_turn


def public_view(data: GameData, state: GameState) -> dict:
    if state.player is None:
        raise RuntimeError("没有玩家")
    p = state.player
    army, economy, population = totals(state)
    provinces = []
    for spec in data.map.provinces:
        rt = state.provinces[spec.id]
        nat = data.nation(spec.nation)
        band = data.map_style.band_at(rt.threat)
        provinces.append({
            "id": spec.id,
            "name": spec.name,
            "kind": spec.kind,
            "capital": spec.capital,
            "nation": spec.nation,
            "nation_name": nat.short_name,
            "port": spec.port,
            "controller": rt.controller,
            "controller_name": data.nation(rt.controller).short_name if rt.controller in data.nations else rt.controller,
            "fort": rt.fort,
            "threat": rt.threat,
            "threat_band": band.id,
            "threat_band_name": band.name,
            "relation": state.relations.get(spec.nation),
            "army": rt.army,
            "economy": rt.economy,
            "population": rt.population,
            "neighbors": list(spec.neighbors),
        })
    player = p.to_dict()
    player.update(army=army, economy=economy, population=population)
    return {
        "turn": state.turn,
        "date": format_turn(data.game.time, state.turn),
        "ended": state.ended,
        "ending": state.ending,
        "player": player,
        "difficulty": state.difficulty,
        "relations": {
            nid: {"name": data.nation(nid).short_name, "value": val}
            for nid, val in state.relations.items()
        },
        "map": {
            "provinces": provinces,
        },
        "news": [n.to_dict() for n in state.news[-16:]],
        "pending": [d.to_dict() for d in state.pending],
        "situations": [s.to_dict() for s in state.situations.values()],
        "cooldowns": dict(state.cooldowns),
        "last_advisor": state.last_advisor,
        "domestic": [
            {
                "id": aid,
                "name": a.name,
                "title": action_title(data.ui, a),
                "category": a.category,
                "cost_economy": a.cost_economy,
                "needs_province": a.needs_province,
                "needs_kind": a.needs_kind,
                "needs_port": a.needs_port,
                "effects": list(a.effects),
            }
            for aid, a in data.domestic.items()
        ],
        "flags": sorted(state.flags.global_flags),
    }


def briefing_text(data: GameData, state: GameState, question: str = "") -> str:
    view = public_view(data, state)
    p = view["player"]
    u = data.ui
    lines = [
        f"现在是{view['date']}。",
        f"你在{p['name']}。领袖是{p['leader']}。",
        (
            f"{u.stat_army} {fmt_army(p['army'])}，{u.stat_economy} {p['economy']}，"
            f"{u.stat_population} {fmt_population(p['population'])}，{u.stat_stability} {p['stability']}。"
        ),
    ]
    if view["relations"]:
        lines.append("与各国关系：")
    for item in view["relations"].values():
        lines.append(f"- {item['name']} {u.stat_relation} {item['value']}")
    lines.append("本国各省：")
    for pr in view["map"]["provinces"]:
        if pr["kind"] != "home":
            continue
        extra = f"，{u.place_fort}{pr['fort']}" if pr["fort"] else ""
        stats = (
            f"{u.stat_army} {fmt_army(pr['army'])}，{u.stat_economy} {pr['economy']}，"
            f"{u.stat_population} {fmt_population(pr['population'])}"
        )
        if pr["controller"] == p["id"]:
            lines.append(f"- {pr['name']}：{u.place_ours}，{stats}{extra}")
        else:
            lines.append(f"- {pr['name']}：{u.place_lost}（{pr['controller_name']}）{extra}")
    if view["pending"]:
        lines.append("待决事项：")
        for d in view["pending"]:
            lines.append(f"- {d['title']}：{d['text']}")
    if view["news"]:
        lines.append("近期要闻：")
        for n in view["news"][-5:]:
            lines.append(f"- {n['title']}：{n['text']}")
    if view["ended"]:
        lines.append(view["ending"])
    if question:
        lines.append(f"现在要求你判断：{question}")
    return "\n".join(lines)
