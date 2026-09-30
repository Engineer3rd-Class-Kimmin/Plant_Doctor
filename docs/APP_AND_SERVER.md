# 앱과 서버

## Flutter 앱

앱은 다음 사용자 흐름을 구현합니다.

1. 홈 화면에서 작물 선택
2. 실시간 카메라 또는 갤러리 이미지 입력
3. 실시간 분할 마스크로 병변 후보 확인
4. 사진을 서버에 보내 통합 진단
5. 질병 후보, 신뢰도, 근거 기반 설명 확인
6. 질병 사전과 날씨·농업 가이드 탐색

주요 코드 영역:

- `features/camera`: 카메라 입력과 촬영
- `screens/live_segmentation_screen.dart`: 실시간 마스크 표시
- `services/live_segmentation_service.dart`: 서버 통신 및 응답 파싱
- `features/host_selection`: 작물 선택
- `features/result`, `screens/diagnosis_result_screen.dart`: 결과 표현
- `features/dictionary`: 작물별 질병 사전
- `features/weather`, `services/weather_service.dart`: 날씨 기반 정보
- `core/localization`: 다국어 문자열

## FastAPI 서버

서버 시작 시 SegFormer-B3, ConvNeXt-Small, E5 query encoder, RAG 인덱스, OpenAI client를 로드합니다. 실제 실행 로그에서 다음 상태를 확인했습니다.

```text
SegFormer ready
ConvNeXt-Small ready
OpenAI client ready
vector RAG ready vectors=38697 dim=768 normalized=True
Application startup complete
```

### Windows 실행

```powershell
cd E:\plantdoctor\plant_doctor_live_segmentation\server
E:\EyeGuideRAG\.venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8001
```

가상환경을 활성화하지 않고 Python 실행 파일을 직접 호출하면 PowerShell ExecutionPolicy 문제를 피할 수 있습니다.

### 상태 확인

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
```

`http://127.0.0.1:8001/`에 404가 나타나는 것은 루트 라우트가 정의되지 않았기 때문일 수 있습니다. 서버 장애 판단에는 반드시 `/health` 또는 실제 API 경로를 사용해야 합니다.

## 휴대폰 연결

Android 기기에서 `127.0.0.1`과 `localhost`는 PC가 아니라 휴대폰 자신을 가리킵니다. 같은 Wi-Fi에서는 PC의 IPv4 주소와 포트 8001을 설정해야 합니다.

```text
http://<PC의-LAN-IP>:8001
```

외부 네트워크에서는 ngrok 같은 HTTPS 터널을 사용할 수 있지만, 공개 URL과 API 키를 소스 코드에 하드코딩하지 않아야 합니다.

## 의존성 문제 사례

시스템 Python으로 실행했을 때 `ModuleNotFoundError: pillow_heif`가 발생했습니다. 프로젝트에서 사용하던 EyeGuideRAG 가상환경에는 필요한 패키지가 있었으므로 해당 Python으로 실행해 해결했습니다. 재현 환경을 만들 때는 `requirements_mobile_api.txt`를 기준으로 HEIF, FastAPI, Uvicorn, PyTorch/Transformers 등 실제 import 의존성을 고정해야 합니다.

## 공개 저장소에서 제외한 것

- `server/.env` 및 API 키
- 실행 로그와 터널 URL
- 수백 MB 모델 가중치
- 38,697개 벡터 본체와 원문 metadata
- Android 서명키와 빌드된 APK

포트폴리오에는 서버와 앱 소스, 의존성 목록, 지표와 인덱스 manifest만 남겨 설계를 검토할 수 있도록 했습니다.
