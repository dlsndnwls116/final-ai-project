# utils/downloader.py
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from typing import Any


def which(name: str) -> str | None:
    """시스템 PATH에서 실행 파일 찾기"""
    p = shutil.which(name)
    return p if p else None


def check_ytdlp():
    """yt-dlp 체크: exe 우선, 없으면 모듈 방식"""
    # 1. exe 파일 체크
    exe = which("yt-dlp") or which("yt-dlp.exe")
    if exe:
        try:
            result = subprocess.run(
                [exe, "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=5,
            )
            if result.returncode == 0:
                return True, f"exe: {exe} ({result.stdout.strip()})"
        except Exception:
            pass

    # 2. 모듈 방식 체크
    try:
        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=5,
        )
        if result.returncode == 0:
            return True, f"module: {sys.executable} -m yt_dlp ({result.stdout.strip()})"
    except Exception as e:
        return False, f"모듈 호출 실패: {e}"

    return False, "yt-dlp not found"


def healthcheck() -> dict[str, Any]:
    """환경 체크: ffmpeg, ffprobe, yt-dlp 경로 및 버전 확인"""
    out = {
        "ffmpeg": which("ffmpeg"),
        "ffprobe": which("ffprobe"),
        "python": sys.executable,
        "version_info": {},
    }

    # ffmpeg 버전 체크
    if out["ffmpeg"]:
        try:
            result = subprocess.run(
                [out["ffmpeg"], "-version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=5,
            )
            if result.returncode == 0:
                version_line = result.stdout.split("\n")[0]
                out["version_info"]["ffmpeg"] = version_line
        except Exception as e:
            out["version_info"]["ffmpeg"] = f"버전 확인 실패: {e}"

    # ffprobe 버전 체크
    if out["ffprobe"]:
        try:
            result = subprocess.run(
                [out["ffprobe"], "-version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=5,
            )
            if result.returncode == 0:
                version_line = result.stdout.split("\n")[0]
                out["version_info"]["ffprobe"] = version_line
        except Exception as e:
            out["version_info"]["ffprobe"] = f"버전 확인 실패: {e}"

    # yt-dlp 체크 (exe + 모듈 방식)
    yt_dlp_ok, yt_dlp_info = check_ytdlp()
    out["yt_dlp"] = yt_dlp_ok
    out["version_info"]["yt_dlp"] = yt_dlp_info

    out["ok"] = all([out["ffmpeg"], out["ffprobe"], out["yt_dlp"]])
    return out


def download_youtube(
    url: str, out_dir: str, progress_cb: Callable[[int, str], None] = lambda p, m: None
) -> str:
    """유튜브 영상 다운로드 (안전한 래퍼) - 여러 방법 시도"""
    os.makedirs(out_dir, exist_ok=True)
    prog = os.path.join(out_dir, "raw.%(ext)s")

    # 다운로드 방법들 (우선순위 순)
    download_methods = [
        {
            "name": "Android 클라이언트 (권장)",
            "cmd": [
                sys.executable, "-m", "yt_dlp",
                "-f", "best[height<=1080]",
                "--merge-output-format", "mp4",
                "--extractor-args", "youtube:player_client=android",
                "-o", prog, "--no-playlist",
                url,
            ]
        },
        {
            "name": "iOS 클라이언트",
            "cmd": [
                sys.executable, "-m", "yt_dlp",
                "-f", "best[height<=1080]",
                "--merge-output-format", "mp4",
                "--extractor-args", "youtube:player_client=ios",
                "-o", prog, "--no-playlist",
                url,
            ]
        },
        {
            "name": "기본 클라이언트 (fallback)",
            "cmd": [
                sys.executable, "-m", "yt_dlp",
                "-f", "best",
                "--merge-output-format", "mp4",
                "-o", prog, "--no-playlist",
                url,
            ]
        }
    ]

    progress_cb(5, "유튜브 다운로드 시작...")

    for i, method in enumerate(download_methods):
        try:
            progress_cb(5 + i*3, f"다운로드 시도 {i+1}/{len(download_methods)}: {method['name']}")
            
            result = subprocess.run(
                method["cmd"], 
                capture_output=True, 
                text=True, 
                encoding="utf-8", 
                errors="ignore", 
                timeout=300
            )

            if result.returncode == 0:
                progress_cb(15, "다운로드 완료, 파일 검색 중...")
                
                # 결과 파일 찾기
                for f in os.listdir(out_dir):
                    if f.startswith("raw.") and f.endswith(".mp4"):
                        file_path = os.path.join(out_dir, f)
                        progress_cb(20, f"다운로드 성공: {f}")
                        return file_path
                
                # mp4 파일이 없으면 다른 확장자 찾기
                for f in os.listdir(out_dir):
                    if f.startswith("raw.") and any(f.endswith(ext) for ext in [".mp4", ".mkv", ".webm"]):
                        file_path = os.path.join(out_dir, f)
                        progress_cb(20, f"다운로드 성공: {f}")
                        return file_path
                
                raise FileNotFoundError("다운로드된 비디오 파일을 찾을 수 없습니다.")
            
            # 실패 시 로그 기록
            print(f"[DEBUG] {method['name']} 실패: {result.stderr[:200]}...")
            
        except subprocess.TimeoutExpired:
            print(f"[DEBUG] {method['name']} 시간 초과")
            continue
        except Exception as e:
            print(f"[DEBUG] {method['name']} 예외: {str(e)}")
            continue

    # 모든 방법 실패
    error_msg = f"모든 다운로드 방법 실패. 최근 오류:\n{result.stderr if 'result' in locals() else 'N/A'}\n\n해결 방법:\n"
    error_msg += "1. 유튜브 URL이 올바른지 확인\n"
    error_msg += "2. 인터넷 연결 상태 확인\n"
    error_msg += "3. yt-dlp 업데이트: pip install -U yt-dlp\n"
    error_msg += "4. 영상이 비공개/삭제되지 않았는지 확인\n"
    error_msg += "5. 다른 유튜브 영상으로 시도해보세요"
    raise RuntimeError(error_msg)


def extract_audio(
    video_path: str, out_dir: str, progress_cb: Callable[[int, str], None] = lambda p, m: None
) -> str:
    """비디오에서 오디오 추출"""
    os.makedirs(out_dir, exist_ok=True)
    audio_path = os.path.join(out_dir, "audio.m4a")

    ffmpeg_path = which("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError(
            "ffmpeg를 찾을 수 없습니다. PATH에 ffmpeg가 설치되어 있는지 확인해주세요."
        )

    cmd = [
        ffmpeg_path,
        "-i",
        video_path,
        "-vn",  # 비디오 스트림 제외
        "-acodec",
        "aac",
        "-ab",
        "128k",
        "-y",  # 덮어쓰기
        audio_path,
    ]

    progress_cb(25, "오디오 추출 중...")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode != 0:
            raise RuntimeError(f"오디오 추출 실패:\n{result.stderr}")

        progress_cb(30, "오디오 추출 완료")
        return audio_path

    except subprocess.TimeoutExpired:
        raise RuntimeError("오디오 추출 시간 초과")
    except Exception as e:
        raise RuntimeError(f"오디오 추출 중 오류: {str(e)}")


def save_health_report(health_data: dict[str, Any], out_path: str):
    """환경 체크 결과를 JSON 파일로 저장"""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(health_data, f, ensure_ascii=False, indent=2)
