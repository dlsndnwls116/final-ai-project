import os, json, re, textwrap, argparse
from datetime import datetime
from dotenv import load_dotenv

# ========= 환경 =========
load_dotenv()
OPENAI_KEY  = os.getenv("OPENAI_API_KEY")
GEMINI_KEY  = os.getenv("GEMINI_API_KEY")

# ========= 공통 프롬프트 =========
SYSTEM_TEMPLATE = """\
당신은 숏폼 광고 디렉터다.
목표: 15초 리얼스(1080x1920, 30fps). 도시/건물 공간 → 후반 제품 클로즈업 무드, 빠른 템포.
아래 입력을 바탕으로 결과를 JSON으로만 반환하라.

[입력]
- 레퍼런스 요약: {ref_summary}
- 제품 설명: {product_desc}
- 브랜드 톤: {brand_tone}
- 금지요소: {avoid}

[출력 JSON 스키마]
{{
  "fps": 30,
  "resolution": "1080x1920",
  "duration_sec": 15,
  "shots": [
    {{
      "id": 1,
      "start": 0.0,
      "end": 1.8,
      "camera": "tilt up / fast whip",
      "bg_prompt": "도시 고층 빌딩 로비, 하드라이트, 글로시 바닥, 빈 영역 상단 20%",
      "caption": "후킹 카피(최대 10자)",
      "vo": "보이스오버(선택)",
      "sfx": "whoosh",
      "mj_prompt": "미드저니용 한 줄 프롬프트 --ar 9:16 --stylize 250 --chaos 8"
    }}
  ],
  "cta": "마지막 컷 CTA(최대 12자)"
}}
주의:
- shots는 7~9컷. 컷별 길이 합이 duration_sec과 일치.
- caption은 한글, 짧고 강렬하게.
- mj_prompt는 배경/공간 위주, 제품은 후반부 컷에만 언급.
JSON만 출력.
"""

# ========= 유틸 =========
def coerce_json(text: str):
    """코드블럭/텍스트에서 JSON만 안전 추출"""
    m = re.search(r"\{.*\}", text, re.S)
    if not m: raise ValueError("JSON 본문을 찾지 못했어요.")
    return json.loads(m.group(0))

def srt_time(t):
    ms = int((t - int(t)) * 1000)
    h  = int(t // 3600); m = int((t%3600)//60); s = int(t%60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def write_outputs(plan: dict, outdir="out"):
    os.makedirs(outdir, exist_ok=True)
    # storyboard
    with open(os.path.join(outdir,"storyboard.json"),"w",encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    # MJ prompts
    mj_lines = []
    for s in plan["shots"]:
        mj_lines.append(f"CUT {s['id']} [{s['start']:.2f}-{s['end']:.2f}s] : {s.get('mj_prompt','')}")
    open(os.path.join(outdir,"prompts_midjourney.txt"),"w",encoding="utf-8").write("\n".join(mj_lines))
    # SRT
    srt = []; idx = 1
    for s in plan["shots"]:
        cap = (s.get("caption") or "").strip()
        if not cap: continue
        srt += [str(idx), f"{srt_time(s['start'])} --> {srt_time(s['end'])}", cap, ""]
        idx += 1
    open(os.path.join(outdir,"captions.srt"),"w",encoding="utf-8").write("\n".join(srt))
    # editlist
    edit = []
    for s in plan["shots"]:
        dur = round(s["end"]-s["start"], 2)
        edit.append(f"{s['id']},{dur}")
    open(os.path.join(outdir,"editlist.txt"),"w").write("\n".join(edit))

# ========= 엔진: OpenAI =========
def make_with_openai(prompt:str, model="gpt-4o-mini"):
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role":"user","content":prompt}],
        temperature=0.6
    )
    return coerce_json(resp.choices[0].message.content)

# ========= 엔진: Gemini =========
def make_with_gemini(prompt:str, model="gemini-2.0-flash"):
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_KEY)
    m = genai.GenerativeModel(model)
    resp = m.generate_content(prompt)
    # text가 code block을 감쌀 수 있어도 coerce_json이 처리
    return coerce_json(resp.text or "")

# ========= 엔진 선택 =========
def select_engine(engine: str):
    if engine == "gpt":
        if not OPENAI_KEY: raise RuntimeError("OPENAI_API_KEY 없음")
        return ("gpt", make_with_openai)
    if engine == "gemini":
        if not GEMINI_KEY: raise RuntimeError("GEMINI_API_KEY 없음")
        return ("gemini", make_with_gemini)
    # auto
    if OPENAI_KEY: return ("gpt", make_with_openai)
    if GEMINI_KEY: return ("gemini", make_with_gemini)
    raise RuntimeError("사용 가능한 API 키가 없습니다.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["auto","gpt","gemini"], default="auto", help="AI 엔진 선택")
    ap.add_argument("--provider", choices=["auto","gpt","gemini"], help="AI 프로바이더 선택 (--engine과 동일)")
    ap.add_argument("--prompt", help="사용자 정의 프롬프트")
    ap.add_argument("--ref", default="빠른 템포로 도시·건물 공간 스냅컷 → 마지막 3초 제품 클로즈업")
    ap.add_argument("--product", default="매트 블랙 무선 이어버즈, 저지연/하이브리드 ANC, 메탈릭 포인트")
    ap.add_argument("--tone", default="미니멀, 프리미엄, 하이컨트라스트")
    ap.add_argument("--avoid", default="귀여움, 파스텔, 저해상도, 과한 보케")
    ap.add_argument("--outdir", default="out")
    args = ap.parse_args()

    # --provider가 지정되면 --engine보다 우선
    engine = args.provider if args.provider else args.engine
    
    # 사용자 프롬프트가 있으면 직접 사용, 없으면 템플릿 사용
    if args.prompt:
        prompt = args.prompt
    else:
        prompt = SYSTEM_TEMPLATE.format(
            ref_summary=args.ref, product_desc=args.product,
            brand_tone=args.tone, avoid=args.avoid
        )

    name, maker = select_engine(engine)
    print(f"▶ 엔진: {name}")
    plan = maker(prompt)
    # 안전장치: 핵심 필드 보정
    plan["fps"] = 30
    plan["resolution"] = "1080x1920"
    write_outputs(plan, args.outdir)
    print(f"✅ 완료: {args.outdir}/storyboard.json, prompts_midjourney.txt, captions.srt, editlist.txt")

if __name__ == "__main__":
    main()
