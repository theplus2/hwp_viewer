"""
폴더 색인 및 파일 스캔 모듈
고속 색인을 위해 메타데이터만 빠르게 수집하고 텍스트는 필요시 추출
"""
import os
import json
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Callable
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


@dataclass
class FileInfo:
    """파일 정보를 담는 데이터 클래스"""
    file_path: str
    file_name: str
    folder_path: str
    folder_name: str
    extension: str
    size: int
    modified_time: float
    content: str = ""
    indexed: bool = False  # 텍스트 추출 완료 여부
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @staticmethod
    def from_dict(data: dict) -> 'FileInfo':
        # 이전 버전 호환
        if 'indexed' not in data:
            data['indexed'] = bool(data.get('content', ''))
        return FileInfo(**data)


class FolderIndexer:
    """폴더 색인 및 파일 스캔 클래스 - 고속 버전"""
    
    SUPPORTED_EXTENSIONS = {'.hwp', '.docx', '.txt'}
    
    def __init__(self, index_path: Optional[str] = None):
        if index_path is None:
            app_dir = os.path.join(os.path.expanduser("~"), ".hwp_instant_viewer")
            os.makedirs(app_dir, exist_ok=True)
            index_path = os.path.join(app_dir, "index.json")
        
        self.index_path = index_path
        self.indexed_folders: List[str] = []
        self.files: Dict[str, FileInfo] = {}
        self._lock = threading.Lock()
        
        self._load_index()
    
    def _load_index(self):
        """저장된 색인 불러오기"""
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.indexed_folders = data.get('folders', [])
                    files_data = data.get('files', {})
                    self.files = {
                        k: FileInfo.from_dict(v) for k, v in files_data.items()
                    }
            except Exception as e:
                print(f"색인 로드 실패: {e}")
                self.indexed_folders = []
                self.files = {}
    
    def _save_index(self):
        """색인 저장"""
        try:
            with self._lock:
                data = {
                    'folders': self.indexed_folders,
                    'files': {k: v.to_dict() for k, v in self.files.items()}
                }
                with open(self.index_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            print(f"색인 저장 실패: {e}")
    
    def add_folder(self, folder_path: str) -> bool:
        folder_path = os.path.abspath(folder_path)
        if not os.path.isdir(folder_path):
            return False
        if folder_path not in self.indexed_folders:
            self.indexed_folders.append(folder_path)
            self._save_index()
        return True
    
    def remove_folder(self, folder_path: str) -> bool:
        folder_path = os.path.abspath(folder_path)
        if folder_path in self.indexed_folders:
            self.indexed_folders.remove(folder_path)
            to_remove = [fp for fp in self.files.keys() if fp.startswith(folder_path)]
            for fp in to_remove:
                del self.files[fp]
            self._save_index()
            return True
        return False
    
    def scan_folder_fast(self, folder_path: str) -> List[str]:
        """폴더 내 파일들을 빠르게 스캔 (os.scandir 사용)"""
        found_files = []
        
        def scan_recursive(path):
            try:
                with os.scandir(path) as entries:
                    for entry in entries:
                        if entry.is_file(follow_symlinks=False):
                            ext = os.path.splitext(entry.name)[1].lower()
                            if ext in self.SUPPORTED_EXTENSIONS:
                                found_files.append(entry.path)
                        elif entry.is_dir(follow_symlinks=False) and not entry.name.startswith('.'):
                            scan_recursive(entry.path)
            except (PermissionError, OSError):
                pass
        
        scan_recursive(folder_path)
        return found_files
    
    def index_files_fast(
        self, 
        folder_path: str,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        extract_content: bool = False,
        max_workers: int = 4
    ) -> int:
        """
        고속 파일 색인 - 메타데이터만 빠르게 수집
        
        Args:
            folder_path: 색인할 폴더 경로
            progress_callback: 진행 콜백 (current, total, filename)
            extract_content: True면 텍스트도 추출 (느림)
            max_workers: 병렬 처리 스레드 수
        """
        files = self.scan_folder_fast(folder_path)
        total = len(files)
        indexed_count = 0
        
        if progress_callback:
            progress_callback(0, total, "스캔 완료, 색인 중...")
        
        def process_file(file_path):
            try:
                file_name = os.path.basename(file_path)
                stat = os.stat(file_path)
                
                # 이미 색인되어 있고 수정되지 않았으면 스킵
                if file_path in self.files:
                    existing = self.files[file_path]
                    if existing.modified_time == stat.st_mtime:
                        return None
                
                folder_path_part = os.path.dirname(file_path)
                folder_name = os.path.basename(folder_path_part)
                ext = os.path.splitext(file_name)[1].lower()
                
                content = ""
                if extract_content:
                    from .hwp_extractor import extract_text
                    content = extract_text(file_path)
                
                return FileInfo(
                    file_path=file_path,
                    file_name=file_name,
                    folder_path=folder_path_part,
                    folder_name=folder_name,
                    extension=ext,
                    size=stat.st_size,
                    modified_time=stat.st_mtime,
                    content=content,
                    indexed=extract_content
                )
            except Exception as e:
                return None
        
        # 병렬 처리로 속도 향상
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_file, fp): fp for fp in files}
            
            for i, future in enumerate(as_completed(futures)):
                file_path = futures[future]
                file_name = os.path.basename(file_path)
                
                if progress_callback:
                    progress_callback(i + 1, total, file_name)
                
                try:
                    result = future.result()
                    if result:
                        with self._lock:
                            self.files[file_path] = result
                        indexed_count += 1
                except Exception:
                    pass
        
        self._save_index()
        return indexed_count
    
    def index_files(
        self, 
        folder_path: str,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        force_reindex: bool = False
    ) -> int:
        """기존 API 호환 - 텍스트 추출 포함 색인"""
        return self.index_files_fast(
            folder_path, 
            progress_callback, 
            extract_content=True,  # 본문 검색을 위해 텍스트 추출
            max_workers=8
        )

    
    def scan_folder(self, folder_path: str) -> List[str]:
        """기존 API 호환"""
        return self.scan_folder_fast(folder_path)
    
    def index_all_folders(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        force_reindex: bool = False
    ) -> int:
        total_indexed = 0
        for folder in self.indexed_folders:
            if os.path.isdir(folder):
                total_indexed += self.index_files(folder, progress_callback, force_reindex)
        return total_indexed
    
    def get_files_in_folder(self, folder_path: str, include_subfolders: bool = True) -> List[FileInfo]:
        """특정 폴더 내의 색인된 파일들 반환"""
        folder_path = os.path.abspath(folder_path)
        
        if include_subfolders:
            return [
                info for info in self.files.values()
                if info.file_path.startswith(folder_path + os.sep) or
                   info.folder_path == folder_path
            ]
        else:
            return [
                info for info in self.files.values()
                if info.folder_path == folder_path
            ]
    
    def get_all_files(self) -> List[FileInfo]:
        """모든 색인된 파일 반환"""
        return list(self.files.values())
    
    def get_file_info(self, file_path: str) -> Optional[FileInfo]:
        """특정 파일 정보 반환"""
        return self.files.get(file_path)
    
    def extract_content_for_file(self, file_path: str) -> str:
        """특정 파일의 텍스트 추출 (지연 로딩)"""
        if file_path in self.files:
            file_info = self.files[file_path]
            if not file_info.indexed or not file_info.content:
                from .hwp_extractor import extract_text
                content = extract_text(file_path)
                file_info.content = content
                file_info.indexed = True
                self._save_index()
                return content
            return file_info.content
        return ""
