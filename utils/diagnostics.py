# utils/diagnostics.py
from __future__ import annotations
import os, sys, time, threading, traceback, json
from dataclasses import dataclass, field
from typing import Dict, Optional, Any

# psutil이 없을 경우를 위한 fallback
try:
    import psutil  # type: ignore
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

DEFAULT_TIMEOUT = float(os.getenv("WATCHDOG_TIMEOUT", "90"))  # 초
STRICT = os.getenv("ADGEN_DEBUG", "0") == "1"

# ──────────────────────────────────────────────────────────────────────────────
# Heartbeat & Hang Watchdog
# ──────────────────────────────────────────────────────────────────────────────
_last_beats: Dict[str, float] = {}
_lock = threading.Lock()
_watchdog_started = False

def heartbeat(tag: str) -> None:
    """긴 작업 중 1~2초마다 호출. 최근 시각을 기록한다."""
    with _lock:
        _last_beats[tag] = time.time()

def _dump_threads() -> str:
    stacks = []
    for thread_id, frame in sys._current_frames().items():
        stacks.append(
            f"\n--- Thread {thread_id} ({threading.current_thread().name}) ---\n"
            + "".join(traceback.format_stack(frame))
        )
    return "".join(stacks)

def _get_memory_info() -> float:
    """메모리 사용량을 MB 단위로 반환. psutil이 없으면 0 반환."""
    if PSUTIL_AVAILABLE:
        try:
            proc = psutil.Process()
            return proc.memory_info().rss / (1024 * 1024)
        except:
            return 0.0
    return 0.0

def _watchdog_loop(timeout: float) -> None:
    while True:
        time.sleep(3.0)
        now = time.time()
        stale = []
        with _lock:
            for tag, ts in list(_last_beats.items()):
                if now - ts > timeout:
                    stale.append(tag)
        if not stale:
            continue

        # 문제 감지 → 덤프 남김
        rss = _get_memory_info()
        msg = {
            "event": "watchdog_stale",
            "stale_tags": stale,
            "timeout_sec": timeout,
            "rss_mb": round(rss, 1),
            "ts": int(now),
        }
        print("[WATCHDOG]", json.dumps(msg, ensure_ascii=False))
        dump = _dump_threads()
        log_path = os.path.join("logs", f"hang_{int(now)}.log")
        os.makedirs("logs", exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(dump)
        print(f"[WATCHDOG] thread dump → {log_path}")

        if STRICT:
            raise RuntimeError(f"Watchdog timeout: {stale} (see {log_path})")

def start_watchdog(timeout: float = DEFAULT_TIMEOUT) -> None:
    global _watchdog_started
    if _watchdog_started:
        return
    _watchdog_started = True
    t = threading.Thread(target=_watchdog_loop, args=(timeout,), daemon=True)
    t.start()
    print(f"[WATCHDOG] started (timeout={timeout}s, strict={STRICT})")

# ──────────────────────────────────────────────────────────────────────────────
# LoopGuard: 루프 과회전/무한루프 탐지
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class LoopGuard:
    name: str
    max_iter: int = 100000
    warn_every: int = 10000
    start_ts: float = field(default_factory=time.time)
    count: int = 0

    def tick(self, extra: Optional[Dict[str, Any]] = None) -> None:
        """루프 바디에서 매 회전마다 호출."""
        self.count += 1
        if self.count % self.warn_every == 0:
            elapsed = time.time() - self.start_ts
            print(
                json.dumps(
                    {
                        "event": "loop_progress",
                        "name": self.name,
                        "iter": self.count,
                        "elapsed": round(elapsed, 2),
                        "extra": extra or {},
                    },
                    ensure_ascii=False,
                )
            )
        if self.count > self.max_iter:
            elapsed = time.time() - self.start_ts
            msg = (
                f"LoopGuard overflow: {self.name} "
                f"(iter={self.count}, elapsed={elapsed:.1f}s)"
            )
            if STRICT:
                raise RuntimeError(msg)
            else:
                print("[LoopGuard WARN]", msg)

def loop_guard(name: str, max_iter: int = 100000, warn_every: int = 10000) -> LoopGuard:
    return LoopGuard(name=name, max_iter=max_iter, warn_every=warn_every)
