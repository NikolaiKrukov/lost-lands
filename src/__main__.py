import multiprocessing
import sys
import traceback


def _crash(exc: BaseException) -> None:
    text = traceback.format_exc()
    path = None
    try:
        from pathlib import Path

        path = Path(__file__).resolve().parents[1] / "saves" / "launch_error.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except Exception:
        path = None
    print(text, file=sys.stderr)
    if sys.platform == "win32":
        try:
            import ctypes

            msg = str(exc)
            if path is not None:
                msg += f"\n\n完整报错已写入：{path}"
            ctypes.windll.user32.MessageBoxW(None, msg, "失落之地 启动失败", 0x10)
        except Exception:
            pass


if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        from src.server.serve import main

        main()
    except Exception as e:
        _crash(e)
        raise SystemExit(1) from e
