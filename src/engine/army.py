"""陆军在省份之间调动，打得过就占领。规则按《文明时代》：邻省开进、兵力相加或对打。"""

from __future__ import annotations

from src.engine.config import GameData
from src.engine.state import GameState
from src.engine.stats import clamp_floor, fmt_army


def move_army(data: GameData, state: GameState, src_id: str, dst_id: str, amount: int | None = None) -> list[str]:
    words = data.ui
    if state.ended:
        raise ValueError(words.err_ended)
    if state.player is None:
        raise RuntimeError("没有玩家")
    if src_id == dst_id:
        raise ValueError(words.err_move_self)
    if src_id not in state.provinces or dst_id not in state.provinces:
        raise KeyError(words.err_unknown)
    src = state.provinces[src_id]
    dst = state.provinces[dst_id]
    if src.controller != state.player.id:
        raise ValueError(words.err_lost)
    if src.army <= 0:
        raise ValueError(words.err_no_army)
    if dst_id not in data.province(src_id).neighbors:
        raise ValueError(words.err_not_adjacent)
    take = src.army if amount is None else int(amount)
    if take < 1 or take > src.army:
        raise ValueError(words.err_no_army)
    src_name = data.province(src_id).name
    dst_name = data.province(dst_id).name
    src.army = clamp_floor(data, src.army - take)
    if dst.controller == state.player.id:
        dst.army = clamp_floor(data, dst.army + take)
        return [f"{fmt_army(take)}从{src_name}调到{dst_name}。"]
    atk = take
    dfn = dst.army
    if atk > dfn:
        dst.army = clamp_floor(data, atk - dfn)
        dst.controller = state.player.id
        if dfn:
            return [f"从{src_name}开进{dst_name}，打垮{fmt_army(dfn)}，占领该省，余{fmt_army(dst.army)}。"]
        return [f"从{src_name}开进{dst_name}，占领该省。"]
    dst.army = clamp_floor(data, dfn - atk)
    if atk == dfn:
        return [f"从{src_name}进攻{dst_name}，双方打光，未能占领。"]
    return [f"从{src_name}进攻{dst_name}失败，守军余{fmt_army(dst.army)}。"]
