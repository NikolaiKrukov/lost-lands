"""军队调动、殖民、裁军、征兵。"""

from __future__ import annotations

from src.engine.config import GameData
from src.engine.state import GameState
from src.engine.stats import clamp_floor, fmt_army, spend_money


def _march_cd_key(src_id: str) -> str:
    return f"march:{src_id}"


def _recruit_cd_key() -> str:
    return "recruit"


def _take_amount(amount: int | None, max_army: int, words) -> int:
    if amount is None or amount < 1:
        raise ValueError(words.err_march_amount)
    if amount > max_army:
        raise ValueError(words.err_no_army)
    return int(amount)


def _take_recruit(amount: int | None, max_n: int, words) -> int:
    if amount is None or amount < 1:
        raise ValueError(words.err_march_amount)
    if amount > max_n:
        raise ValueError(words.err_recruit_cap)
    return int(amount)


def _sync_army_owner(pr, player_id: str) -> None:
    if pr.army <= 0:
        pr.army_owner = ""


def _can_march_from(data: GameData, state: GameState, src_id: str) -> bool:
    src = state.provinces[src_id]
    if src.army <= 0:
        return False
    if src.controller == state.player.id:
        return True
    unowned = data.map_style.unowned_nation
    return src.controller == unowned and src.army_owner == state.player.id


def move_army(
    data: GameData,
    state: GameState,
    src_id: str,
    dst_id: str,
    amount: int | None = None,
) -> list[str]:
    words = data.ui
    if state.ended:
        raise ValueError(words.err_ended)
    if state.player is None:
        raise RuntimeError("没有玩家")
    if src_id == dst_id:
        raise ValueError(words.err_move_self)
    if src_id not in state.provinces or dst_id not in state.provinces:
        raise KeyError(words.err_unknown)
    if not _can_march_from(data, state, src_id):
        raise ValueError(words.err_lost)
    cd_key = _march_cd_key(src_id)
    if cd_key in state.cooldowns:
        raise ValueError(words.err_march_cooling)
    src = state.provinces[src_id]
    dst = state.provinces[dst_id]
    if dst_id not in data.province(src_id).neighbors:
        raise ValueError(words.err_not_adjacent)
    take = _take_amount(amount, src.army, words)
    src_name = data.province(src_id).name
    dst_name = data.province(dst_id).name
    player = state.player.id
    unowned = data.map_style.unowned_nation
    src.army = clamp_floor(data, src.army - take)
    _sync_army_owner(src, player)
    if dst.controller == player:
        dst.army = clamp_floor(data, dst.army + take)
        dst.army_owner = player
        state.cooldowns[cd_key] = data.game.army.march_cooldown_days
        return [f"{fmt_army(take)}从{src_name}调到{dst_name}。"]
    if dst.controller == unowned:
        dst.army = clamp_floor(data, dst.army + take)
        dst.army_owner = player
        state.cooldowns[cd_key] = data.game.army.march_cooldown_days
        return [f"{fmt_army(take)}从{src_name}开进无主地{dst_name}。"]
    atk = take
    dfn = dst.army
    if atk > dfn:
        dst.army = clamp_floor(data, atk - dfn)
        dst.army_owner = player
        dst.controller = player
        state.cooldowns[cd_key] = data.game.army.march_cooldown_days
        if dfn:
            return [f"从{src_name}开进{dst_name}，打垮{fmt_army(dfn)}，占领该省，余{fmt_army(dst.army)}。"]
        return [f"从{src_name}开进{dst_name}，占领该省。"]
    dst.army = clamp_floor(data, dfn - atk)
    _sync_army_owner(dst, player)
    state.cooldowns[cd_key] = data.game.army.march_cooldown_days
    if atk == dfn:
        return [f"从{src_name}进攻{dst_name}，双方打光，未能占领。"]
    return [f"从{src_name}进攻{dst_name}失败，守军余{fmt_army(dst.army)}。"]


def colonize(data: GameData, state: GameState, province_id: str, amount: int | None) -> list[str]:
    words = data.ui
    if state.ended:
        raise ValueError(words.err_ended)
    if state.player is None:
        raise RuntimeError("没有玩家")
    pr = state.provinces[province_id]
    unowned = data.map_style.unowned_nation
    if pr.controller != unowned or pr.army_owner != state.player.id:
        raise ValueError(words.err_border)
    take = _take_amount(amount, pr.army, words)
    name = data.province(province_id).name
    pr.army = clamp_floor(data, pr.army - take)
    _sync_army_owner(pr, state.player.id)
    pr.population = clamp_floor(data, pr.population + take)
    pr.controller = state.player.id
    if pr.army > 0:
        pr.army_owner = state.player.id
    return [f"在{name}殖民，{fmt_army(take)}转为人口，该省归我方。"]


def demobilize(data: GameData, state: GameState, province_id: str, amount: int | None) -> list[str]:
    words = data.ui
    if state.ended:
        raise ValueError(words.err_ended)
    if state.player is None:
        raise RuntimeError("没有玩家")
    pr = state.provinces[province_id]
    if pr.controller != state.player.id:
        raise ValueError(words.err_lost)
    take = _take_amount(amount, pr.army, words)
    name = data.province(province_id).name
    pr.army = clamp_floor(data, pr.army - take)
    _sync_army_owner(pr, state.player.id)
    pr.population = clamp_floor(data, pr.population + take)
    return [f"{name}裁军{fmt_army(take)}，转为人口。"]


def recruit(data: GameData, state: GameState, province_id: str, amount: int | None) -> list[str]:
    words = data.ui
    if state.ended:
        raise ValueError(words.err_ended)
    if state.player is None:
        raise RuntimeError("没有玩家")
    pr = state.provinces[province_id]
    if pr.controller != state.player.id:
        raise ValueError(words.err_lost)
    cd_key = _recruit_cd_key()
    if cd_key in state.cooldowns:
        raise ValueError(words.err_cooling)
    cap = pr.population // 2
    take = _take_recruit(amount, cap, words)
    cost = take * data.game.army.recruit_money_per_army
    spend_money(state, cost, words)
    name = data.province(province_id).name
    pr.army = clamp_floor(data, pr.army + take)
    pr.army_owner = state.player.id
    pr.population = clamp_floor(data, pr.population - take)
    state.cooldowns[cd_key] = data.game.army.recruit_cooldown_days
    return [f"{name}扩充陆军{fmt_army(take)}，人口-{fmt_army(take)}。"]
