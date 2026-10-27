# 공개 코드 계약 평가

총 38건: PASS 38, FAIL 0

기존 23문항의 입력과 기대값은 유지했다. 제품의 label_host가 복합 작물명을 구분자 경계까지 보존하도록 패치하고, 전체 이름·별칭·대소문자·출처 접미사·유사 접두어 회귀 15문항을 추가했다.

모델을 로드하지 않고 실제 app.py에서 네 함수를 추출하여 실행했다. 함수 본문을 평가용 코드로 교체하지 않았으며 외부 API와 GPU를 호출하지 않았다. 모델 추론 성능과 서버 통합 동작은 이 결과에 포함되지 않는다.

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
| PD-09 | label_host | PASS | "napa_cabbage" | "napa_cabbage" |
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
| PD-R01 | label_host | PASS | "napa_cabbage" | "napa_cabbage" |
| PD-R02 | label_host | PASS | "napa_cabbage" | "napa_cabbage" |
| PD-R03 | label_host | PASS | "napa" | "napa" |
| PD-R04 | label_host | PASS | "bell_pepper" | "bell_pepper" |
| PD-R05 | label_host | PASS | "bell_pepper" | "bell_pepper" |
| PD-R06 | label_host | PASS | "bell" | "bell" |
| PD-R07 | label_host | PASS | "chinese_cabbage" | "chinese_cabbage" |
| PD-R08 | label_host | PASS | "chinese_cabbage" | "chinese_cabbage" |
| PD-R09 | label_host | PASS | "chinese" | "chinese" |
| PD-R10 | label_host | PASS | "grape" | "grape" |
| PD-R11 | label_host | PASS | "grape" | "grape" |
| PD-R12 | label_host | PASS | "grapevinex" | "grapevinex" |
| PD-R13 | label_host | PASS | "cabbage" | "cabbage" |
| PD-R14 | label_host | PASS | "napa" | "napa" |
| PD-R15 | label_host | PASS | "tomato" | "tomato" |

수정 전 22/23 결과와 원래 평가셋은 [baseline](baseline/RESULTS.md)에 보존했다. 이전 실패 PD-09가 같은 기대값 napa_cabbage를 반환하는지 재확인한다. 이 평가는 모델 정확도나 농가 외부검증을 대체하지 않으며 기존 B3/Small 점수와 합산하지 않는다.

재현: `python evaluation/contract-v1/run.py` (저장소 루트). 표준 라이브러리만 사용하며 실패 시 종료 코드 1. fixture, 제품 코드, 실행기 SHA-256과 실행 환경은 results.json에 기록한다.

평가셋·실행기·패치: Codex(ai-assisted). 개발 회귀이며 독립 블라인드 평가가 아니다. 사람 검토는 대기 중이다.
