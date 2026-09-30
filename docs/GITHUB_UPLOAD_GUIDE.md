# GitHub 업로드 가이드

## 1. 업로드 전 직접 확인

- GitHub 사용자명, 연락처, 프로젝트 기간을 README에 추가할지 결정
- 저장소 라이선스를 선택할지 결정
- `src/mobile/lib/core/constants/server_config.dart`의 로컬 서버 주소를 예시 값으로 바꿀지 확인
- 모든 파일에서 실제 API 키가 없는지 재확인
- 데이터셋과 공공 자료의 명칭·출처 링크를 추가할지 확인
- 앱 스크린샷에 개인 알림, IP, 위치정보가 보이지 않는지 확인

## 2. 로컬 Git 저장소 만들기

```powershell
cd E:\plantdoctor\leaf-parazzi-portfolio
git init
git add .
git status
git commit -m "docs: publish Leaf Parazzi plant diagnosis portfolio"
```

## 3. GitHub의 빈 저장소와 연결

GitHub에서 README나 `.gitignore`를 자동 생성하지 않은 빈 저장소를 만든 뒤:

```powershell
git branch -M main
git remote add origin https://github.com/<YOUR_ID>/<REPOSITORY>.git
git push -u origin main
```

## 4. 대용량 파일 확인

```powershell
Get-ChildItem -Recurse -File |
  Where-Object Length -gt 50MB |
  Select-Object FullName, @{N='MB';E={[math]::Round($_.Length/1MB,1)}}
```

현재 공개본에는 모델 가중치, 데이터셋, APK를 넣지 않는 것을 권장합니다. 나중에 배포 파일을 공유하려면 GitHub Release 또는 모델 저장소를 사용하고 checksum을 함께 제공하십시오.

## 5. 권장 저장소 설명

```text
SegFormer + ConvNeXt + evidence-gated Vector RAG 기반 Android 식물 질병 진단 시스템 (개인 프로젝트)
```

권장 토픽:

```text
plant-disease-detection, semantic-segmentation, segformer,
convnext, rag, sentence-transformers, fastapi, flutter, android
```

## 6. 공개 후 확인

- README의 Mermaid가 정상 렌더링되는지 확인
- 문서 내부 상대 링크가 모두 열리는지 확인
- GitHub secret scanning 경고가 없는지 확인
- 저장소의 Languages가 의도한 코드 구성을 반영하는지 확인
- About 영역에 설명과 topics를 추가
