# utils/youtube_refs.py
from __future__ import annotations

import os
import sys
from pathlib import Path

import cv2
import imagehash
import imageio_ffmpeg
import numpy as np
from PIL import Image
from yt_dlp import YoutubeDL

__all__ = ["download_youtube", "extract_keyframes", "sample_frames"]

# 1) ffmpeg 경로 확보 + 환경변수/PATH 주입
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
FFDIR = str(Path(FFMPEG_EXE).parent)
os.environ["IMAGEIO_FFMPEG_EXE"] = FFMPEG_EXE  # moviepy/imageio용
os.environ["FFMPEG_BINARY"] = FFMPEG_EXE  # 일부 라이브러리용
os.environ["PATH"] = FFDIR + os.pathsep + os.environ.get("PATH", "")

print(f"✅ ffmpeg 환경변수 설정: {FFMPEG_EXE}")


def _ensure_packages():
    try:
        import yt_dlp  # noqa
    except Exception:
        raise RuntimeError(
            "yt-dlp 가 설치되어 있지 않습니다. "
            "다음 명령으로 설치하세요:\n"
            f'"{sys.executable}" -m pip install yt-dlp'
        )
    try:
        import imageio_ffmpeg  # noqa
    except Exception:
        raise RuntimeError(
            "imageio-ffmpeg 가 설치되어 있지 않습니다. "
            "다음 명령으로 설치하세요:\n"
            f'"{sys.executable}" -m pip install imageio-ffmpeg'
        )


def download_youtube(url: str, out_dir: Path) -> Path:
    """
    yt-dlp Python API로 유튜브 영상 다운로드 (최종 mp4).
    ffmpeg 환경변수가 이미 설정되어 있음.
    """
    _ensure_packages()

    out_dir.mkdir(parents=True, exist_ok=True)

    # 2) yt-dlp에 ffmpeg 위치 명시 (Python310 폴더에 ffmpeg/ffprobe 복사됨)
    ydl_opts = {
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "noprogress": True,
        "quiet": True,
        "ffmpeg_location": r"C:\Users\user\AppData\Local\Programs\Python\Python310",  # ffmpeg/ffprobe 복사한 폴더
        "merge_output_format": "mp4",
        "format": "bv*+ba/best[ext=mp4]/best",  # 고화질+오디오 → mp4
    }

    print(f"✅ ffmpeg 사용: {FFMPEG_EXE}")

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        vid = info.get("id")
        candidates = list(out_dir.glob(f"{vid}.*"))
        if not candidates:
            raise RuntimeError("영상 다운로드는 되었으나 결과 파일을 찾지 못했습니다.")
        mp4 = next((p for p in candidates if p.suffix.lower() == ".mp4"), None)
        return mp4 or candidates[0]


def _laplacian_sharpness(gray: np.ndarray) -> float:
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def _phash(img_bgr: np.ndarray) -> imagehash.ImageHash:
    img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(img)
    return imagehash.phash(pil)


def _hist_distance(a_bgr: np.ndarray, b_bgr: np.ndarray) -> float:
    a = cv2.cvtColor(a_bgr, cv2.COLOR_BGR2HSV)
    b = cv2.cvtColor(b_bgr, cv2.COLOR_BGR2HSV)
    hist_a = cv2.calcHist([a], [0, 1], None, [32, 32], [0, 180, 0, 256])
    hist_b = cv2.calcHist([b], [0, 1], None, [32, 32], [0, 180, 0, 256])
    cv2.normalize(hist_a, hist_a)
    cv2.normalize(hist_b, hist_b)
    # 0=유사, 1=다름
    return cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_BHATTACHARYYA)


def sample_frames(
    video_path: Path,
    save_dir: Path,
    num_frames: int = 6,
    start_sec: float = 3.0,
    end_sec: float | None = None,
) -> list[Path]:
    """
    빠른 프레임 샘플링 (MVP용)
    """
    save_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError("영상 열기 실패")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps

    start_frame = int(start_sec * fps)
    end_frame = int((end_sec or duration) * fps) if end_sec else total_frames

    # 균등 간격으로 프레임 선택
    frame_indices = np.linspace(start_frame, end_frame - 1, num_frames, dtype=int)

    saved_paths = []
    for i, frame_idx in enumerate(frame_indices):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if ret:
            # 960px로 리사이즈
            if frame.shape[1] > 960:
                r = 960 / frame.shape[1]
                frame = cv2.resize(
                    frame, (960, int(frame.shape[0] * r)), interpolation=cv2.INTER_AREA
                )

            out_path = save_dir / f"yt_ref_{i + 1:03d}.jpg"
            cv2.imwrite(str(out_path), frame)
            saved_paths.append(out_path)

    cap.release()
    return saved_paths


def extract_keyframes(
    video_path: Path,
    save_dir: Path,
    target_frames: int = 60,
    candidate_fps: float = 3.0,
    min_sharpness: float = 60.0,
    hash_thresh: int = 8,
    min_scene_diff: float = 0.3,
    resize_width: int = 960,
) -> list[Path]:
    """
    - candidate_fps 간격으로 후보 프레임 추출
    - 흐린 프레임 제거(Laplacian)
    - perceptual hash로 중복 제거
    - 장면 차이(HSV 히스토그램)로 다양성 확보
    - target_frames 만큼 저장
    """
    save_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError("영상 열기 실패")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(fps / candidate_fps)))

    candidates: list[tuple[int, np.ndarray, float, imagehash.ImageHash]] = []

    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % step == 0:
            if resize_width and frame.shape[1] > resize_width:
                r = resize_width / frame.shape[1]
                frame = cv2.resize(
                    frame, (resize_width, int(frame.shape[0] * r)), interpolation=cv2.INTER_AREA
                )
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            sharp = _laplacian_sharpness(gray)
            if sharp >= min_sharpness:
                ph = _phash(frame)
                candidates.append((frame_idx, frame, sharp, ph))
        frame_idx += 1

    cap.release()
    if not candidates:
        return []

    # 중복 제거
    unique: list[tuple[int, np.ndarray, float, imagehash.ImageHash]] = []
    for idx, img, sharp, ph in candidates:
        dup = False
        for _, u_img, _, u_ph in unique:
            if ph - u_ph < hash_thresh:
                dup = True
                break
        if not dup:
            unique.append((idx, img, sharp, ph))
        if len(unique) > target_frames * 4:
            break

    if not unique:
        unique = candidates

    # 장면 다양성
    selected = []
    last_img = None
    for idx, img, sharp, ph in sorted(unique, key=lambda x: x[0]):
        if last_img is None:
            selected.append((idx, img))
            last_img = img
            continue
        dist = _hist_distance(last_img, img)
        if dist >= min_scene_diff:
            selected.append((idx, img))
            last_img = img
        if len(selected) >= target_frames:
            break

    # 부족하면 sharpness 기준 보충
    if len(selected) < target_frames:
        remain = target_frames - len(selected)
        already = set(i for i, _ in selected)
        pool = sorted(unique, key=lambda x: x[2], reverse=True)
        for idx, img, sharp, ph in pool:
            if idx in already:
                continue
            selected.append((idx, img))
            if len(selected) >= target_frames:
                break

    out_paths: list[Path] = []
    for i, (idx, img) in enumerate(sorted(selected, key=lambda x: x[0]), start=1):
        out_p = save_dir / f"yt_ref_{i:03d}.jpg"
        cv2.imwrite(str(out_p), img)
        out_paths.append(out_p)

    return out_paths
