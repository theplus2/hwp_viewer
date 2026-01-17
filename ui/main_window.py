"""
메인 윈도우
3-패널 레이아웃: 폴더 트리 + 파일 목록 + 텍스트 뷰어
"""
import os
import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QMessageBox, QProgressDialog, QApplication, QStatusBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.folder_tree import FolderTreeWidget
from ui.file_list import FileListWidget
from ui.text_viewer import TextViewerWidget
from core.indexer import FolderIndexer
from core.searcher import HWPSearcher


class IndexWorker(QThread):
    """백그라운드 색인 작업 스레드"""
    progress = pyqtSignal(int, int, str)  # current, total, filename
    finished = pyqtSignal(int)  # indexed_count
    
    def __init__(self, indexer: FolderIndexer, folder_path: str):
        super().__init__()
        self.indexer = indexer
        self.folder_path = folder_path
    
    def run(self):
        count = self.indexer.index_files(
            self.folder_path,
            progress_callback=lambda c, t, f: self.progress.emit(c, t, f)
        )
        self.finished.emit(count)


class MainWindow(QMainWindow):
    """
    메인 윈도우 - 3-패널 레이아웃
    
    ┌──────────┬────────────┬──────────────────────┐
    │  폴더    │  파일      │                      │
    │  트리    │  목록      │    텍스트 뷰어       │
    │          │            │                      │
    │  200px   │  300px     │    나머지 공간       │
    └──────────┴────────────┴──────────────────────┘
    """
    
    def __init__(self):
        super().__init__()
        
        # Core 모듈 초기화
        self.indexer = FolderIndexer()
        self.searcher = HWPSearcher(self.indexer)  # FTS5 검색용 indexer 전달
        
        self._setup_ui()
        self._setup_menu()
        self._connect_signals()
        self._load_saved_folders()
    
    def _setup_ui(self):
        """UI 초기화"""
        self.setWindowTitle("HWP Instant Viewer v2.2.2")
        self.setMinimumSize(1200, 700)
        self.resize(1400, 800)
        
        # 다크 테마 스타일
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QSplitter::handle {
                background-color: #3d3d3d;
                width: 2px;
            }
            QSplitter::handle:hover {
                background-color: #007acc;
            }
        """)
        
        # 중앙 위젯
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        
        # 3-패널 스플리터
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 패널 1: 폴더 트리
        self.folder_tree = FolderTreeWidget()
        self.splitter.addWidget(self.folder_tree)
        
        # 패널 2: 파일 목록
        self.file_list = FileListWidget()
        self.splitter.addWidget(self.file_list)
        
        # 패널 3: 텍스트 뷰어
        self.text_viewer = TextViewerWidget()
        self.splitter.addWidget(self.text_viewer)
        
        # 초기 크기 비율 설정
        self.splitter.setSizes([200, 300, 700])
        
        layout.addWidget(self.splitter)
        
        # 상태바
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #007acc;
                color: white;
                font-size: 12px;
                padding: 5px;
            }
        """)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("준비됨")
        
        # 개발자 정보 영구 표시
        from PyQt6.QtWidgets import QLabel
        developer_label = QLabel("Developed by 윤영천 목사")
        developer_label.setStyleSheet("color: white; padding-right: 10px;")
        self.status_bar.addPermanentWidget(developer_label)
        
        # 텍스트 뷰어 초기화
        self.text_viewer.clear()
    
    def _setup_menu(self):
        """메뉴바 설정"""
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #2d2d2d;
                color: #ffffff;
                padding: 5px;
            }
            QMenuBar::item:selected {
                background-color: #094771;
            }
            QMenu {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
            }
            QMenu::item:selected {
                background-color: #094771;
            }
        """)
        
        # 파일 메뉴
        file_menu = menubar.addMenu("파일")
        
        add_folder_action = QAction("폴더 추가", self)
        add_folder_action.setShortcut(QKeySequence.StandardKey.Open)
        add_folder_action.triggered.connect(self.folder_tree._on_add_folder)
        file_menu.addAction(add_folder_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("종료", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 색인 메뉴
        index_menu = menubar.addMenu("색인")
        
        reindex_action = QAction("전체 재색인", self)
        reindex_action.setShortcut(QKeySequence.StandardKey.Refresh)
        reindex_action.triggered.connect(self._reindex_all)
        index_menu.addAction(reindex_action)
        
        index_menu.addSeparator()
        
        reset_db_action = QAction("전체 DB 초기화", self)
        reset_db_action.triggered.connect(self._reset_database)
        index_menu.addAction(reset_db_action)
        
        # 도움말 메뉴
        help_menu = menubar.addMenu("도움말")
        
        about_action = QAction("정보", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        
        help_menu.addSeparator()
        
        donation_action = QAction("후원문의", self)
        donation_action.triggered.connect(self._show_donation)
        help_menu.addAction(donation_action)
    
    def _connect_signals(self):
        """시그널 연결"""
        # 폴더 트리 시그널
        self.folder_tree.folder_selected.connect(self._on_folder_selected)
        self.folder_tree.folder_added.connect(self._on_folder_added)
        self.folder_tree.folder_removed.connect(self._on_folder_removed)
        
        # 파일 목록 시그널
        self.file_list.file_selected.connect(self._on_file_selected)
        self.file_list.search_requested.connect(self._on_search_requested)
        self.file_list.clear_requested.connect(self._on_clear_requested)
    
    def _on_clear_requested(self):
        """검색 초기화 시 텍스트 뷰어도 초기화"""
        self.text_viewer.clear()
        self.status_bar.showMessage("검색 초기화됨")
    
    def _load_saved_folders(self):
        """저장된 폴더 목록 로드"""
        folders = self.indexer.indexed_folders
        self.folder_tree.set_folders(folders)
        
        if folders:
            self.status_bar.showMessage(f"등록된 폴더: {len(folders)}개")
    
    def _on_folder_selected(self, folder_path: str):
        """폴더 선택 시 - 바로 파일 목록 표시 (탐색기 스타일)"""
        self.status_bar.showMessage(f"폴더: {folder_path}")
        
        # 1. 색인된 데이터가 있는지 먼저 확인 (본문 포함 정보를 위해)
        indexed_files = self.indexer.get_files_in_folder(folder_path, include_subfolders=True)
        
        if indexed_files:
            # 색인된 데이터 사용
            self.file_list.set_files(indexed_files)
        else:
            # 색인되지 않은 경우 디스크 직접 스캔 (메타데이터만)
            files = self._scan_folder_files(folder_path)
            self.file_list.set_files_direct(files, folder_path)
    
    def _scan_folder_files(self, folder_path: str, include_subfolders: bool = True) -> list:
        """폴더 내 지원 파일들 스캔 (하위 폴더 포함 옵션)"""
        supported_ext = {'.hwp', '.hwpx', '.docx'}
        files = []
        
        def scan_recursive(path):
            try:
                for entry in os.scandir(path):
                    try:
                        if entry.is_file():
                            ext = os.path.splitext(entry.name)[1].lower()
                            if ext in supported_ext:
                                try:
                                    size = entry.stat().st_size
                                except (PermissionError, OSError):
                                    size = 0
                                files.append({
                                    'file_path': entry.path,
                                    'file_name': entry.name,
                                    'folder_path': os.path.dirname(entry.path),
                                    'folder_name': os.path.basename(os.path.dirname(entry.path)),
                                    'extension': ext,
                                    'size': size
                                })
                        elif entry.is_dir() and include_subfolders and not entry.name.startswith('.'):
                            scan_recursive(entry.path)
                    except (PermissionError, OSError):
                        pass
            except (PermissionError, OSError):
                pass
        
        scan_recursive(folder_path)
        return sorted(files, key=lambda f: f['file_name'].lower())
    
    def _on_folder_added(self, folder_path: str):
        """폴더 추가 시"""
        self.indexer.add_folder(folder_path)
        
        reply = QMessageBox.question(
            self, "색인 진행",
            f"'{os.path.basename(folder_path)}' 폴더가 추가되었습니다.\n지금 색인을 진행할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._index_folder(folder_path)
    
    def _on_folder_removed(self, folder_path: str):
        """폴더 제거 시 - DB에서도 해당 폴더 색인 삭제"""
        self.indexer.remove_folder(folder_path)
        self.file_list.set_files_direct([], "")  # 파일 목록 초기화
        self.text_viewer.clear()  # 텍스트 뷰어 초기화
        self.status_bar.showMessage(f"폴더 및 색인 삭제됨: {os.path.basename(folder_path)}")
    
    def _on_file_selected(self, file_path: str):
        """파일 선택 시 - HTML로 추출하여 표/이미지 표시"""
        self.status_bar.showMessage(f"파일: {os.path.basename(file_path)}")
        
        # 파일 확장자에 따라 적절한 추출기 사용
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.hwp' or ext == '.hwpx':
            from core.hwp_extractor import extract_html
            html_content, images = extract_html(file_path)
        elif ext == '.docx':
            from core.hwp_extractor import extract_html_from_docx
            html_content, images = extract_html_from_docx(file_path)
        else:
            html_content, images = "<p>지원하지 않는 파일 형식입니다.</p>", []
        
        query = self.file_list.get_current_query()
        self.text_viewer.set_content(file_path, html_content, images, query)

    
    def _on_search_requested(self, query: str):
        """검색 요청 시 - FTS5 전문 검색 사용"""
        self.status_bar.showMessage(f"검색 중: {query}")
        
        # 폴더 내 검색 옵션 확인
        folder_only = self.file_list.is_folder_only_search()
        search_all = self.file_list.is_search_all()
        current_folder = self.file_list.get_current_folder()
        
        # 검색 범위 결정
        search_folder = None
        if folder_only and current_folder:
            search_folder = current_folder
            self.status_bar.showMessage(f"'{os.path.basename(current_folder)}' 폴더에서 검색 중...")
        else:
            self.status_bar.showMessage(f"전체 폴더에서 검색 중...")
        
        # FTS5 검색 사용 (초고속)
        results = self.searcher.search_fts(query, search_folder)
        
        # FTS5 결과가 없으면 기존 방식으로 폴백
        if not results:
            if folder_only and current_folder:
                all_files = self.indexer.get_files_in_folder(current_folder, include_subfolders=True)
            elif search_all:
                all_files = self.indexer.get_all_files()
            else:
                if current_folder:
                    all_files = self.indexer.get_files_in_folder(current_folder, include_subfolders=True)
                else:
                    all_files = self.indexer.get_all_files()
            
            results = self.searcher.search(query, all_files)
        
        # 결과 표시
        self.file_list.set_search_results(results)
        
        # 현재 뷰어에 표시된 텍스트에 하이라이트 적용
        self.text_viewer.set_query(query)
        
        scope = f"'{os.path.basename(current_folder)}' 폴더" if folder_only and current_folder else "전체"
        self.status_bar.showMessage(f"'{query}' 검색 완료: {len(results)}개 파일 ({scope})")
    
    def _index_folder(self, folder_path: str):
        """폴더 색인 (프로그레스 다이얼로그 표시)"""
        # 프로그레스 다이얼로그
        progress = QProgressDialog("색인 중...", "취소", 0, 100, self)
        progress.setWindowTitle("색인 진행")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setStyleSheet("""
            QProgressDialog {
                background-color: #2d2d2d;
                color: #ffffff;
            }
            QProgressDialog QLabel {
                color: #ffffff;
                font-size: 13px;
            }
            QPushButton {
                color: #ffffff;
                background-color: #555555;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QProgressBar {
                border: 1px solid #3d3d3d;
                border-radius: 3px;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #007acc;
            }
        """)
        progress.show()
        
        # 백그라운드 스레드에서 색인
        self.index_worker = IndexWorker(self.indexer, folder_path)
        
        def on_progress(current, total, filename):
            if total > 0:
                progress.setValue(int(current / total * 100))
                progress.setLabelText(f"색인 중: {filename}")
        
        def on_finished(count):
            progress.close()
            self.status_bar.showMessage(f"색인 완료: {count}개 파일")
            
            # 파일 목록 갱신
            files = self.indexer.get_files_in_folder(folder_path)
            self.file_list.set_files(files)
            
            QMessageBox.information(
                self, "색인 완료",
                f"총 {count}개 파일이 색인되었습니다."
            )
        
        self.index_worker.progress.connect(on_progress)
        self.index_worker.finished.connect(on_finished)
        self.index_worker.start()
    
    def _reindex_all(self):
        """전체 재색인"""
        folders = self.indexer.indexed_folders
        
        if not folders:
            QMessageBox.warning(self, "알림", "등록된 폴더가 없습니다.")
            return
        
        reply = QMessageBox.question(
            self, "전체 재색인",
            f"등록된 {len(folders)}개 폴더를 모두 재색인합니다.\n계속하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            for folder in folders:
                if os.path.isdir(folder):
                    self._index_folder(folder)
    
    def _reset_database(self):
        """전체 DB 초기화"""
        reply = QMessageBox.warning(
            self, "전체 DB 초기화",
            "모든 색인 데이터와 폴더 목록이 삭제됩니다.\n이 작업은 되돌릴 수 없습니다.\n\n계속하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 색인 데이터 초기화 (SQLite)
            self.indexer.reset_database()
            
            # UI 초기화
            self.folder_tree.set_folders([])
            self.file_list.set_files_direct([], "")
            self.text_viewer.clear()
            
            self.status_bar.showMessage("전체 DB가 초기화되었습니다.")
            QMessageBox.information(self, "완료", "전체 DB가 초기화되었습니다.")
    
    def _show_about(self):
        """정보 다이얼로그"""
        QMessageBox.about(
            self, "HWP Instant Viewer",
            "HWP Instant Viewer v2.2.2\n\n"
            "HWP 파일을 빠르게 탐색하고 검색하는 도구\n\n"
            "기능:\n"
            "• 폴더 트리 탐색\n"
            "• HWP/HWPX/DOCX 파일 색인\n"
            "• FTS5 전문 검색 (초고속)\n"
            "• 검색어 하이라이트\n"
            "• 표 텍스트 추출\n"
            "• 파일 우클릭 탐색기 열기\n\n"
            "Developed by 윤영천 목사\n"
            "Built with PyQt6 + SQLite\n\n"
            "문의 http://blog.naver.com/theplus2"
        )
    
    def _show_donation(self):
        """후원 안내 다이얼로그"""
        QMessageBox.information(
            self, "후원 안내",
            "안녕하세요! 개발하는데 많은 노력과 시간이 들어갔습니다.\n"
            "커피 한 잔의 여유를 즐길 수 있는 작은 후원의 마음을 전해주시면 감사드리겠습니다.\n\n"
            "하나은행 670-910177-84807"
        )
    
    def closeEvent(self, event):
        """창 닫기 이벤트"""
        reply = QMessageBox.question(
            self, "종료 확인",
            "프로그램을 종료하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()
