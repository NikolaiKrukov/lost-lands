"""事件。约定见 src/rules.md。"""

from __future__ import annotations

from src.engine.config import GameData
from src.engine.effects import apply_effects
from src.engine.rng import GameRNG
from src.engine.state import ActiveSituation, GameState, NewsItem, PendingDecision


def _after_list(ev: dict) -> list[str]:
    raw = ev.get("after") or []
    if isinstance(raw, str):
        return [raw]
    return list(raw)


def _delay_range(ev: dict) -> tuple[int, int] | None:
    raw = ev.get("delay")
    if raw is None:
        return None
    if isinstance(raw, int):
        if raw < 1:
            raise ValueError(f"{ev['id']} delay 必须大于 0")
        return raw, raw
    lo, hi = int(raw["min"]), int(raw["max"])
    return lo, hi


def _at_turn(ev: dict) -> int | None:
    raw = ev.get("at_turn")
    return None if raw is None else int(raw)


def _time_ready(state: GameState, ev: dict) -> bool:
    start = _at_turn(ev)
    if start is None:
        return True
    if ev.get("delay") is not None:
        return state.turn >= start
    return state.turn == start


def _after_ready(state: GameState, ev: dict) -> bool:
    req = _after_list(ev)
    if not req:
        return True
    return all(p in state.event_resolved for p in req)


def _progress_ready(state: GameState, ev: dict) -> bool:
    sid = ev.get("progress_complete")
    if not sid:
        return True
    sit = state.situations.get(sid)
    return bool(sit and sit.progress_total and sit.progress_current >= sit.progress_total)


def _situation_running(state: GameState, ev: dict) -> bool:
    sid = ev.get("situation")
    if not sid:
        return True
    return sid in state.situations


def arm_event(state: GameState, event_id: str) -> None:
    if event_id in state.event_clock or event_id in state.event_armed:
        return
    state.event_armed[event_id] = state.turn


def _try_arm_causal(state: GameState, ev: dict) -> None:
    if _delay_range(ev) is None:
        return
    if not _after_ready(state, ev) or not _progress_ready(state, ev):
        return
    start = _at_turn(ev)
    if start is not None and state.turn < start:
        return
    arm_event(state, ev["id"])


def _delay_due(state: GameState, ev: dict, rng: GameRNG) -> bool:
    if _delay_range(ev) is None:
        return True
    _try_arm_causal(state, ev)
    eid = ev["id"]
    if eid not in state.event_clock:
        if eid not in state.event_armed:
            return False
        lo, hi = _delay_range(ev)
        arm = state.event_armed.pop(eid)
        state.event_clock[eid] = arm + rng.randint(lo, hi)
    return state.turn >= state.event_clock[eid]


def _has_flag_spec(state: GameState, spec: dict) -> bool:
    flag = spec["flag"] if isinstance(spec, dict) else spec
    if isinstance(spec, dict) and spec.get("global"):
        return state.flags.has_flag(None, flag)
    nid = spec.get("nation") if isinstance(spec, dict) else None
    if state.player is None:
        raise RuntimeError("没有玩家")
    return state.flags.has_flag(nid or state.player.id, flag)


def _check_condition(state: GameState, cond: dict) -> bool:
    if not cond:
        return True
    if state.player is None:
        raise RuntimeError("没有玩家")
    p = state.player
    for key in ("army", "economy", "stability"):
        if key not in cond:
            continue
        spec = cond[key]
        val = getattr(p, key)
        if "max" in spec and val > spec["max"]:
            return False
        if "min" in spec and val < spec["min"]:
            return False
    for spec in cond.get("has_flag") or []:
        if isinstance(spec, str):
            spec = {"flag": spec, "global": True}
        if not _has_flag_spec(state, spec):
            return False
    for spec in cond.get("not_has_flag") or []:
        if isinstance(spec, str):
            spec = {"flag": spec, "global": True}
        if _has_flag_spec(state, spec):
            return False
    return True


def _activated(state: GameState, ev: dict) -> bool:
    if not _time_ready(state, ev):
        return False
    if not _after_ready(state, ev):
        return False
    if not _situation_running(state, ev):
        return False
    if not _progress_ready(state, ev):
        return False
    return True


def _eligible(state: GameState, ev: dict, rng: GameRNG) -> bool:
    if ev.get("id") in state.fired_events:
        return False
    if not _activated(state, ev):
        return False
    if not _check_condition(state, ev.get("condition") or {}):
        return False
    if not _delay_due(state, ev, rng):
        return False
    return True


def mark_event_resolved(state: GameState, eid: str) -> None:
    state.event_resolved.add(eid)


def arm_after_dependents(data: GameData, state: GameState, resolved_id: str) -> None:
    for ev in data.events:
        if resolved_id in _after_list(ev):
            _try_arm_causal(state, ev)


def start_initial_situations(data: GameData, state: GameState) -> None:
    for ev in data.events:
        if ev.get("at_start"):
            start_situation(data, state, ev)


def start_situation(data: GameData, state: GameState, ev: dict) -> list[str]:
    sid = ev["id"]
    prog = ev.get("progress") or {}
    timeout = ev.get("timeout_turns")
    state.situations[sid] = ActiveSituation(
        id=sid,
        title=ev.get("title", sid),
        started_turn=state.turn,
        timeout_turns=int(timeout) if timeout is not None else None,
        progress_current=int(prog.get("current") or 0),
        progress_total=int(prog.get("total") or 0),
    )
    mark_event_resolved(state, sid)
    return [f"【局势】{ev.get('title', sid)}开始"]


def tick_situation_progress(state: GameState) -> None:
    for sit in state.situations.values():
        if sit.progress_total:
            sit.progress_current += 1


def _default_option(ev: dict) -> dict:
    opts = ev.get("options") or []
    for o in opts:
        if o.get("default"):
            return o
    return opts[0]


def _fire_one(data: GameData, state: GameState, ev: dict) -> list[str]:
    eid = ev["id"]
    title = ev.get("title", eid)
    text = ev.get("text") or ""
    state.fired_events.add(eid)
    if ev.get("type") in ("situation", "progress"):
        return start_situation(data, state, ev)
    if ev.get("options"):
        state.pending.append(PendingDecision(
            event_id=eid,
            title=title,
            text=text,
            options=[{"id": o["id"], "text": o["text"]} for o in ev["options"]],
            turn=state.turn,
        )
        )
        return [f"桌上多了一件事：{title}"]
    msgs = apply_effects(data, state, ev.get("effects") or [], title)
    mark_event_resolved(state, eid)
    arm_after_dependents(data, state, eid)
    if ev.get("audience") == "world":
        state.news.append(NewsItem(turn=state.turn, event_id=eid, title=title, text=text))
        return [f"报上写：{title}"] + msgs
    return [title] + msgs


def check_and_fire_events(data: GameData, state: GameState, rng: GameRNG) -> list[str]:
    messages: list[str] = []
    for ev in data.events:
        if ev.get("at_start"):
            continue
        if _eligible(state, ev, rng):
            messages.extend(_fire_one(data, state, ev))
    return messages


def apply_event_choice(data: GameData, state: GameState, event_id: str, option_id: str) -> list[str]:
    decision = next((d for d in state.pending if d.event_id == event_id), None)
    if decision is None:
        raise KeyError(f"没有待决 {event_id}")
    ev = data.event(event_id)
    opt = next((o for o in ev["options"] if o["id"] == option_id), None)
    if opt is None:
        raise KeyError(f"{event_id} 没有选项 {option_id}")
    title = ev.get("title", event_id)
    msgs = apply_effects(data, state, opt.get("effects") or [], title)
    state.pending = [d for d in state.pending if d is not decision]
    mark_event_resolved(state, event_id)
    arm_after_dependents(data, state, event_id)
    line = f"{title}——你回了：{opt['text']}"
    return [line] + msgs


def resolve_unanswered(data: GameData, state: GameState) -> list[str]:
    messages: list[str] = []
    for d in list(state.pending):
        ev = data.event(d.event_id)
        opt = _default_option(ev)
        messages.extend(apply_event_choice(data, state, d.event_id, opt["id"]))
    return messages


def apply_situation_timeouts(data: GameData, state: GameState) -> list[str]:
    messages: list[str] = []
    for sid, sit in list(state.situations.items()):
        if sit.timeout_turns is None:
            continue
        if state.turn - sit.started_turn < sit.timeout_turns:
            continue
        ev = data.event(sid)
        opt = ev["timeout_option"]
        messages.extend(apply_effects(data, state, opt.get("effects") or [], sit.title))
        del state.situations[sid]
        messages.append(f"【局势】{sit.title}到期")
    return messages
