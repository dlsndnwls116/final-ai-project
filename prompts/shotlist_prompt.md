# Ad Brief → Shotlist JSON (System Guide)
아래 **JSON 객체**로만 출력하고 설명/문장 금지.

{
  "shots": [
    {"t":0.0,"dur":2.2,"type":"intro","scene":"string","caption":"string"},
    {"t":2.2,"dur":4.2,"type":"value","scene":"string","caption":"string"},
    {"t":6.4,"dur":2.8,"type":"cta","scene":"string","caption":"string"}
  ]
}

규칙:
- 총 길이 8~10초(3비트). 필요 시 각 dur를 균형 있게 조정.
- caption은 10~16자 한 줄, brief의 tone/offer/cta 반영.
- 필드 외 키 금지. 숫자는 소수점 한 자리~두 자리.
- 한국어로 작성.
