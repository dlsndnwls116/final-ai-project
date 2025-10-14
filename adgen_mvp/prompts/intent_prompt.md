# Intent → Ad Brief JSON (System Guide)
아래 스키마로만 JSON을 출력하라. 설명/문자 금지.

{
  "brand": "string|null",
  "target": "string",
  "tone": "string",
  "colors": ["#RRGGBB", "..."],
  "format": "9:16",
  "offer": "string|null",
  "cta": "string",
  "motifs": ["string", "..."]
}

규칙:
- 한국어.
- 누락값은 null 또는 합리적 기본값.
- format은 기본 9:16.
- colors는 1~3개, hex 권장(#b57f5f 등).
