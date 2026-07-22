# PDF변환기

Windows 10/11에서 HWP/HWPX, Excel, Word, PowerPoint 문서를 개별 PDF로 일괄 변환하기 위한 데스크톱 프로그램입니다.

## 현재 구현 범위 (v0.3.0 개발 중)

- PySide6 기반 GUI
- 파일 여러 개 추가
- 폴더 및 하위 폴더 검색
- 드래그 앤 드롭
- 파일 삭제, 전체 삭제, 순서 위/아래 이동
- 파일별 페이지 범위 직접 입력
- 저장 폴더 선택
- 품질 및 컬러/흑백 선택 UI
- 전체 진행률 및 파일별 상태 표시 기반
- 설정 JSON 저장
- TXT 로그 기반
- 확장자별 변환기 플러그인 구조
- Word, Excel, PowerPoint COM PDF 변환
- HWP/HWPX 한글 자동화 PDF 변환
- 여러 파일 변환 중 실패한 파일을 기록하고 다음 파일 계속 처리
- 동일한 PDF 파일명은 `(1)`, `(2)` 자동 증가
- 페이지 범위(`1,3-5`) 적용
- PowerPoint 숨김 슬라이드 제외
- 일시정지 및 중지
- 모든 지원 문서의 컬러/흑백 PDF 출력
- 흑백 변환 시 검색 가능한 텍스트와 벡터 그래픽 유지
- 최소용량 선택 시 PDF 이미지 압축

한글 자동화 보안 모듈이 설치되지 않은 PC에서는 첫 변환 때 한글의 파일 접근 승인 창이 표시될 수 있습니다.
변환 결과 상세 화면과 독립 실행형 EXE 패키징은 다음 개발 단계에서 연결합니다.

## 개발 환경

- Python 3.11 이상
- Windows 10/11 64비트
- PySide6
- pywin32

## 실행

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
pdf-converter
```

## 빌드 예정

```powershell
pyinstaller --noconfirm --windowed --name PDF변환기 src/pdf_converter/main.py
```
