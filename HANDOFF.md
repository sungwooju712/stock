# KOSPI 인사이트 — 작업 인계 노트

최종 갱신: 2026-10-24 (KST)

이 문서는 다른 PC에서 실행하거나 개발을 이어서 할 때 필요한 정보를 정리한 것입니다.
AI 대화 자체는 파일로 저장되지 않으므로, 새 PC에서 OpenCode를 열고 이 문서를 먼저 읽게 하면 됩니다.

## 1. 현재 상태

- Windows용 데스크톱 앱 구현 완료: 대시보드, 종목 분석, 스크리너, 즐겨찾기 관리, 데이터·설정
- 최종 상호작용 테스트: **54/54 통과**
- 최종 UI 확인: 1440×920, 1180×760 (실제 Windows Qt 렌더링)
- 최종 휴대용 빌드: `dist\KOSPI Insight\`
  - `KOSPI Insight.exe` 5,979,102 bytes
  - 전체 262개 파일, 약 145.1 MB
  - 아이콘·한국어 버전 정보 포함
- 초기 DB: KOSPI **942종목**, 재무 **942종목**, 기본 관심종목 **4개**, 일별 종가 **3,712행**
- 데이터 기준일: **2026-10-23** (2023-01-02부터 전일 종가까지)
- 미리보기 엑셀:
  - `exports\preview_report.xlsx` — 5시트, `한장보고`·`전체보고`에 각각 차트 3개
  - `exports\preview_screen.xlsx` — `스크리닝 결과` 621종목

## 2. 전송 패키지

OneDrive 동기화를 쓰지 않고 USB·클라우드로 옮길 때는 아래 압축 파일을 사용합니다.

- `handoff\KOSPI_Insight_portable_20261024.zip` — 휴대용 실행본 (약 63 MB)
  - 압축을 풀면 `KOSPI Insight\KOSPI Insight.exe`가 나옵니다. 폴더 전체를 유지한 채 실행하세요.
- `handoff\KOSPI_Insight_source_20261024.zip` — 소스·DB·미리보기 (약 0.8 MB)
  - 개발을 이어서 할 때 사용합니다. `dist`는 포함하지 않습니다.

압축을 푼 뒤 첫 실행은 Windows Defender 검사 때문에 10~20초 걸릴 수 있습니다.

## 3. 다른 PC에서 바로 실행 (개발 환경 불필요)

1. OneDrive를 사용한다면 같은 Microsoft 계정으로 로그인한 뒤 `문서\기본 프로젝트` 폴더가 동기화될 때까지 기다립니다.
   - 폴더가 "온라인 전용"이면 프로젝트 폴더를 마우스 오른쪽 버튼 → **항상 이 장치에 유지**를 선택합니다.
2. `dist\KOSPI Insight\KOSPI Insight.exe`를 더블클릭합니다.
3. 첫 실행 시 `%LOCALAPPDATA%\KOSPIInsight\kospi_insight.db`가 내장 시드 DB로 자동 생성됩니다.
4. 네트워크가 있으면 시작 시 최신 시세·관심종목 종가를 조용히 갱신합니다.
5. Windows SmartScreen이 표시되면 **추가 정보 → 실행**을 선택합니다. (서명되지 않은 개인 빌드입니다.)

OneDrive를 쓰지 않는다면 `dist\KOSPI Insight` 폴더 전체를 USB나 클라우드로 복사해도 됩니다.
EXE만 복사하면 동작하지 않습니다. 반드시 폴더 전체를 복사하세요.

### 관심종목·설정을 그대로 가져가려면

- 소스 실행 DB: `data\kospi_insight.db`
- 휴대용 EXE DB: `%LOCALAPPDATA%\KOSPIInsight\kospi_insight.db`

휴대용 EXE의 관심종목·메모·캐시를 그대로 옮기려면 현재 PC의 위 DB 파일을 새 PC의 같은 경로에 복사한 뒤 실행합니다.
앱 설정(자동 갱신, 기본 차트 기간 등)은 Windows 레지스트리(`HKCU\Software\KOSPIInsight\KOSPI Insight`)에 저장되므로 자동으로 넘어가지 않습니다. 새 PC에서 다시 설정하면 됩니다.

## 4. 개발을 이어서 하는 경우

필요 환경: Windows 10/11 64비트, Python 3.12 이상

```powershell
# 프로젝트 폴더에서
py -m pip install -r requirements.txt
py -m kospi_insight
```

자동 갱신 없이 실행하려면:

```powershell
py -m kospi_insight --no-auto-refresh
```

`KOSPI_Insight_실행.bat`을 더블클릭해도 됩니다.

### 휴대용 EXE 다시 빌드

```powershell
py -m pip install -r requirements-dev.txt
py -m PyInstaller --noconfirm --clean KOSPIInsight.spec
```

또는 `build_portable.bat`을 실행합니다. 결과물은 `dist\KOSPI Insight\`입니다.

## 5. 폴더 구조

```text
main.py                     앱 진입점
KOSPIInsight.spec           PyInstaller 빌드 설정
build_portable.bat          휴대용 빌드 실행
KOSPI_Insight_실행.bat      소스 실행
requirements.txt            실행 의존성
requirements-dev.txt        빌드 의존성
kospi_insight/
  app.py                    QApplication 초기화, 로깅, 예외 처리
  main_window.py            셸, 탐색, 백그라운드 작업, 엑셀 내보내기
  naver.py                  네이버증권 공개 API 클라이언트
  database.py               SQLite 스키마와 캐시
  services.py               스크리닝·차트·종가 조회·갱신
  excel_report.py           5시트 엑셀 보고서와 차트
  charts.py                 커스텀 차트 위젯
  widgets.py                공통 UI 컴포넌트
  pages/                    대시보드·종목 분석·스크리너·즐겨찾기·설정
scripts/
  build_seed.py             초기 DB 생성
  capture_ui.py             UI 캡처
  smoke_interactions.py     상호작용 테스트 54개
  generate_previews.py      미리보기 엑셀 재생성
assets/
  seed_kospi.db             배포용 초기 DB
  app_icon.ico/.png         앱 아이콘
  check_white.png, chevron_*.png
data/
  kospi_insight.db          소스 실행용 DB
exports/
  preview_report.xlsx       관심종목 보고서 예시
  preview_screen.xlsx       스크리너 결과 예시
```

## 6. 데이터·경로 규칙

| 구분 | 경로 |
| --- | --- |
| 소스 실행 DB | `data\kospi_insight.db` |
| 휴대용 EXE DB | `%LOCALAPPDATA%\KOSPIInsight\kospi_insight.db` |
| 휴대용 EXE 로그 | `%LOCALAPPDATA%\KOSPIInsight\kospi_insight.log` |
| 휴대용 EXE 엑셀 | 내 문서\`KOSPI 인사이트 내보내기` |
| 소스 엑셀 | `exports\` |

환경 변수로 경로를 바꿀 수 있습니다.

- `KOSPI_INSIGHT_DB` — SQLite DB 파일 경로
- `KOSPI_INSIGHT_DATA_DIR` — 로그·DB 폴더
- `KOSPI_INSIGHT_EXPORT_DIR` — 엑셀 내보내기 폴더
- `KOSPI_INSIGHT_NO_AUTO_REFRESH=1` — 시작 자동 갱신 비활성화

## 7. 구현 메모

- 데이터 출처는 **NAVER Finance / KRX 공개 데이터**이며 DART API 키는 사용하지 않습니다.
- 네이버 통합 API의 `lastClosePrice`는 **전일 종가**이고, 가장 최근 실제 종가는 `dealTrendInfos[0].closePrice`입니다.
- 일별 종가는 2023-01-02부터 `date.today() - 1`까지 요청하고, 네이버가 휴장일을 건너뜁니다.
- 재무제표의 매출액·영업이익·당기순이익은 **억원 단위**, 시가총액은 **원 단위**입니다.
- 스크리닝 재무 지표는 최근 확정 연간 실적(현재 2025 회계연도), PER·PBR·배당수익률은 현재 네이버 밸류에이션 기준입니다.
- 기본 스크리너 조건은 시가총액 1,000억원 이상입니다. 추가 조건: 부채비율, 영업이익률, PER, 매출액, ROE, 배당수익률, 당기순이익 흑자, 우선주 포함/제외.
- 엑셀 관심종목 보고서는 `한장보고`, `전체보고`, `일일종가`, `월별종가`, `연간데이터` 5개 시트이며, 앞의 두 시트에 네이티브 차트 3개씩 들어갑니다.
- 장기 작업은 단일 QThreadPool 작업으로 실행되며, 시작 자동 갱신은 진행 창 없이 조용히 실행됩니다.

## 8. 검증 명령

```powershell
# 상호작용 테스트 (54개)
py scripts\smoke_interactions.py

# 실제 Windows UI 캡처 (1440×920, 1180×760)
py scripts\capture_ui.py

# 미리보기 엑셀 재생성
py scripts\generate_previews.py
```

`scripts\smoke_interactions.py`는 `data\kospi_insight.db`를 임시 폴더로 복사해 사용하므로 원본 DB를 변경하지 않습니다.
다만 테스트와 UI 캡처 스크립트는 `QSettings`를 초기화하므로, 실행 후 앱 설정(자동 갱신·기본 차트 기간 등)이 기본값으로 돌아갈 수 있습니다.

## 9. 알려진 제한

- 네이버증권 공개 페이지·API 구조가 바뀌면 데이터 수집이 실패할 수 있습니다.
- 재무 데이터가 없는 종목은 스크리너에서 제외되거나 지표가 `–`로 표시됩니다.
- 전체 재무 갱신은 요청 제한을 피하기 위해 순차·소수 병렬로 처리하므로 수 분이 걸릴 수 있습니다.
- 우선주는 기본 포함이며 스크리너에서 제외할 수 있습니다.
- Windows 10/11 64비트 환경을 기준으로 합니다.
- 이 앱은 정보 제공용이며 투자 권유가 아닙니다.

## 10. AI 에이전트로 이어서 작업하기

1. 새 PC에서 OpenCode를 프로젝트 폴더에서 실행합니다.
2. "HANDOFF.md를 읽고 현재 상태를 파악한 뒤 이어서 작업해 줘"라고 요청합니다.
3. 필요하면 `py scripts\smoke_interactions.py`로 현재 상태를 먼저 확인합니다.

이전 대화의 맥락은 자동으로 넘어가지 않습니다. 위 문서와 소스·DB·빌드 산출물이 인계 자료입니다.
