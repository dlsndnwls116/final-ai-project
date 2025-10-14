# utils/frame_extractor.py
from __future__ import annotations
import os
from pathlib import Path
from PIL import Image
import cv2

def extract_frame_to_image(video_path: str, t: float = 0.5) -> Image.Image:
    """
    비디오에서 특정 시점의 프레임을 추출하여 PIL Image로 반환
    종속성: pip install moviepy imageio-ffmpeg
    
    Args:
        video_path: 비디오 파일 경로
        t: 추출할 시점 (초)
    
    Returns:
        PIL Image 객체
    """
    try:
        # MoviePy 사용 (더 안정적)
        from moviepy.editor import VideoFileClip
        import numpy as np
        
        with VideoFileClip(video_path) as v:
            if not v.duration:
                t = 0
            else:
                t = min(t, v.duration / 2)  # 영상 길이의 절반 이하로 제한
            frame = v.get_frame(t)  # np.ndarray (H,W,3)
        
        return Image.fromarray(np.uint8(frame))
        
    except Exception as e:
        # OpenCV 폴백
        try:
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                raise ValueError(f"비디오 파일을 열 수 없습니다: {video_path}")
            
            # 총 프레임 수와 FPS 확인
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            if fps <= 0:
                fps = 30.0  # 기본 FPS
            
            # 추출할 프레임 번호 계산
            frame_number = int(t * fps)
            frame_number = min(frame_number, total_frames - 1)  # 범위 체크
            
            # 해당 프레임으로 이동
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            
            # 프레임 읽기
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                raise ValueError(f"프레임을 읽을 수 없습니다: {video_path}")
            
            # BGR -> RGB 변환 (OpenCV는 BGR 사용)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # PIL Image로 변환
            pil_image = Image.fromarray(frame_rgb)
            
            return pil_image
            
        except Exception as e2:
            raise ValueError(f"프레임 추출 실패 (MoviePy: {e}, OpenCV: {e2})")

def extract_multiple_frames(video_path: str, frame_times: list[float]) -> list[Image.Image]:
    """
    비디오에서 여러 시점의 프레임을 추출
    
    Args:
        video_path: 비디오 파일 경로
        frame_times: 추출할 시점들 (초 단위)
    
    Returns:
        PIL Image 객체들의 리스트
    """
    images = []
    for time in frame_times:
        try:
            img = extract_frame_to_image(video_path, time)
            images.append(img)
        except Exception as e:
            print(f"프레임 {time}초 추출 실패: {e}")
    
    return images

def get_video_duration(video_path: str) -> float:
    """
    비디오의 총 재생 시간을 반환
    
    Args:
        video_path: 비디오 파일 경로
    
    Returns:
        재생 시간 (초)
    """
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"비디오 파일을 열 수 없습니다: {video_path}")
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        
        if fps <= 0:
            return 0.0
        
        return frame_count / fps
        
    except Exception:
        return 0.0

__all__ = ["extract_frame_to_image", "extract_multiple_frames", "get_video_duration"]
