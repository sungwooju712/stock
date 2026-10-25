# KOSPI 인사이트

KOSPI 전 종목의 2023년 이후 종가와 재무·밸류에이션 지표를 한 화면에서 살펴보는 Windows 데스크톱 앱입니다. 네이버증권의 공개 시세·재무 데이터를 사용하며 DART API 키는 필요하지 않습니다.

> 다른 PC로 옮기거나 개발을 이어서 할 때는 [`HANDOFF.md`](HANDOFF.md)를 먼저 읽으세요. GitHub 저장소에는 소스와 샘플 데이터만 포함되며, 휴대용 EXE·전송용 ZIP 같은 빌드 산출물은 포함하지 않습니다.

## 주요 기능

- **대시보드** — KOSPI 유니버스, 상승/하락 분포, 관심종목 최근 30거래일 수익률, 시가총액 상위 종목
- **종목 분석** — 전체기간·연간·월간·전일종가 차트, 최대 8개 종목 비교, 재무·밸류에이션 지표, 거래일별 종가 조회
- **스크리너** — 시가총액(기본 1,000억원), 부채비율, 영업이익률, PER, 매출액, ROE, 배당수익률, 당기순이익 흑자, 우선주 포함/제외 조건
- **즐겨찾기 관리** — 별칭·메모 인라인 수정, 순서 변경, 삭제, 종목 분석 열기
- **데이터·설정** — 시세/재무/관심종목 종가 갱신, 자동 갱신 설정, 기본 차트 기간, 데이터 경로 확인

기본 관심종목은 삼성전자, SK하이닉스, KB금융, 신한지주입니다. 첫 실행 시 내장된 KOSPI 942종목·재무 스냅샷을 복사하고, 네트워크가 연결되어 있으면 최신 시세와 관심종목 일별 종가를 자동으로 갱신합니다.

## 데이터 기준

- 종가: 2023-01-02부터 **전일 종가**까지
- 재무 지표: 최근 확정 연간 실적(현재 스냅샷 2025 회계연도)
- PER·PBR·배당수익률: 현재가 기준 네이버증권 밸류에이션
- 출처: NAVER Finance / KRX 공개 데이터
- 데이터 지연·오류 가능성이 있으며 투자 권유가 아닙니다.

## 실행 (소스)

Python 3.12 이상이 필요합니다.

```powershell
py -m pip install -r requirements.txt
py -m kospi_insight
```

또는 `KOSPI_Insight_실행.bat`을 더블클릭합니다.

개발용 옵션:

```powershell
py -m kospi_insight --no-auto-refresh
py -m kospi_insight --db C:\temp\test.db
```

## 휴대용 EXE 빌드

```powershell
py -m pip install -r requirements-dev.txt
py -m PyInstaller --noconfirm --clean KOSPIInsight.spec
```

또는 `build_portable.bat`을 실행합니다. 결과물은 `dist\KOSPI Insight\` 폴더이며, `KOSPI Insight.exe`를 더블클릭하면 설치 없이 실행됩니다. 폴더 전체를 USB나 다른 PC로 복사해도 됩니다.

- 실행 파일 아이콘과 Windows 파일 정보가 포함됩니다.
- `assets\seed_kospi.db`, 아이콘, 체크·화살표 이미지가 EXE에 함께 번들됩니다.
- 빌드 폴더는 `dist\KOSPI Insight\`이고, 삭제 후 다시 빌드해도 됩니다.

## 저장 위치

| 구분 | 경로 |
| --- | --- |
| 소스 실행 DB | `data\kospi_insight.db` |
| 배포 EXE DB | `%LOCALAPPDATA%\KOSPIInsight\kospi_insight.db` |
| 배포 EXE 로그 | `%LOCALAPPDATA%\KOSPIInsight\kospi_insight.log` |
| 배포 EXE 엑셀 | 내 문서\`KOSPI 인사이트 내보내기` |
| 소스 엑셀 | `exports\` |

환경 변수로 경로를 바꿀 수 있습니다.

- `KOSPI_INSIGHT_DB` — SQLite DB 파일 경로
- `KOSPI_INSIGHT_DATA_DIR` — 로그·DB 폴더
- `KOSPI_INSIGHT_EXPORT_DIR` — 엑셀 내보내기 폴더
- `KOSPI_INSIGHT_NO_AUTO_REFRESH=1` — 시작 자동 갱신 비활성화

## 엑셀 내보내기

관심종목 보고서는 다음 5개 시트로 저장됩니다.

1. `한장보고` — 요약 표와 3개 차트
2. `전체보고` — 상세 표와 3개 차트
3. `일일종가`
4. `월별종가`
5. `연간데이터`

스크리너 결과는 `스크리닝 결과` 시트로 저장됩니다. 종목 분석 화면의 `엑셀` 버튼은 해당 종목 보고서를 만듭니다.

## 개발 검증

```powershell
# UI 스크린샷 (실제 Windows 렌더링, 1440x920 및 1180x760)
py scripts\capture_ui.py

# 헤드리스 환경
py scripts\capture_ui.py --offscreen

# 상호작용 스모크 테스트 54개 항목
py scripts\smoke_interactions.py
```

## 프로젝트 구조

```text
kospi_insight/
  app.py            앱 초기화
  main_window.py    셸·탐색·백그라운드 작업·엑셀 내보내기
  naver.py          네이버증권 공개 API 클라이언트
  database.py       SQLite 스키마와 캐시
  services.py       스크리닝·차트·종가 조회·갱신
  excel_report.py   5시트 엑셀 보고서
  pages/            대시보드·종목 분석·스크리너·즐겨찾기·설정
  charts.py         커스텀 차트 위젯
  widgets.py        공통 UI 컴포넌트
scripts/
  build_seed.py     초기 DB 생성
  capture_ui.py     UI 캡처
  smoke_interactions.py  상호작용 테스트
assets/
  seed_kospi.db     배포용 초기 DB
  app_icon.*        앱 아이콘
```

## 알려진 제한

- 네이버증권 공개 페이지 구조가 바뀌면 데이터 수집이 실패할 수 있습니다.
- 재무 데이터가 없는 종목은 스크리너에서 제외되거나 지표가 `–`로 표시됩니다.
- 대량 재무 갱신은 네이버 요청 제한을 피하기 위해 순차·소수 병렬로 처리하므로 수 분이 걸릴 수 있습니다.
- 우선주는 기본적으로 포함되며 스크리너에서 제외할 수 있습니다.
- Windows 10/11 64비트 환경을 기준으로 합니다.
