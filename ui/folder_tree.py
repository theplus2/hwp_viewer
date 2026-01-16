"""
폴더 트리 위젯
등록된 폴더만 표시하는 커스텀 트리 뷰
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QMenu, QMessageBox, QFileDialog, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QIcon


class FolderTreeWidget(QWidget):
    """
    등록된 폴더만 표시하는 폴더 트리
    - 폴더 추가 전에는 빈 상태
    - 폴더 추가 시 해당 폴더와 하위 폴더 표시
    - 폴더 클릭 시 파일 목록 표시 (색인 없이 바로)
    """
    
    folder_selected = pyqtSignal(str)  # 폴더 선택 시그널
    folder_added = pyqtSignal(str)     # 폴더 추가 시그널 (색인 요청)
    folder_removed = pyqtSignal(str)   # 폴더 제거 시그널
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.root_folders = []  # 등록된 루트 폴더들
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 헤더
        header = QLabel("📁 폴더 목록")
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
        
        # 버튼 영역
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(5)
        
        self.add_btn = QPushButton("+ 폴더 추가")
        self.add_btn.clicked.connect(self._on_add_folder)
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        btn_layout.addWidget(self.add_btn)
        
        self.remove_btn = QPushButton("- 제거")
        self.remove_btn.clicked.connect(self._on_remove_folder)
        self.remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        btn_layout.addWidget(self.remove_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 트리 위젯 (QTreeWidget 사용 - 커스텀 아이템 지원)
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setAnimated(True)
        self.tree_widget.setIndentation(20)
        self.tree_widget.itemClicked.connect(self._on_item_clicked)
        self.tree_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.tree_widget.setStyleSheet("""
            QTreeWidget {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                font-size: 13px;
            }
            QTreeWidget::item {
                padding: 5px;
            }
            QTreeWidget::item:hover {
                background-color: #2a2d2e;
            }
            QTreeWidget::item:selected {
                background-color: #094771;
            }
        """)
        
        layout.addWidget(self.tree_widget, 1)  # stretch factor 1
        
        # 안내 레이블 (고정 높이)
        self.empty_label = QLabel("📂 폴더를 추가하세요")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setFixedHeight(80)
        self.empty_label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 12px;
                padding: 20px;
                background-color: #1e1e1e;
                border: 1px dashed #3d3d3d;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.empty_label)
        
        # 빈 공간 채우기 위한 stretch
        layout.addStretch(1)
        
        self._update_empty_state()
    
    def _update_empty_state(self):
        """빈 상태 표시 업데이트"""
        if self.root_folders:
            self.empty_label.hide()
            self.tree_widget.show()
        else:
            self.empty_label.show()
            self.tree_widget.hide()
    
    def _on_add_folder(self):
        """폴더 추가 버튼 클릭"""
        folder = QFileDialog.getExistingDirectory(
            self, "폴더 선택", "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if folder:
            if folder not in self.root_folders:
                self.root_folders.append(folder)
                self._add_folder_to_tree(folder)
                self._update_empty_state()
                self.folder_added.emit(folder)  # 색인 시작 시그널
            else:
                QMessageBox.information(self, "알림", "이미 추가된 폴더입니다.")
    
    def _add_folder_to_tree(self, folder_path: str):
        """트리에 폴더 추가 (하위 폴더 포함)"""
        folder_name = os.path.basename(folder_path)
        file_count = self._count_files_in_folder(folder_path, recursive=False)
        root_item = QTreeWidgetItem([f"📁 {folder_name} ({file_count})"])
        root_item.setData(0, Qt.ItemDataRole.UserRole, folder_path)
        root_item.setData(0, Qt.ItemDataRole.UserRole + 1, True)  # is_root 표시
        
        # 하위 폴더 추가 (재귀)
        self._add_subfolders(root_item, folder_path)
        
        self.tree_widget.addTopLevelItem(root_item)
        root_item.setExpanded(True)
    
    def _count_files_in_folder(self, folder_path: str, recursive: bool = False) -> int:
        """폴더 내 지원 파일 개수 계산"""
        supported_ext = {'.hwp', '.docx', '.txt'}
        count = 0
        
        try:
            for entry in os.scandir(folder_path):
                if entry.is_file():
                    ext = os.path.splitext(entry.name)[1].lower()
                    if ext in supported_ext:
                        count += 1
                elif entry.is_dir() and recursive and not entry.name.startswith('.'):
                    count += self._count_files_in_folder(entry.path, recursive=True)
        except PermissionError:
            pass
        
        return count
    
    def _add_subfolders(self, parent_item: QTreeWidgetItem, folder_path: str, max_depth: int = 5, current_depth: int = 0):
        """하위 폴더를 재귀적으로 추가"""
        if current_depth >= max_depth:
            return
        
        try:
            for entry in sorted(os.scandir(folder_path), key=lambda e: e.name.lower()):
                if entry.is_dir() and not entry.name.startswith('.'):
                    file_count = self._count_files_in_folder(entry.path, recursive=False)
                    child_item = QTreeWidgetItem([f"📂 {entry.name} ({file_count})"])
                    child_item.setData(0, Qt.ItemDataRole.UserRole, entry.path)
                    parent_item.addChild(child_item)
                    
                    # 재귀적으로 하위 폴더 추가
                    self._add_subfolders(child_item, entry.path, max_depth, current_depth + 1)
        except PermissionError:
            pass
    
    def _on_remove_folder(self):
        """폴더 제거 버튼 클릭"""
        current_item = self.tree_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "알림", "제거할 폴더를 선택하세요.")
            return
        
        # 루트 폴더 찾기
        root_item = current_item
        while root_item.parent():
            root_item = root_item.parent()
        
        folder_path = root_item.data(0, Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(
            self, "확인",
            f"'{os.path.basename(folder_path)}'를 목록에서 제거하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if folder_path in self.root_folders:
                self.root_folders.remove(folder_path)
            
            index = self.tree_widget.indexOfTopLevelItem(root_item)
            self.tree_widget.takeTopLevelItem(index)
            
            self._update_empty_state()
            self.folder_removed.emit(folder_path)
    
    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """트리 아이템 클릭 - 바로 파일 목록 표시"""
        folder_path = item.data(0, Qt.ItemDataRole.UserRole)
        if folder_path:
            self.folder_selected.emit(folder_path)
    
    def _show_context_menu(self, position):
        """우클릭 컨텍스트 메뉴"""
        item = self.tree_widget.itemAt(position)
        if not item:
            return
        
        menu = QMenu()
        
        open_action = QAction("탐색기에서 열기", self)
        open_action.triggered.connect(lambda: self._open_in_explorer(item))
        menu.addAction(open_action)
        
        refresh_action = QAction("새로고침", self)
        refresh_action.triggered.connect(lambda: self._refresh_folder(item))
        menu.addAction(refresh_action)
        
        menu.exec(self.tree_widget.viewport().mapToGlobal(position))
    
    def _open_in_explorer(self, item: QTreeWidgetItem):
        """탐색기에서 폴더 열기"""
        import subprocess
        import platform
        
        folder_path = item.data(0, Qt.ItemDataRole.UserRole)
        
        if platform.system() == "Windows":
            os.startfile(folder_path)
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", folder_path])
        else:  # Linux
            subprocess.run(["xdg-open", folder_path])
    
    def _refresh_folder(self, item: QTreeWidgetItem):
        """폴더 새로고침"""
        # 루트 폴더 찾기
        root_item = item
        while root_item.parent():
            root_item = root_item.parent()
        
        folder_path = root_item.data(0, Qt.ItemDataRole.UserRole)
        
        # 기존 자식 제거
        root_item.takeChildren()
        
        # 다시 하위 폴더 추가
        self._add_subfolders(root_item, folder_path)
    
    def set_folders(self, folders: list):
        """폴더 목록 설정 (저장된 폴더 로드 시 사용)"""
        self.root_folders = []
        self.tree_widget.clear()
        
        for folder in folders:
            if os.path.isdir(folder):
                self.root_folders.append(folder)
                self._add_folder_to_tree(folder)
        
        self._update_empty_state()
    
    def get_folders(self) -> list:
        """등록된 폴더 목록 반환"""
        return self.root_folders.copy()
