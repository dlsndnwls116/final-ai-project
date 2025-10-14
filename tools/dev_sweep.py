# tools/dev_sweep.py
from __future__ import annotations
import subprocess, sys, json, os, time, tempfile, textwrap

ROOT = os.path.dirname(os.path.dirname(__file__))

def run(cmd: list[str]) -> dict:
    t0 = time.time()

    # 모든 하위 프로세스에 UTF-8 강제
    env = os.environ.copy()
    env.update({
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    })

    try:
        cp = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,                 # 텍스트 모드
            encoding="utf-8",          # ← 디코딩을 UTF-8로 고정
            errors="replace",          # ← 못 푸는 문자는로 치환(크래시 방지)
            env=env,
            timeout=180,               # ← 3분 제한
            check=False,
        )
        ok = (cp.returncode == 0)
        return {
            "cmd": " ".join(cmd),
            "ok": ok,
            "rc": cp.returncode,
            "stdout": cp.stdout[-4000:],  # 너무 길면 뒷부분만
            "stderr": cp.stderr[-4000:],
            "elapsed": round(time.time() - t0, 2),
        }
    except subprocess.TimeoutExpired as e:
        return {
            "cmd": " ".join(cmd),
            "ok": False,
            "rc": -1,
            "stdout": "",
            "stderr": "timeout",
            "elapsed": round(time.time() - t0, 2),
        }
    except Exception as e:
        return {
            "cmd": " ".join(cmd),
            "ok": False,
            "exc": repr(e),
            "elapsed": round(time.time() - t0, 2),
        }

def main() -> int:
    results = []
    # 1) 컴파일 에러 선제 차단
    results.append(run([sys.executable, "-m", "compileall", "-q", "app", "services", "utils"]))

    # 2) ruff / mypy / pytest(스모크) / 초미니 렌더 스모크
    results.append(run([sys.executable, "-m", "ruff", "check", "." ]))
    results.append(run(["mypy", "services", "app", "utils", "--ignore-missing-imports"]))
    results.append(run(["pytest", "-q", "-k", "smoke or quick or sanity", "--maxfail=1"]))

    # 3) 초미니 렌더 스모크: 1장 이미지로 1s 렌더 (있으면)
    smoke = os.path.join(ROOT, "tools", "smoke_render.py")
    if os.path.exists(smoke):
        results.append(run([sys.executable, smoke]))

    summary = {
        "ok": all(r.get("ok") for r in results),
        "results": results,
    }
    os.makedirs("logs", exist_ok=True)
    with open(os.path.join("logs", "dev_sweep.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
