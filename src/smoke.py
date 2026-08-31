"""框架烟雾。从项目根：python -m src.smoke"""

from __future__ import annotations

import json

from src.engine.army import colonize, demobilize, move_army, recruit
from src.engine.briefing import briefing_text
from src.engine.config import load_game_data
from src.engine.domestic import do_domestic, tick_cooldowns
from src.engine.game import GameEngine
from src.engine.time import format_date, format_turn, year_of


def test_load_and_time() -> None:
    data = load_game_data()
    assert data.game.meta.version == "0.104"
    assert data.player.id == "player"
    assert data.game.stat.stability_max == 50
    assert data.setup.points_total == 50
    pts = data.setup.points
    assert pts.army + pts.economy + pts.population + pts.stability <= 50
    assert data.setup.army_per_point == 100
    assert data.setup.population_per_point == 1000
    assert "levy" not in data.domestic
    assert "railway" not in data.domestic
    assert "militia" not in data.domestic
    assert data.game.time.turns_per_year == 12
    t0 = data.game.time.start_turn
    assert year_of(data.game.time, t0) == 2056
    assert format_turn(data.game.time, t0) == "2056年5月"
    assert format_date(data.game.time, t0, 1) == "2056年5月1日"
    assert data.game.stat.start_money == 50.0
    assert data.game.army.march_cooldown_days == 10
    assert data.game.army.recruit_money_per_army == 0.03
    assert data.game.time.day_tick_ms == 200
    assert data.map_style.hover_lock_ms == 500
    assert data.ui.pause
    assert data.ui.resume
    assert data.ui.stat_army == "军队"
    assert data.ui.stat_money == "杜卡特"
    assert data.ui.map_threat == "威胁地图"
    assert all(a.cooldown_days > 0 for a in data.domestic.values())
    assert data.events == []
    assert {a.category for a in data.domestic.values()} == {"build", "army"}
    assert set(data.nations) == {"player", "world"}
    assert data.nations["player"].player
    assert [d.id for d in data.setup.difficulties] == ["easy", "normal", "hard"]
    assert data.setup.default_difficulty == "normal"
    assert data.setup.default_country == "曙光公社"
    assert data.setup.default_leader == "伊琳娜·生于紫室者"
    assert data.map_style.threat.default == 0
    assert data.map_style.band_at(0).id == "light"
    assert data.map_style.band_at(1).id == "light"
    assert data.map_style.band_at(2).id == "medium"
    assert data.map_style.band_at(4).id == "heavy"
    names = {p.name for p in data.map.provinces}
    ids = {p.id for p in data.map.provinces}
    assert "宾夕法尼亚" in names
    assert "佛罗里达州" in names
    assert "马里兰州" in names
    assert "密苏里州" in names
    assert data.domestic["schools"].name == "增加警察"
    assert "pennsylvania" in ids
    assert "us-hi" not in ids
    assert 50 < len(data.map.provinces) < 90
    assert sum(1 for p in data.map.provinces if p.kind == "home") == 1
    assert {p.nation for p in data.map.provinces if p.kind == "home"} == {"player"}
    pa = data.province("pennsylvania")
    assert pa.neighbors
    geo = json.loads(data.map_path.read_text(encoding="utf-8"))
    for feat in geo["features"]:
        assert feat["properties"]["id"] != "us-hi"
        g = feat["geometry"]
        rings = g["coordinates"] if g["type"] == "Polygon" else [r for poly in g["coordinates"] for r in poly]
        for ring in rings:
            lons = [c[0] for c in ring]
            assert not (min(lons) < -100 and max(lons) > 100), feat["properties"]["id"]


def test_new_setup() -> None:
    data = load_game_data()
    eng = GameEngine(data, seed=1)
    st = eng.new_game("曙光公社", "林安", "normal", 10, 20, 15, 5)
    assert st.turn == data.game.time.start_turn
    assert st.day == 1
    assert st.paused is True
    assert st.player is not None
    assert st.player.name == "曙光公社"
    assert st.player.leader == "林安"
    assert st.player.stability == 5
    assert st.difficulty == "normal"
    cap = st.provinces["pennsylvania"]
    assert cap.controller == "player"
    assert cap.threat == 0
    assert cap.army == 1000
    assert cap.economy == 20
    assert cap.population == 15000
    assert {rt.threat for rt in st.provinces.values()} == {0}
    assert st.relations == {}
    assert st.pending == []
    assert st.player.money == 50.0
    eng.advance_month(st)
    assert st.player.money == 60.0
    do_domestic(data, st, "industry", "pennsylvania")
    assert cap.economy == 22
    assert st.player.money == 56.0
    assert cap.army == 1000
    recruit(data, st, "pennsylvania", 100)
    assert cap.army == 1100
    assert cap.population == 14900
    assert st.player.stability == 5
    assert st.player.money == 53.0
    dest = data.province("pennsylvania").neighbors[0]
    move_army(data, st, "pennsylvania", dest, 500)
    assert st.provinces[dest].controller == data.map_style.unowned_nation
    assert st.provinces[dest].army == 500
    assert cap.army == 600
    for _ in range(data.game.army.march_cooldown_days):
        tick_cooldowns(st)
    move_army(data, st, "pennsylvania", dest, 200)
    assert st.provinces[dest].army == 700
    assert cap.army == 400
    for _ in range(data.game.army.march_cooldown_days):
        tick_cooldowns(st)
    move_army(data, st, "pennsylvania", dest, 400)
    assert st.provinces[dest].army == 1100
    assert cap.army == 0
    colonize(data, st, dest, 1100)
    assert st.provinces[dest].controller == "player"
    assert st.provinces[dest].army == 0
    assert st.provinces[dest].population == 1100
    for _ in range(3):
        eng.advance_turn(st)
    assert st.turn == data.game.time.start_turn + 4
    text = briefing_text(data, st)
    assert "曙光公社" in text
    assert "林安" in text
    assert "宾夕法尼亚" in text
    assert "海军" not in text
    assert "16000" in text
    assert "k" not in text


def test_setup_points_limit() -> None:
    data = load_game_data()
    eng = GameEngine(data, seed=1)
    try:
        eng.new_game("曙光公社", "林安", "normal", 20, 20, 20, 5)
        raise AssertionError("超过总点数应失败")
    except ValueError as e:
        assert str(e) == data.ui.err_setup_points
    try:
        eng.new_game("曙光公社", "林安", "normal", 0, 0, 0, 51)
        raise AssertionError("稳定超过上限应失败")
    except ValueError as e:
        assert str(e) == data.ui.err_setup_stability


def run() -> None:
    test_load_and_time()
    test_new_setup()
    test_setup_points_limit()
    print("smoke ok")


if __name__ == "__main__":
    run()
