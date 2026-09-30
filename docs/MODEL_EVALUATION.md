# 데이터와 모델 평가

## 데이터셋 분석

### PlantSeg

- 원본 규모: 11,457개 이미지
- 정규화 클래스: 386개
- 작물 그룹: 35개
- 10장 미만 클래스: 273개
- 30장 미만 클래스: 284개
- 분류 데이터 생성 중 제외한 비정상 빈 마스크: 16건

이 분포는 전체 386개 클래스를 그대로 안정적으로 분류하기 어렵다는 것을 보여줍니다. 따라서 실제 제품 범위를 24개 주요 작물로 제한하고, 충분한 샘플과 설명 근거가 있는 질병 클래스를 중심으로 구성했습니다.

### PlantWild

- 전체 확인 규모: 18,542장, 89개 클래스
- healthy subset: 7,840장, 30개 클래스
- 분할용 준비 샘플: 4,000장
- train: 3,400장
- validation: 600장

PlantWild healthy 샘플의 마스크는 의도적으로 전부 비어 있습니다. 이는 데이터 오류가 아니라 정상 잎에 병변 픽셀이 없다는 정답입니다.

### hard negative 구성

병변이 아닌 영역을 병변으로 오인하는 문제를 줄이기 위해 PlantWild 정상 잎과 실제 실패 사례를 섞었습니다. 한 구성 manifest에서는 lesion train 8,255장, healthy train 2,752장, lesion validation 908장, healthy validation 600장을 기록했습니다.

## 최종 병변 분할: SegFormer-B3

최종 산출물은 ImageNet/ADE20K 계열 사전학습 가중치에서 시작한 SegFormer-B3 기반 2-class segmentation 모델입니다.

| PlantSeg 원본 테스트 | 값 |
|---|---:|
| True Positive pixels | 39,090,987 |
| False Positive pixels | 11,025,068 |
| False Negative pixels | 8,205,401 |
| Dice | **80.2587%** |
| IoU | **67.0268%** |
| Precision | **78.0009%** |
| Recall | **82.6511%** |
| False Positive Rate | **5.9522%** |

선택된 checkpoint는 epoch 3입니다. 점수 선택에는 PlantSeg 성능뿐 아니라 정상 잎과 실패 사례에서의 false positive도 함께 고려했습니다.

증강 테스트에서 PlantSeg Dice 78.43%, IoU 64.51%, Recall 83.01%를 기록했습니다. 환경 변형에서 recall은 유지되지만 precision이 하락하는 양상을 확인해, 실시간 사용에서는 mask threshold와 최소 병변 면적 조건이 중요하다고 판단했습니다.

## 최종 질병 분류: ConvNeXt-Small

| 항목 | 값 |
|---|---:|
| 클래스 | 62 |
| 학습 이미지 | 4,578 |
| 검증 이미지 | 1,117 |
| 입력 크기 | 384 × 384 |
| batch size | 16 |
| best epoch | 21 |
| Top-1 Accuracy | **82.7216%** |
| Top-3 Accuracy | **93.1065%** |
| Macro Recall | **81.7237%** |

정확도만 높고 소수 클래스가 무시되는 상황을 피하기 위해 Macro Recall을 함께 선택 기준에 반영했습니다. 사용자에게 하나의 단정값만 보여주기보다 Top-3 후보를 유지해 RAG와 결과 설명 단계에서 비교할 수 있도록 했습니다.

## 환경 증강

실제 촬영 조건을 모사하기 위해 다음 변형을 조합했습니다.

- 90/180/270도 및 소각도 회전
- 수평/수직 반전
- 밝기, 대비, 감마, 채도, 색온도 변화
- 부분 그림자와 역광
- Gaussian/motion blur
- 센서 노이즈와 JPEG 압축
- crop/scale/resize 변화

발표 기준으로 SegFormer 학습 입력은 약 7,000/2,300/2,300(train/val/test) 원본에서 약 18만 장 규모의 증강 샘플 흐름을 사용했고, 분류기는 약 4,700/1,600/1,600 원본 구성에서 약 12.8만 장 규모의 증강 흐름을 사용했습니다. 실제 run summary에는 필터링 이후 학습 4,578장, 검증 1,117장이 기록되어 있습니다. 발표 수치는 준비 단계, run summary는 최종 학습 입력이라는 차이가 있습니다.

## 이전 실험과의 관계

이 프로젝트에는 SegFormer-B2/B3, ConvNeXt-Tiny/Small, 원본/환경 증강, predicted mask/ground-truth mask, host-aware/non-host-aware 평가가 혼재합니다. 예를 들어 이전 Tiny 모델의 공식 테스트 Top-1 79.94%, Top-3 91.65%와 host-constrained Top-1 92.02%가 남아 있지만, 이는 최종 Small 모델과 평가 대상이 다릅니다.

따라서 포트폴리오에서는 다음 원칙을 따릅니다.

- 최종 모델은 B3/Small의 원본 지표 파일을 기준으로 표시
- host constraint가 적용된 수치는 일반 분류 정확도와 분리
- 서로 다른 테스트셋의 수치를 직접 빼서 개선 폭으로 주장하지 않음
- 모델 성능과 앱 end-to-end 품질을 구분

## 해석과 한계

- 높은 Top-3는 후보 생성에는 유리하지만 확정 진단 정확도를 뜻하지 않습니다.
- long-tail 질병은 학습 표본이 적어 Macro 지표와 클래스별 confusion을 계속 봐야 합니다.
- 정상 잎 false positive가 완전히 제거된 것은 아닙니다.
- 증강 데이터는 실제 농가 외부 검증을 대체하지 않습니다.
- 계절, 생육 단계, 복합 감염, 영양 결핍은 이미지 하나만으로 구분하기 어렵습니다.
