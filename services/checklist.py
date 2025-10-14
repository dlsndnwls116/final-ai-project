"""
S3. 자동 체크리스트 & 브리프/샷리스트 서비스
recipe.json을 바탕으로 필수 소스 체크리스트를 생성하고, 업로드/입력 UI 제공
"""

from datetime import datetime
from pathlib import Path
from typing import Any


def analyze_shot_needs(shot: dict[str, Any]) -> list[str]:
    """샷 분석 결과로 needs 채우기(제품 중심으로 우선 분석)"""
    needs = []

    # 1-소스 모드에서는 제품이 항상 필요
    needs.append("product")

    # 색상 팔레트 분석 (자동 생성에 필요)
    palette = shot.get("palette", [])
    if palette:
        needs.append("brand_color")

    # 텍스트 분석
    texts = shot.get("text", [])
    for text_info in texts:
        text = text_info.get("text", "").lower()

        # 할인/프로모션 관련 텍스트 감지
        if any(
            keyword in text for keyword in ["할인", "discount", "sale", "off", "%", "원", "won"]
        ):
            needs.append("offer_text")

        # CTA 관련 텍스트 감지
        if any(
            keyword in text
            for keyword in ["지금", "now", "방문", "visit", "구매", "buy", "신청", "apply"]
        ):
            needs.append("cta_text")

        # 브랜드명/상호 관련 텍스트 감지
        if any(
            keyword in text for keyword in ["카페", "cafe", "스토어", "store", "브랜드", "brand"]
        ):
            needs.append("brand_logo")

    # 모션 분석
    motion = shot.get("motion", {})
    motion_type = motion.get("type", "static")

    if motion_type in ["pan", "zoom"]:
        # 팬/줌 모션이 있으면 외부 컷이나 제품 컷일 가능성
        if "외부" in str(shot.get("description", "")) or "exterior" in str(
            shot.get("description", "")
        ):
            needs.append("store_exterior")
        else:
            needs.append("product_shot")

    return list(set(needs))  # 중복 제거


def build_checklist(recipe: dict[str, Any]) -> dict[str, Any]:
    """레시피를 바탕으로 체크리스트 생성"""

    # 기본 체크리스트 항목들
    base_needs = [
        {
            "id": "product",
            "type": "image",
            "desc": "제품 이미지/영상",
            "required": True,
            "placeholder": "제품 사진 또는 영상 (PNG/JPG/MP4/MOV)",
        },
        {
            "id": "brand_color",
            "type": "color",
            "desc": "브랜드 색상(hex), 없으면 팔레트로 대체",
            "required": False,
            "placeholder": "분석된 팔레트에서 자동 선택",
        },
        {
            "id": "brand_logo",
            "type": "image",
            "desc": "투명 배경 로고(PNG)",
            "required": False,
            "placeholder": "스톡 로고 또는 텍스트로 대체 가능",
        },
        {
            "id": "offer_text",
            "type": "text",
            "desc": "할인 문구/기간",
            "required": False,
            "placeholder": "예: 20% 할인, 9월 한정",
        },
        {
            "id": "cta_text",
            "type": "text",
            "desc": "CTA (예: 지금 방문하세요!)",
            "required": False,
            "placeholder": "예: 지금 방문하세요! / 바로 신청하기",
        },
        {
            "id": "store_exterior",
            "type": "video",
            "desc": "가게 외부 2~4초",
            "required": False,
            "placeholder": "스톡 비디오 또는 이미지로 대체",
        },
        {
            "id": "product_shot",
            "type": "video",
            "desc": "제품/B-roll 2~4초(최소 2개)",
            "required": False,
            "placeholder": "스톡 비디오 또는 이미지로 대체",
        },
    ]

    # 샷별 needs 분석
    shots = recipe.get("shots", [])
    shot_needs = []

    for shot in shots:
        needs = analyze_shot_needs(shot)
        shot_needs.extend(needs)

    # needs 빈도 계산
    needs_count = {}
    for need in shot_needs:
        needs_count[need] = needs_count.get(need, 0) + 1

    # 체크리스트 업데이트 (1-소스 모드: 제품만 필수)
    checklist = []
    for item in base_needs:
        item_id = item["id"]
        frequency = needs_count.get(item_id, 0)

        # 1-소스 모드에서는 제품만 필수, 나머지는 선택사항
        if item_id == "product":
            item["required"] = True
        else:
            item["required"] = False
            
        item["frequency"] = frequency
        checklist.append(item)

    # recipe에 체크리스트 추가
    recipe["checklist"] = checklist

    return recipe


def generate_brief_md(recipe: dict[str, Any], user_input: str = "") -> str:
    """간결한 브리프 마크다운 생성"""

    meta = recipe.get("meta", {})
    audio = recipe.get("audio", {})
    shots = recipe.get("shots", [])

    # 기본 정보
    duration = meta.get("duration", 0)
    fps = meta.get("fps", 30)
    resolution = f"{meta.get('size', [0, 0])[0]}x{meta.get('size', [0, 0])[1]}"
    bpm = audio.get("bpm", 120)

    # 샷 요약
    shot_summary = []
    for i, shot in enumerate(shots[:10]):  # 처음 10개만
        shot_info = {
            "time": f"{shot['t0']:.1f}s-{shot['t1']:.1f}s",
            "duration": f"{shot['duration']:.1f}s",
            "motion": shot.get("motion", {}).get("type", "static"),
            "colors": shot.get("palette", [])[:3],
        }
        shot_summary.append(shot_info)

    # 브리프 마크다운 생성
    brief_content = f"""# 광고 브리프

## 기본 정보
- **영상 길이**: {duration:.1f}초
- **해상도**: {resolution}
- **프레임레이트**: {fps} FPS
- **BPM**: {bpm:.1f}
- **총 샷 수**: {len(shots)}개

## 사용자 요구사항
{user_input if user_input else "레퍼런스 영상 기반 자동 생성"}

## 샷 구성
"""

    for i, shot in enumerate(shot_summary):
        brief_content += f"""
### 샷 {i + 1}: {shot["time"]}
- **길이**: {shot["duration"]}
- **모션**: {shot["motion"]}
- **주요 색상**: {", ".join(shot["colors"])}
"""

    # 스타일 가이드
    brief_content += f"""
## 스타일 가이드
- **전체 톤**: 동적이고 현대적인 스타일
- **색상 팔레트**: 분석된 색상 조합 활용
- **모션**: 자연스러운 전환과 적절한 속도감
- **타이포그래피**: Pretendard-Bold, 아웃라인 적용

## 체크리스트 (1-소스 모드)
- [x] **제품 이미지/영상** (필수)
- [ ] 브랜드 색상 (자동 생성)
- [ ] 브랜드 로고 (선택사항)
- [ ] 할인 문구/기간 텍스트 (선택사항)
- [ ] CTA 텍스트 (선택사항)
- [ ] 가게 외부 영상 (선택사항)
- [ ] 제품/B-roll 영상 (선택사항)

---
*생성일: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""

    return brief_content


def generate_shotlist_json(recipe: dict[str, Any]) -> dict[str, Any]:
    """샷리스트 JSON 생성"""

    shots = recipe.get("shots", [])
    meta = recipe.get("meta", {})
    audio = recipe.get("audio", {})

    shotlist = {
        "version": "1.0",
        "meta": {
            "total_shots": len(shots),
            "duration": meta.get("duration", 0),
            "fps": meta.get("fps", 30),
            "resolution": meta.get("size", [0, 0]),
            "bpm": audio.get("bpm", 120),
        },
        "shots": [],
    }

    for i, shot in enumerate(shots):
        shot_item = {
            "shot_number": i + 1,
            "time_range": {"start": shot["t0"], "end": shot["t1"], "duration": shot["duration"]},
            "visual": {
                "thumbnail": shot["thumb"],
                "palette": shot.get("palette", []),
                "motion": shot.get("motion", {}),
                "description": f"샷 {i + 1} - {shot.get('motion', {}).get('type', 'static')} 모션",
            },
            "text": {"elements": shot.get("text", []), "needs": analyze_shot_needs(shot)},
            "assets": {"required": [], "optional": []},
        }

        # 필요한 자산 분석 (1-소스 모드: 제품만 필수)
        needs = analyze_shot_needs(shot)
        for need in needs:
            if need == "product":
                shot_item["assets"]["required"].append(need)
            else:
                shot_item["assets"]["optional"].append(need)

        shotlist["shots"].append(shot_item)

    return shotlist


def save_assets_structure(project_id: str, checklist: list[dict[str, Any]]) -> str:
    """자산 저장 구조 생성"""

    assets_dir = Path("assets") / project_id
    assets_dir.mkdir(parents=True, exist_ok=True)

    # 자산별 폴더 생성
    for item in checklist:
        item_id = item["id"]
        item_type = item["type"]

        if item_type == "image":
            (assets_dir / "images").mkdir(exist_ok=True)
        elif item_type == "video":
            (assets_dir / "videos").mkdir(exist_ok=True)
        elif item_type == "text":
            (assets_dir / "texts").mkdir(exist_ok=True)
        elif item_type == "color":
            (assets_dir / "colors").mkdir(exist_ok=True)

    return str(assets_dir)


def get_upload_instructions(checklist: list[dict[str, Any]]) -> dict[str, Any]:
    """업로드 가이드 생성"""

    instructions = {
        "required": [],
        "optional": [],
        "file_types": {
            "image": ["png", "jpg", "jpeg", "gif"],
            "video": ["mp4", "mov", "avi", "mkv"],
            "text": ["txt", "md"],
            "color": ["hex", "css"],
        },
        "max_sizes": {"image": "10MB", "video": "100MB", "text": "1MB", "color": "1KB"},
    }

    for item in checklist:
        item_info = {
            "id": item["id"],
            "desc": item["desc"],
            "type": item["type"],
            "placeholder": item.get("placeholder", ""),
            "frequency": item.get("frequency", 0),
        }

        if item["required"]:
            instructions["required"].append(item_info)
        else:
            instructions["optional"].append(item_info)

    return instructions
