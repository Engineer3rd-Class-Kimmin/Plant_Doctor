# 공개 코드 계약 평가

총 23건: PASS 22, FAIL 1

모델을 로드하지 않고 원본 app.py에서 네 함수를 추출하여 실행했다. 원본 함수 본문을 복사하거나 교체하지 않았으며, 외부 API와 GPU를 호출하지 않았다. 실제 AI 추론 성능은 이 결과에 포함되지 않는다.

| ID | 함수 | 결과 | 기대값 | 실제값 |
|---|---|---|---|---|
| PD-01 | normalize_label | PASS | "tomato_blight" | "tomato_blight" |
| PD-02 | normalize_label | PASS | "apple_scab" | "apple_scab" |
| PD-03 | normalize_label | PASS | "grape_mildew" | "grape_mildew" |
| PD-04 | normalize_label | PASS | "" | "" |
| PD-05 | normalize_label | PASS | "rice_blast" | "rice_blast" |
| PD-06 | label_host | PASS | "bell_pepper" | "bell_pepper" |
| PD-07 | label_host | PASS | "grape" | "grape" |
| PD-08 | label_host | PASS | "tomato" | "tomato" |
| PD-09 | label_host | FAIL | "napa_cabbage" | "napa" |
| PD-10 | label_host | PASS | "" | "" |
| PD-11 | _extract_json | PASS | {"a": 1} | {"a": 1} |
| PD-12 | _extract_json | PASS | {"a": 1} | {"a": 1} |
| PD-13 | _extract_json | PASS | {"a": 1} | {"a": 1} |
| PD-14 | _extract_json | PASS | {} | {} |
| PD-15 | _extract_json | PASS | {} | {} |
| PD-16 | _extract_json | PASS | {} | {} |
| PD-17 | _extract_json | PASS | {} | {} |
| PD-18 | _extract_json | PASS | {} | {} |
| PD-19 | _extract_json | PASS | {} | {} |
| PD-20 | _string_values | PASS | [] | [] |
| PD-21 | _string_values | PASS | ["symptom"] | ["symptom"] |
| PD-22 | _string_values | PASS | ["a", "b"] | ["a", "b"] |
| PD-23 | _string_values | PASS | ["0"] | ["0"] |

복합 작물명 실패는 host 제약의 위험을 드러낸다. 이 평가는 모델 정확도나 농가 외부검증을 대체하지 않으며, 기존 B3/Small 점수와 합산하지 않는다.

재현: `python evaluation/contract-v1/run.py` (저장소 루트). 표준 라이브러리만 사용하며 실패 시 종료 코드 1. fixture, 원본 코드, 실행기 SHA-256과 실행 환경은 results.json에 기록한다.

평가셋·실행기 작성: Codex(ai-assisted). 개발 진단이며 독립 블라인드 평가가 아니다.
