"""
HWP Instant Viewer
메인 진입점
"""
import sys
import os

# 프로젝트 루트를 path에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt

from ui.main_window import MainWindow


def main():
    # High DPI 지원
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("HWP Instant Viewer")
    app.setApplicationVersion("2.3.5")
    
    # 아이콘 설정 (있으면)
    icon_path = os.path.join(project_root, "resources", "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # 전역 스타일
    app.setStyleSheet("""
        * {
            font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
        }
        QToolTip {
            background-color: #2d2d2d;
            color: #ffffff;
            border: 1px solid #3d3d3d;
            padding: 5px;
        }
    """)
    
    # 메인 윈도우 생성 및 표시
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
