# PDF변환기

Windows 10/11에서 HWP/HWPX, Excel, Word, PowerPoint 문서를 개별 PDF로 일괄 변환하기 위한 데스크톱 프로그램입니다.

## 현재 구현 범위 (v0.1.0)

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

문서별 COM 변환 엔진은 다음 개발 단계에서 연결합니다.

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
