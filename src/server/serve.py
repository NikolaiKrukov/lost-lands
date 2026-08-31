"""启动。默认 8010，不要占 Game1 的 8000。

Windows 下默认弹出控制窗口，关掉窗口即结束服务。
"""

from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path

import uvicorn

from src.engine.config import CONFIG_DIR, load_game_data
from src.server.app import FRONTEND_DIST, create_app

FRONTEND_DIR = FRONTEND_DIST.parent


def _frontend_source_newer(index: Path) -> bool:
    src = FRONTEND_DIR / "src"
    newest = max((p.stat().st_mtime for p in src.rglob("*") if p.is_file()), default=0)
    return newest > index.stat().st_mtime


def ensure_frontend(rebuild: bool = False) -> None:
    from src.engine.config import frozen

    index = FRONTEND_DIST / "index.html"
    if frozen():
        if not index.is_file():
            raise SystemExit("打包内容缺少前端 dist")
        return
    if index.is_file() and not rebuild and not _frontend_source_newer(index):
        return
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        raise SystemExit("未找到 npm，无法构建前端。请先安装 Node.js。")
    if not (FRONTEND_DIR / "node_modules").is_dir():
        print("正在安装前端依赖…")
        subprocess.run([npm, "install"], cwd=FRONTEND_DIR, check=True)
    print("正在构建前端…")
    subprocess.run([npm, "run", "build"], cwd=FRONTEND_DIR, check=True)
    if not index.is_file():
        raise SystemExit("前端构建失败")


def port_taken(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) == 0


def _parse_args(host: str, default_port: int) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="失落之地")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--host", type=str, default=host)
    parser.add_argument("--port", type=int, default=default_port)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--console", action="store_true", help="不用控制窗口，在当前终端运行")
    parser.add_argument("--window", action="store_true", help="强制使用控制窗口")
    return parser.parse_args()


def run_console(args: argparse.Namespace) -> None:
    from src.server.launcher import take_port, write_pid_file

    host = args.host
    port = args.port
    url = f"http://{host}:{port}"
    state = take_port(host, port)
    if state == "already":
        print(f"游戏已在运行：{url}")
        if not args.no_browser:
            webbrowser.open(url)
        return
    if state == "busy":
        raise SystemExit(
            f"端口 {port} 被其他程序占用，没有结束他人进程。"
        )

    ensure_frontend(rebuild=args.rebuild)
    app = create_app(args.config or CONFIG_DIR)

    @app.on_event("startup")
    def _open() -> None:
        print(f"已启动：{url}")
        if not args.no_browser:
            webbrowser.open(url)

    write_pid_file()
    uvicorn.run(app, host=host, port=port)


def main() -> None:
    data = load_game_data(CONFIG_DIR)
    args = _parse_args(data.game.server.host, data.game.server.port)
    use_window = args.window or (sys.platform == "win32" and not args.console)
    if args.console:
        use_window = False
    if use_window:
        from src.server.launcher import run_window
        run_window(args)
        return
    run_console(args)


if __name__ == "__main__":
    main()
