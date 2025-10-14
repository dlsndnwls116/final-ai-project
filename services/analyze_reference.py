"""
S2. 레퍼런스 자동 분석 서비스
영상에서 샷/전환/박자/팔레트/타이포/OCR/모션을 추출하고 타임라인 레시피(JSON) 생성
"""

import json
import os
import subprocess
import tempfile
from typing import Any

import cv2

# OCR
import easyocr

# Audio analysis
import librosa
import numpy as np

# Color analysis
# PySceneDetect
from scenedetect import SceneManager, open_video
from scenedetect.detectors import ContentDetector

# Machine learning for color clustering
from sklearn.cluster import KMeans

RECIPE_VERSION = "0.1"


def extract_scenes(
    video_path: str, threshold: float = 27.0, min_scene_len: int = 12
) -> list[tuple[float, float]]:
    """장면 탐지: PySceneDetect content mode"""
    try:
        video = open_video(video_path)
        sm = SceneManager()
        sm.add_detector(ContentDetector(threshold=threshold, min_scene_len=min_scene_len))
        sm.detect_scenes(video)
        scene_list = sm.get_scene_list()

        # (start_seconds, end_seconds) 튜플 리스트로 변환
        scenes = []
        for scene in scene_list:
            start_sec = scene[0].get_seconds()
            end_sec = scene[1].get_seconds()
            scenes.append((start_sec, end_sec))

        return scenes
    except Exception as e:
        print(f"장면 탐지 실패: {e}")
        return []


def audio_beats(video_path: str) -> tuple[float, list[float]]:
    """박자 분석: librosa.beat.beat_track"""
    try:
        # ffmpeg로 오디오 추출
        wav_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        cmd = ["ffmpeg", "-y", "-i", video_path, "-vn", "-ac", "1", "-ar", "44100", wav_path]

        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=60
        )
        if result.returncode != 0:
            print(f"오디오 추출 실패: {result.stderr}")
            return 120.0, []  # 기본값

        # librosa로 박자 분석
        y, sr = librosa.load(wav_path, sr=44100)
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")

        # 임시 파일 정리
        os.unlink(wav_path)

        return float(tempo), beats.tolist()
    except Exception as e:
        print(f"박자 분석 실패: {e}")
        return 120.0, []  # 기본값


def palette_for_frame(frame_bgr: np.ndarray, k: int = 5) -> list[str]:
    """팔레트 추출: KMeans 클러스터링"""
    try:
        # BGR → RGB 변환
        img_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        # 픽셀 데이터 재구성
        pixels = img_rgb.reshape(-1, 3)

        # KMeans 클러스터링
        km = KMeans(n_clusters=k, n_init="auto", random_state=42)
        km.fit(pixels)

        # 클러스터 중심을 색상 코드로 변환
        centers = km.cluster_centers_.astype(int)
        colors = []
        for r, g, b in centers:
            color_hex = f"#{r:02X}{g:02X}{b:02X}"
            colors.append(color_hex)

        return colors
    except Exception as e:
        print(f"팔레트 추출 실패: {e}")
        return ["#000000", "#FFFFFF", "#808080", "#FF0000", "#00FF00"]  # 기본값


def extract_ocr_text(
    frame_bgr: np.ndarray, languages: list[str] = ["ko", "en"]
) -> list[dict[str, Any]]:
    """OCR 텍스트 추출: easyocr"""
    try:
        reader = easyocr.Reader(languages)
        results = reader.readtext(frame_bgr)

        text_boxes = []
        for bbox, text, confidence in results:
            if confidence > 0.5:  # 신뢰도 50% 이상만
                # bbox를 [x1, y1, x2, y2] 형태로 정규화
                bbox_array = np.array(bbox)
                x1, y1 = bbox_array.min(axis=0)
                x2, y2 = bbox_array.max(axis=0)

                text_boxes.append(
                    {
                        "text": text,
                        "bbox": [int(x1), int(y1), int(x2), int(y2)],
                        "confidence": float(confidence),
                    }
                )

        return text_boxes
    except Exception as e:
        print(f"OCR 추출 실패: {e}")
        return []


def _to_gray(img: np.ndarray) -> np.ndarray | None:
    """이미지를 그레이스케일로 안전하게 변환"""
    if img is None:
        return None
    if len(img.shape) == 3 and img.shape[2] == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def detect_motion(
    prev_frame: np.ndarray, cur_frame: np.ndarray, prev_pts: np.ndarray | None = None
) -> tuple[dict[str, Any], np.ndarray | None]:
    """모션 감지: optical flow 기반 줌/팬/틸트 추정 (안전한 버전)"""
    try:
        prev_gray = _to_gray(prev_frame)
        gray = _to_gray(cur_frame)

        if prev_gray is None or gray is None:
            return {
                "type": "static",
                "intensity": 0.0,
                "zoom": 1.0,
                "pan_x": 0.0,
                "pan_y": 0.0,
            }, None

        # 포인트가 없으면 새로 추출
        if prev_pts is None or len(prev_pts) < 4:
            prev_pts = cv2.goodFeaturesToTrack(
                prev_gray, maxCorners=200, qualityLevel=0.01, minDistance=7, blockSize=7
            )
            if prev_pts is None:
                # 텍스처가 없으면 기본 모션 감지로 폴백
                diff = cv2.absdiff(prev_gray, gray)
                motion_pixels = np.sum(diff > 30)
                total_pixels = diff.shape[0] * diff.shape[1]
                motion_ratio = motion_pixels / total_pixels

                return {
                    "type": "pan" if motion_ratio > 0.1 else "static",
                    "intensity": float(motion_ratio),
                    "zoom": 1.0,
                    "pan_x": 0.0,
                    "pan_y": 0.0,
                }, None

        # 포인트를 올바른 형태로 변환
        prev_pts = np.float32(prev_pts.reshape(-1, 1, 2))

        try:
            # Optical Flow 계산 (안전한 버전)
            next_pts, st, err = cv2.calcOpticalFlowPyrLK(
                prev_gray,
                gray,
                prev_pts,
                None,
                winSize=(21, 21),
                maxLevel=3,
                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
            )
        except cv2.error as e:
            print(f"OpticalFlow 계산 실패: {e}")
            return {
                "type": "static",
                "intensity": 0.0,
                "zoom": 1.0,
                "pan_x": 0.0,
                "pan_y": 0.0,
            }, None

        if next_pts is None or st is None:
            return {
                "type": "static",
                "intensity": 0.0,
                "zoom": 1.0,
                "pan_x": 0.0,
                "pan_y": 0.0,
            }, None

        # 유효한 포인트만 추출
        good_new = next_pts[st == 1]
        good_old = prev_pts[st == 1]

        if len(good_new) < 4:
            # 유효점 부족 -> 기본 모션 감지로 폴백
            diff = cv2.absdiff(prev_gray, gray)
            motion_pixels = np.sum(diff > 30)
            total_pixels = diff.shape[0] * diff.shape[1]
            motion_ratio = motion_pixels / total_pixels

            return {
                "type": "pan" if motion_ratio > 0.1 else "static",
                "intensity": float(motion_ratio),
                "zoom": 1.0,
                "pan_x": 0.0,
                "pan_y": 0.0,
            }, None

        # 모션 벡터 계산
        motion_vectors = good_new - good_old
        motion_magnitude = np.linalg.norm(motion_vectors, axis=1)
        avg_motion = float(np.mean(motion_magnitude))

        # 모션 방향 분석
        avg_dx = float(np.mean(motion_vectors[:, 0]))
        avg_dy = float(np.mean(motion_vectors[:, 1]))

        # 모션 타입 분류
        if avg_motion < 1.0:
            motion_type = "static"
        elif abs(avg_dx) > abs(avg_dy):
            motion_type = "pan_horizontal"
        else:
            motion_type = "pan_vertical"

        return {
            "type": motion_type,
            "intensity": avg_motion,
            "zoom": 1.0,  # 실제로는 scale 변화 계산 필요
            "pan_x": avg_dx,
            "pan_y": avg_dy,
        }, good_new

    except Exception as e:
        print(f"모션 감지 실패: {e}")
        return {"type": "static", "intensity": 0.0, "zoom": 1.0, "pan_x": 0.0, "pan_y": 0.0}, None


def analyze_reference(
    video_path: str, out_dir: str, num_keyframes: int = 120, progress_cb=None
) -> dict[str, Any]:
    """레퍼런스 영상 종합 분석"""
    warnings = []  # 분석 중 발생한 경고들

    if progress_cb:
        progress_cb(5, "분석 준비 중...")

    os.makedirs(out_dir, exist_ok=True)
    frames_dir = os.path.join(out_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    # 1. 장면 탐지
    if progress_cb:
        progress_cb(15, "장면 탐지 중...")
    scenes = extract_scenes(video_path)

    if not scenes:
        raise RuntimeError("장면을 찾을 수 없습니다.")

    # 2. 박자 분석
    if progress_cb:
        progress_cb(35, "박자 분석 중...")
    tempo, beats = audio_beats(video_path)

    # 3. 비디오 정보 추출
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps

    # 4. 샷별 분석
    if progress_cb:
        progress_cb(50, "샷별 분석 중...")

    shots = []
    prev_frame = None
    prev_pts = None  # OpticalFlow 추적을 위한 이전 프레임의 특징점

    for i, (start_sec, end_sec) in enumerate(scenes):
        if progress_cb and i % 10 == 0:
            progress_cb(50 + (i / len(scenes)) * 20, f"샷 {i + 1}/{len(scenes)} 분석 중...")

        # 샷 중간 시점의 프레임 추출
        middle_sec = start_sec + (end_sec - start_sec) / 2
        cap.set(cv2.CAP_PROP_POS_MSEC, middle_sec * 1000)
        ret, frame = cap.read()

        if not ret:
            continue

        # 팔레트 추출
        palette = palette_for_frame(frame, k=5)

        # OCR 텍스트 추출
        ocr_texts = extract_ocr_text(frame)

        # 모션 감지 (이전 프레임과 비교)
        motion = {"type": "static", "intensity": 0.0, "zoom": 1.0, "pan_x": 0.0, "pan_y": 0.0}
        if prev_frame is not None:
            motion, prev_pts = detect_motion(prev_frame, frame, prev_pts)
            # 모션 감지 실패 시 경고 추가
            if motion["type"] == "static" and prev_pts is None and i > 0:
                warnings.append(f"샷 {i + 1}: 모션 포인트 검출 실패 (텍스처 부족)")

        # 썸네일 저장
        thumb_path = os.path.join(frames_dir, f"shot_{i:03d}.jpg")
        cv2.imwrite(thumb_path, frame)

        # 샷 정보 구성
        shot_info = {
            "idx": i,
            "t0": round(start_sec, 2),
            "t1": round(end_sec, 2),
            "duration": round(end_sec - start_sec, 2),
            "transition_in": "cut" if i == 0 else "auto",
            "motion": motion,
            "palette": palette,
            "thumb": thumb_path,
            "text": ocr_texts,
            "overlay": [],
            "needs": [],
        }

        shots.append(shot_info)
        prev_frame = frame.copy()

    cap.release()

    # 5. 레시피 JSON 생성
    if progress_cb:
        progress_cb(85, "레시피 생성 중...")

    recipe = {
        "version": RECIPE_VERSION,
        "meta": {
            "fps": fps,
            "size": [width, height],
            "duration": total_duration,
            "total_shots": len(shots),
        },
        "audio": {
            "bpm": tempo,
            "beats": beats[:128],  # 최대 128개 비트만 저장
        },
        "shots": shots,
        "globals": {
            "typography": {"primary": "Pretendard-Bold", "outline": True},
            "lut": "warm-soft",
        },
        "warnings": warnings,  # 분석 경고 추가
        "checklist": [],
    }

    # 6. 결과 저장
    recipe_path = os.path.join(out_dir, "recipe.json")
    with open(recipe_path, "w", encoding="utf-8") as f:
        json.dump(recipe, f, ensure_ascii=False, indent=2)

    # 7. 비트 정보 별도 저장
    beat_info = {"bpm": tempo, "beats": beats, "total_beats": len(beats)}
    beat_path = os.path.join(out_dir, "beat.json")
    with open(beat_path, "w", encoding="utf-8") as f:
        json.dump(beat_info, f, ensure_ascii=False, indent=2)

    if progress_cb:
        progress_cb(100, "분석 완료!")

    return recipe


def get_analysis_summary(recipe: dict[str, Any]) -> dict[str, Any]:
    """분석 결과 요약 정보"""
    shots = recipe.get("shots", [])
    audio = recipe.get("audio", {})
    meta = recipe.get("meta", {})

    # 샷 통계
    shot_durations = [shot.get("duration", 0) for shot in shots]
    avg_shot_duration = np.mean(shot_durations) if shot_durations else 0

    # 팔레트 통계
    all_colors = []
    for shot in shots:
        all_colors.extend(shot.get("palette", []))

    # 텍스트 통계
    total_texts = sum(len(shot.get("text", [])) for shot in shots)

    return {
        "total_shots": len(shots),
        "total_duration": meta.get("duration", 0),
        "avg_shot_duration": round(avg_shot_duration, 2),
        "bpm": audio.get("bpm", 0),
        "total_beats": len(audio.get("beats", [])),
        "unique_colors": len(set(all_colors)),
        "total_texts": total_texts,
        "fps": meta.get("fps", 0),
        "resolution": f"{meta.get('size', [0, 0])[0]}x{meta.get('size', [0, 0])[1]}",
    }
