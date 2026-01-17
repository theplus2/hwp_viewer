@echo off
rem -------------------------------------------------
rem Windows 단일 실행 파일 빌드 스크립트
rem -------------------------------------------------
rem 가상환경 활성화 (필요 시)
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
rem PyInstaller 설치 확인
pip install --upgrade pyinstaller
rem 아이콘 파일이 있으면 사용
set ICON=assets\icon.ico
rem 프로젝트 루트 디렉터리로 이동
cd /d %~dp0..\
rem 빌드 실행 (아이콘 존재 여부에 따라 옵션 적용)
if exist %ICON% (
    python -m PyInstaller --onefile --windowed --icon %ICON% --name HWPViewer ^
        --distpath dist --workpath build main.py
) else (
    python -m PyInstaller --onefile --windowed --name HWPViewer ^
        --distpath dist --workpath build main.py
)
echo 빌드 완료. exe 파일은 dist\HWPViewer.exe 에 위치합니다.
