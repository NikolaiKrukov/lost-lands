from fastapi.testclient import TestClient

from src.server.app import create_app


def test_new_choice_advisor_turn():
    app = create_app()
    c = TestClient(app)
    assert c.get("/api/health").json()["app"] == "guarantee"
    meta = c.get("/api/meta").json()
    assert meta["version"] == "0.103"
    assert meta["ui"]["end_turn"]
    assert meta["ui"]["setup_start"]
    assert meta["ui"]["menu_restart"]
    assert meta["ui"]["menu_delete"]
    assert meta["map_style"]["hover_lock_ms"] == 800
    assert meta["setup"]["default_difficulty"] == "normal"
    assert meta["setup"]["default_country"] == "曙光公社"
    assert meta["setup"]["default_leader"] == "伊琳娜·生于紫室者"
    assert meta["map_style"]["threat"]["default"] == 0
    assert [d["id"] for d in meta["setup"]["difficulties"]] == ["easy", "normal", "hard"]
    assert meta["setup"]["points_total"] == 50
    assert meta["setup"]["stability_max"] == 50
    assert "stat_navy" not in meta["ui"]
    assert meta["ui"]["stat_population"]
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
    assert st["date"] == "2056年5月"
    assert st["player"]["id"] == "player"
    assert st["player"]["name"] == "曙光公社"
    assert st["player"]["leader"] == "林安"
    assert st["difficulty"] == "easy"
    assert {p["threat"] for p in st["map"]["provinces"]} == {0}
    assert all(p["threat_band"] == "light" for p in st["map"]["provinces"])
    assert "navy" not in st["player"]
    assert st["player"]["army"] == 1000
    assert st["player"]["economy"] == 20
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
    r = c.post("/api/domestic", json={"action": "industry", "province": "pennsylvania"})
    assert r.status_code == 200
    after = r.json()["state"]
    assert after["player"]["economy"] == 18
    assert after["player"]["army"] == 1000
    assert after["player"]["population"] == 15000
    cats = {a["category"] for a in st["domestic"]}
    assert cats == {"build", "army"}
    assert all(a["id"] != "militia" for a in st["domestic"])
    levy = next(a for a in st["domestic"] if a["id"] == "levy")
    assert "扩充防卫队" in levy["title"]
    assert "（陆军+100）" in levy["title"]
    assert all("k" not in a["title"] for a in st["domestic"])
    dest = pa["neighbors"][0]
    moved = c.post("/api/army/move", json={"src": "pennsylvania", "dst": dest})
    assert moved.status_code == 200
    mv = moved.json()["state"]
    assert mv["player"]["army"] == 1000
    took = next(p for p in mv["map"]["provinces"] if p["id"] == dest)
    assert took["controller"] == "player"
    assert took["army"] == 1000
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
