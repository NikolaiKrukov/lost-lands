"""Windows 控制窗口：关掉窗口即结束本进程及子进程。"""

from __future__ import annotations

import atexit
import ctypes
import os
import queue
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from src.engine.config import PROJECT_ROOT, frozen

PID_FILE = PROJECT_ROOT / "saves" / "server.pid"

_JOB_HANDLE = None


def write_pid_file() -> None:
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    atexit.register(clear_pid_file)


def clear_pid_file() -> None:
    if PID_FILE.is_file():
        PID_FILE.unlink()


def read_pid_file() -> int | None:
    if not PID_FILE.is_file():
        return None
    text = PID_FILE.read_text(encoding="utf-8").strip()
    return int(text) if text.isdigit() else None


def is_our_process(cmdline: str, project_root: Path | None = None) -> bool:
    if not cmdline:
        return False
    root = str((project_root or PROJECT_ROOT).resolve()).replace("/", "\\").lower()
    cl = cmdline.replace("/", "\\").lower()
    if root in cl:
        return True
    compact = " ".join(cl.split())
    if frozen():
        return Path(sys.executable).name.lower() in compact
    if "-m src" in compact or "src.server" in compact:
        return True
    name = (project_root or PROJECT_ROOT).name.lower()
    return name in compact


def health_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/health", timeout=0.8) as r:
            return 200 <= r.status < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def listen_pids(port: int) -> list[int]:
    r = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True)
    text = r.stdout.decode("mbcs", errors="replace")
    pids: set[int] = set()
    for line in text.splitlines():
        if "LISTENING" not in line.upper() and "侦听" not in line:
            continue
        parts = line.split()
        if len(parts) < 4 or not parts[-1].isdigit():
            continue
        local = parts[1] if parts[0].upper() == "TCP" else parts[0]
        if local.rsplit(":", 1)[-1] == str(port):
            pids.add(int(parts[-1]))
    return sorted(pids)


def process_cmdline(pid: int) -> str:
    r = subprocess.run(
        [
            "powershell", "-NoProfile", "-Command",
            f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}').CommandLine",
        ],
        capture_output=True, text=True, timeout=8,
    )
    return (r.stdout or "").strip()


def process_name(pid: int) -> str:
    r = subprocess.run(
        [
            "powershell", "-NoProfile", "-Command",
            f"(Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue).ProcessName",
        ],
        capture_output=True, text=True, timeout=8,
    )
    return (r.stdout or "").strip()


def kill_pid_tree(pid: int) -> None:
    if pid <= 0 or pid == os.getpid():
        return
    subprocess.run(
        ["taskkill", "/F", "/T", "/PID", str(pid)],
        capture_output=True, check=False,
    )


def kill_own_listeners(port: int) -> None:
    for pid in listen_pids(port):
        if pid == os.getpid():
            continue
        if is_our_process(process_cmdline(pid)):
            kill_pid_tree(pid)


def attach_kill_on_close_job() -> None:
    global _JOB_HANDLE
    if sys.platform != "win32" or _JOB_HANDLE is not None:
        return
    k32 = ctypes.windll.kernel32

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", ctypes.c_uint32),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", ctypes.c_uint32),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", ctypes.c_uint32),
            ("SchedulingClass", ctypes.c_uint32),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    job = k32.CreateJobObjectW(None, None)
    if not job:
        return
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = 0x2000
    if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
        return
    if not k32.AssignProcessToJobObject(job, k32.GetCurrentProcess()):
        return
    _JOB_HANDLE = job


def take_port(host: str, port: int, project_root: Path | None = None) -> str:
    """ok / already / busy。already=本项目服务已在跑；busy=别人占用，不杀。"""
    from src.server.serve import port_taken

    root = project_root or PROJECT_ROOT
    if not port_taken(host, port):
        return "ok"
    url = f"http://{host}:{port}"
    if health_ok(url):
        return "already"
    ours: list[int] = []
    foreign = False
    owned = read_pid_file()
    for pid in listen_pids(port):
        if pid == os.getpid():
            continue
        cmd = process_cmdline(pid)
        if pid == owned or is_our_process(cmd, root):
            ours.append(pid)
        else:
            foreign = True
    if ours and not foreign:
        for pid in ours:
            kill_pid_tree(pid)
        for _ in range(25):
            if not port_taken(host, port):
                clear_pid_file()
                return "ok"
            time.sleep(0.12)
    return "busy"


def _message_box(title: str, text: str, error: bool = False) -> None:
    if sys.platform != "win32":
        print(f"{title}: {text}")
        return
    ctypes.windll.user32.MessageBoxW(None, text, title, 0x10 if error else 0x40)


def _ask_yes_no(title: str, text: str) -> bool:
    if sys.platform != "win32":
        print(text)
        return True
    return ctypes.windll.user32.MessageBoxW(None, text, title, 0x04 | 0x20) == 6


class _QueueIO:
    encoding = "utf-8"
    errors = "replace"
    closed = False

    def __init__(self, put) -> None:
        self._put = put

    def write(self, s: str) -> int:
        if s:
            self._put(s)
        return len(s) if s else 0

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False

    def fileno(self) -> int:
        raise OSError("no fileno")


def run_window(args) -> None:
    import tkinter as tk
    from tkinter.scrolledtext import ScrolledText

    import uvicorn
    import webbrowser

    from src.engine.config import CONFIG_DIR
    from src.server.app import create_app
    from src.server.serve import ensure_frontend, port_taken

    attach_kill_on_close_job()

    host = args.host
    port = args.port
    url = f"http://{host}:{port}"
    title = "失落之地"

    state = take_port(host, port)
    if state == "already":
        keep = _ask_yes_no(
            title,
            "游戏已经在运行。\n\n是：打开浏览器继续\n否：结束旧服务并重新启动",
        )
        if keep:
            webbrowser.open(url)
            return
        kill_own_listeners(port)
        for _ in range(25):
            if not port_taken(host, port):
                break
            time.sleep(0.12)
        else:
            msg = f"没能结束端口 {port} 上的本游戏进程。"
            _message_box(title, msg, error=True)
            raise SystemExit(msg)
        clear_pid_file()
    elif state == "busy":
        msg = f"端口 {port} 被其他程序占用，没有结束他人进程。"
        _message_box(title, msg, error=True)
        raise SystemExit(msg)

    logs: queue.Queue[str] = queue.Queue()
    ui_jobs: queue.Queue = queue.Queue()
    server_box: dict = {"server": None}

    def put(s: str) -> None:
        logs.put(s if s.endswith("\n") else s + "\n")

    def on_main(fn) -> None:
        ui_jobs.put(fn)

    sys.stdout = _QueueIO(put)  # type: ignore[assignment]
    sys.stderr = _QueueIO(put)  # type: ignore[assignment]

    root = tk.Tk()
    root.title(title)
    root.geometry("560x420")
    root.minsize(480, 320)

    status = tk.StringVar(value="正在启动…")
    tk.Label(root, textvariable=status, anchor="w", padx=12, pady=8).pack(fill="x")
    log = ScrolledText(root, height=18, wrap="word", state="disabled")
    log.pack(fill="both", expand=True, padx=10, pady=(0, 8))

    btns = tk.Frame(root)
    btns.pack(fill="x", padx=10, pady=(0, 10))

    def open_browser() -> None:
        webbrowser.open(url)

    def halt() -> None:
        clear_pid_file()
        srv = server_box.get("server")
        if srv is not None:
            srv.should_exit = True
        os._exit(0)

    tk.Button(btns, text="打开浏览器", command=open_browser).pack(side="left")
    tk.Button(btns, text="退出并关闭服务", command=halt).pack(side="right")
    root.protocol("WM_DELETE_WINDOW", halt)

    def pump() -> None:
        chunk = []
        try:
            while True:
                chunk.append(logs.get_nowait())
        except queue.Empty:
            pass
        if chunk:
            log.configure(state="normal")
            log.insert("end", "".join(chunk))
            log.see("end")
            log.configure(state="disabled")
        try:
            while True:
                ui_jobs.get_nowait()()
        except queue.Empty:
            pass
        root.after(80, pump)

    def worker() -> None:
        try:
            put("准备前端…")
            ensure_frontend(rebuild=args.rebuild)
            app = create_app(args.config or CONFIG_DIR)
            on_main(lambda t=app.title: root.title(t))

            @app.on_event("startup")
            def _started() -> None:
                on_main(lambda: status.set(f"运行中  {url}"))
                put(f"已启动：{url}")
                if not args.no_browser:
                    open_browser()

            cfg = uvicorn.Config(app, host=host, port=port, log_level="info", log_config=None, use_colors=False)
            server = uvicorn.Server(cfg)
            server_box["server"] = server
            write_pid_file()
            server.run()
            on_main(lambda: status.set("已停止"))
        except Exception as e:
            put(f"启动失败：{e}")
            on_main(lambda: status.set("启动失败"))
            _message_box(title, str(e), error=True)

    pump()
    threading.Thread(target=worker, daemon=True).start()
    root.mainloop()
    halt()
