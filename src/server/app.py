"""HTTP 接口。"""

from __future__ import annotations

import os
import mimetypes
import threading
from pathlib import Path

mimetypes.add_type("text/javascript", ".mjs")

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.agents.advisor import ask_advisor
from src.agents.http import make_provider
from src.engine.army import move_army
from src.engine.briefing import public_view
from src.engine.config import CONFIG_DIR, SRC_ROOT, load_game_data
from src.engine.domestic import do_domestic
from src.engine.events import apply_event_choice
from src.engine.game import GameEngine
from src.engine.save import SaveManager, suggest_save_name
from src.engine.state import NewsItem
from src.engine.time import format_turn

FRONTEND_DIST = SRC_ROOT / "frontend" / "dist"


class NewBody(BaseModel):
    name: str = ""
    country: str
    leader: str
    difficulty: str
    army: int | None = None
    economy: int | None = None
    population: int | None = None
    stability: int | None = None


class LoadBody(BaseModel):
    name: str


class ChoiceBody(BaseModel):
    event_id: str
    option_id: str


class DomesticBody(BaseModel):
    action: str
    province: str | None = None


class MoveBody(BaseModel):
    src: str
    dst: str
    amount: int | None = None


class AdvisorBody(BaseModel):
    question: str


class AdvisorConfigBody(BaseModel):
    provider: str
    api_key: str


def create_app(config_dir: Path | None = None) -> FastAPI:
    data = load_game_data(config_dir or CONFIG_DIR)
    m = data.game.meta
    app = FastAPI(title=f"{m.name} v{m.version}")
    engine = GameEngine(data)
    box: dict = {"state": None, "save": None, "provider": make_provider(data.game.advisor)}
    saves = SaveManager(data.save_db_path(), data.game.save.log_suffix, data.game.time)

    def persist() -> None:
        name = box["save"]
        if not name or box["state"] is None:
            return
        saves.save(box["state"], engine.rng.getstate(), name)

    def view():
        if box["state"] is None:
            raise HTTPException(400, data.ui.err_no_game)
        out = public_view(data, box["state"])
        out["save_name"] = box["save"] or ""
        out["difficulty"] = box["state"].difficulty
        return out

    @app.get("/api/health")
    def health():
        return {"ok": True, "app": "guarantee"}

    @app.get("/api/meta")
    def meta():
        return {
            "name": m.name,
            "version": m.version,
            "player": data.player.short_name,
            "ui": data.ui.model_dump(),
            "setup": {
                "difficulties": [d.model_dump() for d in data.setup.difficulties],
                "default_difficulty": data.setup.default_difficulty,
                "default_country": data.setup.default_country,
                "default_leader": data.setup.default_leader,
                "points_total": data.setup.points_total,
                "army_per_point": data.setup.army_per_point,
                "economy_per_point": data.setup.economy_per_point,
                "population_per_point": data.setup.population_per_point,
                "stability_max": data.game.stat.stability_max,
                "points": data.setup.points.model_dump(),
            },
            "map_style": data.map_style.model_dump(),
            "nations_paint": {
                nid: {"fill": n.fill, "hover": n.fill_hover}
                for nid, n in data.nations.items()
            },
            "date_span": f"{format_turn(data.game.time, data.game.time.start_turn)} – {format_turn(data.game.time, data.game.time.end_turn)}",
        }

    @app.get("/api/state")
    def state():
        return view()

    @app.get("/api/map.geojson")
    def map_geojson():
        return FileResponse(data.map_path, media_type="application/geo+json")

    @app.get("/api/saves")
    def list_saves():
        return saves.list_saves_meta()

    @app.post("/api/new")
    def new_game(body: NewBody):
        try:
            st = engine.new_game(
                body.country,
                body.leader,
                body.difficulty,
                body.army,
                body.economy,
                body.population,
                body.stability,
            )
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        box["state"] = st
        if st.player is None:
            raise RuntimeError("没有玩家")
        who = st.player.short_name
        name = body.name.strip() or suggest_save_name(data.game.save, who)
        box["save"] = name
        persist()
        return {"name": name, "state": view()}

    @app.post("/api/load")
    def load(body: LoadBody):
        try:
            st, rng = saves.load(body.name)
        except FileNotFoundError as e:
            raise HTTPException(404, str(e)) from e
        box["state"] = st
        box["save"] = body.name
        if rng is not None:
            engine.rng.setstate(rng)
        return {"name": body.name, "state": view()}

    @app.post("/api/save")
    def save_now():
        if not box["save"]:
            box["save"] = suggest_save_name(data.game.save, data.player.short_name)
        persist()
        return {"name": box["save"], "state": view()}

    @app.post("/api/delete")
    def delete(body: LoadBody):
        return {"ok": saves.delete(body.name)}

    @app.post("/api/choice")
    def choice(body: ChoiceBody):
        st = box["state"]
        try:
            msgs = apply_event_choice(data, st, body.event_id, body.option_id)
        except KeyError as e:
            raise HTTPException(400, str(e)) from e
        for line in msgs:
            st.archive_line(line)
        persist()
        return {"messages": msgs, "state": view()}

    @app.post("/api/domestic")
    def domestic(body: DomesticBody):
        st = box["state"]
        try:
            msgs = do_domestic(data, st, body.action, body.province)
        except (KeyError, ValueError) as e:
            raise HTTPException(400, str(e)) from e
        for line in msgs:
            st.archive_line(line)
        st.news.append(NewsItem(
            turn=st.turn,
            event_id=f"domestic:{body.action}",
            title=msgs[0],
            text="\n".join(msgs[1:]) if len(msgs) > 1 else msgs[0],
        ))
        persist()
        return {"messages": msgs, "state": view()}

    @app.post("/api/army/move")
    def army_move(body: MoveBody):
        st = box["state"]
        try:
            msgs = move_army(data, st, body.src, body.dst, body.amount)
        except (KeyError, ValueError) as e:
            raise HTTPException(400, str(e)) from e
        for line in msgs:
            st.archive_line(line)
        st.news.append(NewsItem(
            turn=st.turn,
            event_id=f"army:{body.src}:{body.dst}",
            title=msgs[0],
            text=msgs[0],
        ))
        persist()
        return {"messages": msgs, "state": view()}

    @app.post("/api/turn")
    def turn():
        st = box["state"]
        try:
            msgs = engine.advance_turn(st)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        persist()
        return {"messages": msgs, "state": view()}

    @app.post("/api/advisor")
    def advisor(body: AdvisorBody):
        text = ask_advisor(data, box["state"], box["provider"], body.question)
        persist()
        return {"text": text, "state": view()}

    @app.get("/api/advisor/config")
    def advisor_config():
        presets = [
            {
                "id": pid,
                "name": p.name,
                "needs_key": p.needs_key,
                "site": p.site,
            }
            for pid, p in sorted(data.game.advisor.presets.items(), key=lambda kv: kv[1].order)
        ]
        return {"provider": data.game.advisor.provider, "presets": presets}

    @app.post("/api/advisor/config")
    def set_advisor_config(body: AdvisorConfigBody):
        if body.provider not in data.game.advisor.presets:
            raise HTTPException(400, data.ui.err_unknown)
        data.game.advisor.provider = body.provider
        last = data.game.advisor.last_path()
        last.parent.mkdir(parents=True, exist_ok=True)
        last.write_text(yaml.safe_dump({"provider": body.provider}, allow_unicode=True), encoding="utf-8")
        if body.api_key:
            data.game.advisor.presets[body.provider].api_key = body.api_key
            api_dir = data.game.advisor.user_api_dir()
            api_dir.mkdir(parents=True, exist_ok=True)
            (api_dir / f"{body.provider}.yaml").write_text(
                yaml.safe_dump({"api_key": body.api_key}, allow_unicode=True),
                encoding="utf-8",
            )
        box["provider"] = make_provider(data.game.advisor)
        return {"provider": body.provider}

    @app.post("/api/exit")
    def exit_game():
        threading.Timer(0.2, lambda: os._exit(0)).start()
        return {"ok": True}

    index_html = FRONTEND_DIST / "index.html"
    assets_dir = FRONTEND_DIST / "assets"
    if index_html.is_file() and assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/")
        def index():
            return FileResponse(index_html, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})
    else:
        @app.get("/")
        def index():
            return {"message": "前端未构建。请运行 play.bat"}

    return app
