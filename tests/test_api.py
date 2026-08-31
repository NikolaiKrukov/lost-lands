from fastapi.testclient import TestClient

from src.server.app import create_app


def test_new_choice_advisor_turn():
    app = create_app()
    c = TestClient(app)
    assert c.get("/api/health").json()["app"] == "guarantee"
    meta = c.get("/api/meta").json()
    assert meta["version"] == "0.104"
    assert meta["ui"]["pause"]
    assert meta["ui"]["resume"]
    assert meta["ui"]["setup_start"]
    assert meta["ui"]["menu_restart"]
    assert meta["ui"]["menu_delete"]
    assert meta["day_tick_ms"] == 200
    assert meta["army"]["recruit_money_per_army"] == 0.03
    assert meta["map_style"]["hover_lock_ms"] == 500
    assert meta["setup"]["default_difficulty"] == "normal"
    assert meta["setup"]["default_country"] == "曙光公社"
    assert meta["setup"]["default_leader"] == "伊琳娜·生于紫室者"
    assert meta["map_style"]["threat"]["default"] == 0
    assert [d["id"] for d in meta["setup"]["difficulties"]] == ["easy", "normal", "hard"]
    assert meta["setup"]["points_total"] == 50
    assert meta["setup"]["stability_max"] == 50
    assert "stat_navy" not in meta["ui"]
    assert meta["ui"]["stat_money"] == "杜卡特"
    assert meta["ui"]["stat_army"] == "军队"
    assert meta["ui"]["colonize"]
    assert meta["ui"]["demobilize"]
    assert meta["ui"]["recruit"] == "扩充陆军"
    assert "changelog" not in meta
    assert c.get("/api/state").status_code == 400
    bad = c.post("/api/new", json={
        "country": "曙光公社",
        "leader": "林安",
        "difficulty": "easy",
        "army": 20,
        "economy": 20,
        "population": 20,
        "stability": 5,
    })
    assert bad.status_code == 400
    st = c.post("/api/new", json={
        "country": "曙光公社",
        "leader": "林安",
        "difficulty": "easy",
        "army": 10,
        "economy": 20,
        "population": 15,
        "stability": 5,
    }).json()["state"]
    assert st["date"] == "2056年5月1日"
    assert st["day"] == 1
    assert st["paused"] is True
    assert st["player"]["id"] == "player"
    assert st["player"]["name"] == "曙光公社"
    assert st["player"]["leader"] == "林安"
    assert st["difficulty"] == "easy"
    assert {p["threat"] for p in st["map"]["provinces"]} == {0}
    assert all(p["threat_band"] == "light" for p in st["map"]["provinces"])
    assert "navy" not in st["player"]
    assert st["player"]["army"] == 1000
    assert st["player"]["economy"] == 20
    assert st["player"]["money"] == 50.0
    assert st["player"]["population"] == 15000
    assert st["player"]["stability"] == 5
    pa = next(p for p in st["map"]["provinces"] if p["id"] == "pennsylvania")
    assert pa["army"] == 1000
    assert pa["economy"] == 20
    assert pa["population"] == 15000
    assert pa["neighbors"]
    assert st["relations"] == {}
    names = {p["name"] for p in st["map"]["provinces"]}
    ids = {p["id"] for p in st["map"]["provinces"]}
    assert "宾夕法尼亚" in names
    assert "pennsylvania" in ids
    assert "us-hi" not in ids
    assert 50 < len(st["map"]["provinces"]) < 90
    assert st["news"] == []
    resumed = c.post("/api/pause", json={"paused": False}).json()["state"]
    assert resumed["paused"] is False
    after_day = c.post("/api/day").json()["state"]
    assert after_day["day"] == 2
    assert after_day["date"] == "2056年5月2日"
    paused = c.post("/api/pause", json={"paused": True}).json()["state"]
    assert paused["paused"] is True
    assert c.post("/api/day").status_code == 400
    after_month = c.post("/api/turn").json()["state"]
    assert after_month["player"]["money"] == 60.0
    r = c.post("/api/domestic", json={"action": "industry", "province": "pennsylvania"})
    assert r.status_code == 200
    after = r.json()["state"]
    assert after["player"]["economy"] == 22
    assert after["player"]["money"] == 56.0
    assert after["player"]["army"] == 1000
    assert after["player"]["population"] == 15000
    cats = {a["category"] for a in st["domestic"]}
    assert cats == {"build", "army"}
    assert all(a["id"] != "militia" for a in st["domestic"])
    assert all(a["id"] != "railway" for a in st["domestic"])
    assert all(a["id"] != "levy" for a in st["domestic"])
    assert all("k" not in a["title"] for a in st["domestic"])
    rec = c.post("/api/army/recruit", json={"province": "pennsylvania", "amount": 100})
    assert rec.status_code == 200
    rec_st = rec.json()["state"]
    assert rec_st["player"]["army"] == 1100
    assert rec_st["player"]["population"] == 14900
    assert rec_st["player"]["money"] == 53.0
    after = rec_st
    dest = pa["neighbors"][0]
    nb = next(p for p in after["map"]["provinces"] if p["id"] == dest)
    assert nb["controller"] == "world"
    moved = c.post("/api/army/move", json={"src": "pennsylvania", "dst": dest, "amount": 500})
    assert moved.status_code == 200
    mv = moved.json()["state"]
    assert mv["player"]["army"] == 600
    took = next(p for p in mv["map"]["provinces"] if p["id"] == dest)
    assert took["controller"] == "world"
    assert took["army"] == 500
    col = c.post("/api/army/colonize", json={"province": dest, "amount": 500})
    assert col.status_code == 200
    col_st = col.json()["state"]
    took2 = next(p for p in col_st["map"]["provinces"] if p["id"] == dest)
    assert took2["controller"] == "player"
    assert took2["army"] == 0
    assert took2["population"] == 500
    demo = c.post("/api/army/demobilize", json={"province": "pennsylvania", "amount": 200})
    assert demo.status_code == 200
    demo_st = demo.json()["state"]
    pa2 = next(p for p in demo_st["map"]["provinces"] if p["id"] == "pennsylvania")
    assert pa2["army"] == 400
    assert pa2["population"] == 15100
    geo = c.get("/api/map.geojson").json()
    assert geo["type"] == "FeatureCollection"
    assert 50 < len(geo["features"]) < 90
    assert geo["camera"]["zoom"]
    assert {f["properties"]["id"] for f in geo["features"]} >= {"pennsylvania"}
    adv = c.post("/api/advisor", json={"question": "要塞应优先加强宾夕法尼亚还是纽约？"}).json()
    assert adv["text"]
    name = c.post("/api/save").json()["name"]
    listed = c.get("/api/saves").json()
    assert any(s["name"] == name for s in listed)
    assert c.post("/api/delete", json={"name": name}).json()["ok"]
    left = {s["name"] for s in c.get("/api/saves").json()}
    assert name not in left
