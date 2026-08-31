"""开局与推进。advance_month 加月；advance_day 按日推进并触发月度结算。"""

from __future__ import annotations

from src.engine.config import GameData, SetupPointsConfig
from src.engine.domestic import tick_cooldowns
from src.engine.events import resolve_unanswered
from src.engine.rng import GameRNG
from src.engine.state import GameState, PlayerRuntime, ProvinceRuntime
from src.engine.stats import capital_id, economy_total, fmt_money, monthly_money_income
from src.engine.time import format_date


def _alloc_points(
    data: GameData,
    army: int | None,
    economy: int | None,
    population: int | None,
    stability: int | None,
) -> SetupPointsConfig:
    setup = data.setup
    given = (army, economy, population, stability)
    if all(v is None for v in given):
        return setup.points
    a, e, pop, stb = given
    if a is None or e is None or pop is None or stb is None:
        raise ValueError(data.ui.err_setup_points)
    pts = SetupPointsConfig(army=a, economy=e, population=pop, stability=stb)
    if min(pts.army, pts.economy, pts.population, pts.stability) < 0:
        raise ValueError(data.ui.err_setup_points)
    if pts.stability > data.game.stat.stability_max:
        raise ValueError(data.ui.err_setup_stability)
    if pts.army + pts.economy + pts.population + pts.stability > setup.points_total:
        raise ValueError(data.ui.err_setup_points)
    return pts


def new_game(
    data: GameData,
    country: str,
    leader: str,
    difficulty: str,
    army: int | None = None,
    economy: int | None = None,
    population: int | None = None,
    stability: int | None = None,
) -> GameState:
    country = country.strip()
    leader = leader.strip()
    if not country or not leader:
        raise ValueError(data.ui.err_setup_blank)
    if difficulty not in {d.id for d in data.setup.difficulties}:
        raise ValueError(data.ui.err_setup_difficulty)
    pts = _alloc_points(data, army, economy, population, stability)
    cfg = data.game
    pl = data.player
    cap = capital_id(data)
    state = GameState()
    state.turn = cfg.time.start_turn
    state.day = 1
    state.paused = True
    state.difficulty = difficulty
    state.player = PlayerRuntime(
        id=pl.id,
        name=country,
        short_name=country,
        leader=leader,
        stability=pts.stability,
        money=cfg.stat.start_money,
    )
    state.relations = {
        nid: n.relation
        for nid, n in data.nations.items()
        if not n.player and n.relation != 0
    }
    for spec in data.map.provinces:
        controller = spec.nation if spec.kind != "home" else pl.id
        army_n = economy_n = population_n = 0
        if spec.id == cap:
            army_n = pts.army * data.setup.army_per_point
            economy_n = pts.economy * data.setup.economy_per_point
            population_n = pts.population * data.setup.population_per_point
        state.provinces[spec.id] = ProvinceRuntime(
            id=spec.id,
            controller=controller,
            fort=0,
            threat=data.map_style.threat.default,
            army=army_n,
            army_owner=pl.id if army_n > 0 else "",
            economy=economy_n,
            population=population_n,
        )
    date = format_date(cfg.time, state.turn, state.day)
    state.archive_line(f"{date} {country}，{leader}。")
    return state


def _maybe_end(data: GameData, state: GameState) -> None:
    if state.turn <= data.game.time.end_turn:
        return
    state.ended = True
    state.paused = True
    occupied = [
        pid for pid, pr in state.provinces.items()
        if data.province(pid).kind == "home" and pr.controller != data.player.id
    ]
    home_kept = [
        pid for pid, pr in state.provinces.items()
        if data.province(pid).kind == "home" and pr.controller == data.player.id
    ]
    if not occupied:
        state.ending = data.ui.ending_intact
    elif home_kept:
        state.ending = data.ui.ending_occupied
    else:
        state.ending = data.ui.ending_fallen


class GameEngine:
    def __init__(self, data: GameData, seed: int | None = None) -> None:
        self.data = data
        self.rng = GameRNG(seed if seed is not None else data.game.save.rng_seed)

    def new_game(
        self,
        country: str,
        leader: str,
        difficulty: str,
        army: int | None = None,
        economy: int | None = None,
        population: int | None = None,
        stability: int | None = None,
    ) -> GameState:
        return new_game(self.data, country, leader, difficulty, army, economy, population, stability)

    def advance_month(self, state: GameState) -> list[str]:
        if state.ended:
            raise ValueError(self.data.ui.err_ended)
        messages = resolve_unanswered(self.data, state)
        if state.player is not None:
            gain = monthly_money_income(self.data, state)
            state.player.money += gain
            if gain:
                messages.append(f"{self.data.ui.stat_money}+{fmt_money(gain)}。")
        state.turn += 1
        _maybe_end(self.data, state)
        if state.ended:
            state.archive_line(state.ending)
        return messages

    def advance_day(self, state: GameState) -> list[str]:
        if state.ended:
            raise ValueError(self.data.ui.err_ended)
        if state.paused:
            raise ValueError(self.data.ui.err_paused)
        tick_cooldowns(state)
        t = self.data.game.time
        state.day += 1
        if state.day > t.days_per_month:
            state.day = 1
            return self.advance_month(state)
        return []

    def advance_turn(self, state: GameState) -> list[str]:
        """兼容测试：一次推进一整月。"""
        tick_cooldowns(state)
        state.day = 1
        return self.advance_month(state)
