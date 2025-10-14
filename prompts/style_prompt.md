# Reference + Brief → Style Guide (JSON only)
다음 JSON **객체 한 개만** 출력. 설명/문장 금지.

{
  "palette": ["#RRGGBB", "..."],
  "font": { "family": "Pretendard", "weight": "600", "fallback": ["Arial","Noto Sans KR"] },
  "caption": { "align": "center", "max_chars": 16, "shadow": true, "bg_opacity": 0.15 },
  "motion": { "transition": "crossfade", "speed": "natural", "cut_rhythm": "3-beat" },
  "mood": ["따뜻함","감성"],
  "music": { "bpm": "80-100", "mood": "warm lo-fi" },
  "cta_style": { "shape": "rounded", "bg": "#000000", "fg": "#FFFFFF" }
}

규칙:
- 한국어.
- 입력 palette(있으면) 우선 사용, 부족 시 최대 6색으로 보강.
- 캡션은 릴스/쇼츠 가독성 기준(10~16자 한 줄).
- 키 추가 금지, 값만 출력.
