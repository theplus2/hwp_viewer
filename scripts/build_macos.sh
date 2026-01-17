#!/usr/bin/env bash
# -------------------------------------------------
# macOS 단일 실행 파일 빌드 스크립트 (.app 및 단일 바이너리)
# -------------------------------------------------

# 프로젝트 루트 디렉터리로 이동 (스크립트 위치 기준)
cd "$(dirname "$0")/.."

# 가상환경 활성화 (있을 경우)
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# PyInstaller 및 필성 패키지 설치 확인
pip install --upgrade pyinstaller

# 아이콘 파일 경로 (실제 .icns 파일이 있으면 사용)
# TIP: png2icns 또는 sips를 사용하여 .ico를 .icns로 변환 가능
ICON="assets/icon.icns"

if [ -f "$ICON" ]; then
    python3 -m PyInstaller --onefile --windowed --icon "$ICON" --name HWPViewer \
        --distpath dist --workpath build main.py
else
    echo "경고: assets/icon.icns 파일이 없습니다. 기본 아이콘으로 빌드합니다."
    python3 -m PyInstaller --onefile --windowed --name HWPViewer \
        --distpath dist --workpath build main.py
fi

echo "빌드 완료. 실행 파일은 dist/HWPViewer.app 또는 dist/HWPViewer 에 위치합니다."
