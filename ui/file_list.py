"""
파일 목록 위젯
선택된 폴더의 HWP 파일들을 표시
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLineEdit, QLabel, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from core.indexer import FileInfo
from core.searcher import SearchResult


class FileListWidget(QWidget):
    """
    선택된 폴더의 HWP 파일 목록
    - 검색 시 매칭된 파일들 표시
    - 파일명 + 폴더 경로 표시
    - 검색어 언급 횟수 배지
    """
    
    file_selected = pyqtSignal(str)  # 파일 선택 시그널 (file_path)
    search_requested = pyqtSignal(str)  # 검색 요청 시그널 (query)
    clear_requested = pyqtSignal()  # 초기화 요청 시그널
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_files = []  # FileInfo 목록
        self._search_results = []  # SearchResult 목록
        self._current_folder = ""  # 현재 선택된 폴더
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 헤더
        header = QLabel("📄 파일 목록")
        header.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                padding: 8px;
                background-color: #2d2d2d;
                color: #ffffff;
                border-radius: 4px;
            }
        """)
        layout.addWidget(header)
        
        # 검색 영역
        search_layout = QHBoxLayout()
        search_layout.setSpacing(5)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 검색어 입력...")
        self.search_input.returnPressed.connect(self._on_search)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #007acc;
            }
        """)
        search_layout.addWidget(self.search_input)
        
        self.search_btn = QPushButton("검색")
        self.search_btn.clicked.connect(self._on_search)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
        """)
        search_layout.addWidget(self.search_btn)
        
        self.clear_btn = QPushButton("초기화")
        self.clear_btn.clicked.connect(self._on_clear_search)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        search_layout.addWidget(self.clear_btn)
        
        layout.addLayout(search_layout)
        
        # 폴더 내 검색 옵션
        from PyQt6.QtWidgets import QCheckBox
        self.folder_only_checkbox = QCheckBox("현재 폴더에서만 검색")
        self.folder_only_checkbox.setStyleSheet("""
            QCheckBox {
                color: #888888;
                font-size: 12px;
                padding: 2px 5px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #555555;
                background: #2d2d2d;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #007acc;
                background: #007acc;
                border-radius: 3px;
            }
        """)
        
        # 검색 범위 옵션 레이아웃
        scope_layout = QHBoxLayout()
        scope_layout.setSpacing(10)
        
        from PyQt6.QtWidgets import QCheckBox
        
        # 전체 폴더 검색 (기본 체크)
        self.search_all_checkbox = QCheckBox("전체 폴더에서 검색")
        self.search_all_checkbox.setChecked(True)
        self.search_all_checkbox.toggled.connect(self._on_search_all_toggled)
        self.search_all_checkbox.setStyleSheet("""
            QCheckBox {
                color: #888888;
                font-size: 12px;
                padding: 2px 5px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #555555;
                background: #2d2d2d;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #007acc;
                background: #007acc;
                border-radius: 3px;
            }
        """)
        scope_layout.addWidget(self.search_all_checkbox)
        
        # 현재 폴더에서만 검색
        self.folder_only_checkbox = QCheckBox("현재 폴더에서만 검색")
        self.folder_only_checkbox.toggled.connect(self._on_folder_only_toggled)
        self.folder_only_checkbox.setStyleSheet("""
            QCheckBox {
                color: #888888;
                font-size: 12px;
                padding: 2px 5px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #555555;
                background: #2d2d2d;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #007acc;
                background: #007acc;
                border-radius: 3px;
            }
        """)
        scope_layout.addWidget(self.folder_only_checkbox)
        scope_layout.addStretch()
        
        layout.addLayout(scope_layout)
        
        # 정렬 옵션 (가나다순 / 날짜순)
        sort_layout = QHBoxLayout()
        sort_layout.setSpacing(5)
        
        sort_label = QLabel("정렬:")
        sort_label.setStyleSheet("color: #888888; font-size: 12px;")
        sort_layout.addWidget(sort_label)
        
        self.sort_name_btn = QPushButton("가나다순")
        self.sort_name_btn.setCheckable(True)
        self.sort_name_btn.setChecked(True)  # 기본값
        self.sort_name_btn.clicked.connect(lambda: self._on_sort_changed('name'))
        self.sort_name_btn.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                padding: 4px 10px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:!checked {
                background-color: #555555;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
        """)
        sort_layout.addWidget(self.sort_name_btn)
        
        self.sort_date_btn = QPushButton("날짜순")
        self.sort_date_btn.setCheckable(True)
        self.sort_date_btn.clicked.connect(lambda: self._on_sort_changed('date'))
        self.sort_date_btn.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                padding: 4px 10px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:!checked {
                background-color: #555555;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
        """)
        sort_layout.addWidget(self.sort_date_btn)
        sort_layout.addStretch()
        
        layout.addLayout(sort_layout)
        self._current_sort = 'name'  # 현재 정렬 기준
        
        # 결과 카운트
        self.count_label = QLabel("파일 0개")
        self.count_label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 12px;
                padding: 2px 5px;
            }
        """)
        layout.addWidget(self.count_label)

        
        # 파일 리스트
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        # 우클릭 컨텍스트 메뉴 설정
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #2d2d2d;
            }
            QListWidget::item:hover {
                background-color: #2a2d2e;
            }
            QListWidget::item:selected {
                background-color: #094771;
            }
        """)
        layout.addWidget(self.list_widget)
    
    def _on_search(self):
        """검색 버튼 클릭"""
        query = self.search_input.text().strip()
        if query:
            self.search_requested.emit(query)
    
    def _on_clear_search(self):
        """검색 초기화"""
        self.search_input.clear()
        self._search_results = []
        self._display_files(self._current_files)
        self.clear_requested.emit()  # 텍스트 뷰어도 초기화
    
    def _on_search_all_toggled(self, checked: bool):
        """전체 폴더 검색 토글"""
        if checked:
            self.folder_only_checkbox.setChecked(False)
    
    def _on_folder_only_toggled(self, checked: bool):
        """현재 폴더만 검색 토글"""
        if checked:
            self.search_all_checkbox.setChecked(False)
    
    def _on_sort_changed(self, sort_type: str):
        """정렬 기준 변경"""
        self._current_sort = sort_type
        
        # 버튼 상태 업데이트
        self.sort_name_btn.setChecked(sort_type == 'name')
        self.sort_date_btn.setChecked(sort_type == 'date')
        
        # 현재 표시된 목록 재정렬 (항상 실행)
        if self._search_results:
            self._display_search_results(self._search_results)
        elif self._current_files:
            self._display_files(self._current_files)
    
    def _sort_list(self, items: list) -> list:
        """목록 정렬 (FileInfo 또는 SearchResult)"""
        if not items:
            return items
        
        try:
            if self._current_sort == 'date':
                # 날짜순 (최신 먼저)
                def get_mtime(item):
                    try:
                        if hasattr(item, 'file_info'):  # SearchResult
                            return getattr(item.file_info, 'modified_time', 0) or 0
                        elif hasattr(item, 'modified_time'):  # FileInfo
                            return item.modified_time or 0
                    except:
                        pass
                    return 0
                return sorted(items, key=get_mtime, reverse=True)
            else:
                # 가나다순
                def get_name(item):
                    try:
                        if hasattr(item, 'file_info'):  # SearchResult
                            return getattr(item.file_info, 'file_name', '').lower()
                        elif hasattr(item, 'file_name'):  # FileInfo
                            return item.file_name.lower()
                    except:
                        pass
                    return ""
                return sorted(items, key=get_name)
        except Exception:
            return items
    
    def _show_context_menu(self, position):
        """파일 아이템 우클릭 컨텍스트 메뉴"""
        item = self.list_widget.itemAt(position)
        if not item:
            return
        
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path:
            return
        
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2d2d2d;
                color: #d4d4d4;
                border: 1px solid #3d3d3d;
            }
            QMenu::item:selected {
                background-color: #094771;
            }
        """)
        
        # 탐색기에서 열기 액션
        open_explorer_action = QAction("📂 탐색기에서 열기", self)
        open_explorer_action.triggered.connect(lambda: self._open_in_explorer(file_path))
        menu.addAction(open_explorer_action)
        
        menu.exec(self.list_widget.mapToGlobal(position))
    
    def _open_in_explorer(self, file_path: str):
        """탐색기에서 파일 위치 열기"""
        import subprocess
        # Windows 경로 형식으로 정규화 (슬래시를 백슬래시로)
        file_path = os.path.normpath(file_path)
        folder_path = os.path.dirname(file_path)
        try:
            # Windows에서 탐색기 열고 파일 선택
            subprocess.run(['explorer', '/select,', file_path], check=False)
        except Exception:
            try:
                # 폴백: 폴더만 열기
                os.startfile(folder_path)
            except Exception:
                pass
    
    def _on_item_clicked(self, item: QListWidgetItem):
        """파일 아이템 클릭"""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path:
            self.file_selected.emit(file_path)
    
    def set_files(self, files: list):
        """파일 목록 설정 (FileInfo 또는 SearchResult 목록)"""
        self._current_files = files
        # 현재 폴더 설정 (검색 범위용)
        if files and isinstance(files[0], FileInfo):
            self._current_folder = files[0].folder_path
        self._display_files(files)
    
    def set_files_direct(self, files: list, folder_path: str = ""):
        """파일 목록 설정 (dict 형식) - 폴더 직접 스캔 결과용"""
        self.list_widget.clear()
        self._current_files = []
        self._current_folder = folder_path
        
        for file_dict in files:
            item = QListWidgetItem()
            icon = self._get_file_icon(file_dict.get('extension', ''))
            text = f"{icon} {file_dict['file_name']}\n   📁 {file_dict['folder_name']}"
            item.setText(text)
            item.setData(Qt.ItemDataRole.UserRole, file_dict['file_path'])
            self.list_widget.addItem(item)
        
        self.count_label.setText(f"파일 {len(files)}개")
    
    def set_search_results(self, results: list):
        """검색 결과 설정 (SearchResult 목록)"""
        self._search_results = results
        self._display_search_results(results)
    
    def _display_files(self, files: list):
        """파일 목록 표시"""
        self.list_widget.clear()
        
        # 정렬 적용
        sorted_files = self._sort_list(files)
        
        for file_info in sorted_files:
            if isinstance(file_info, FileInfo):
                item = self._create_file_item(file_info)
            elif isinstance(file_info, SearchResult):
                item = self._create_search_result_item(file_info)
            else:
                continue
            
            self.list_widget.addItem(item)
        
        self.count_label.setText(f"파일 {len(files)}개")
    
    def _display_search_results(self, results: list):
        """검색 결과 표시"""
        self.list_widget.clear()
        
        # 정렬 적용
        sorted_results = self._sort_list(results)
        
        for result in sorted_results:
            item = self._create_search_result_item(result)
            self.list_widget.addItem(item)
        
        self.count_label.setText(f"검색 결과 {len(results)}개")
    
    def _create_file_item(self, file_info: FileInfo) -> QListWidgetItem:
        """일반 파일 아이템 생성"""
        item = QListWidgetItem()
        
        # 확장자에 따른 아이콘
        icon = self._get_file_icon(file_info.extension)
        
        # 표시 텍스트: 파일명 + 폴더 경로
        text = f"{icon} {file_info.file_name}\n   📁 {file_info.folder_name}"
        item.setText(text)
        item.setData(Qt.ItemDataRole.UserRole, file_info.file_path)
        
        return item
    
    def _create_search_result_item(self, result: SearchResult) -> QListWidgetItem:
        """검색 결과 아이템 생성"""
        item = QListWidgetItem()
        
        file_info = result.file_info
        icon = self._get_file_icon(file_info.extension)
        
        # 표시 텍스트: 파일명 + 매칭 횟수 + 폴더 경로
        match_badge = f"[{result.match_count}회]" if result.match_count > 0 else ""
        text = f"{icon} {file_info.file_name} {match_badge}\n   📁 {file_info.folder_name}"
        
        item.setText(text)
        item.setData(Qt.ItemDataRole.UserRole, file_info.file_path)
        
        # 매칭된 위치에 따라 배경색 변경
        if result.matched_in_filename:
            item.setBackground(Qt.GlobalColor.darkYellow)
        
        return item
    
    def _get_file_icon(self, extension: str) -> str:
        """확장자에 따른 아이콘 반환"""
        icons = {
            '.hwp': '📝',
            '.hwpx': '📝',
            '.docx': '📄'
        }
        return icons.get(extension.lower(), '📄')
    
    def get_current_query(self) -> str:
        """현재 검색어 반환"""
        return self.search_input.text().strip()
    
    def get_current_folder(self) -> str:
        """현재 선택된 폴더 반환"""
        return self._current_folder
    
    def is_folder_only_search(self) -> bool:
        """현재 폴더만 검색 옵션 체크 여부"""
        return self.folder_only_checkbox.isChecked()
    
    def is_search_all(self) -> bool:
        """전체 폴더 검색 옵션 체크 여부"""
        return self.search_all_checkbox.isChecked()
