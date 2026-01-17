"""
폴더 색인 및 파일 스캔 모듈 - SQLite 기반
고속 색인을 위해 메타데이터만 빠르게 수집하고 텍스트는 필요시 추출
"""
import os
import json
from typing import List, Dict, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 새 데이터베이스 모듈 사용
from .database import DatabaseManager, FileInfo

# FileInfo를 re-export하여 기존 코드 호환성 유지
__all__ = ['FolderIndexer', 'FileInfo']


class FolderIndexer:
    """
    폴더 색인 및 파일 스캔 클래스 - SQLite 기반
    
    변경사항:
    - JSON 대신 SQLite 데이터베이스 사용
    - FTS5 전문 검색 지원
    - 배치 단위 색인으로 성능 최적화
    - 기존 API 완전 호환
    """
    
    SUPPORTED_EXTENSIONS = {'.hwp', '.hwpx', '.docx'}
    BATCH_SIZE = 500  # 배치 저장 크기
    
    def __init__(self, db_path: Optional[str] = None):
        """
        FolderIndexer 초기화
        
        Args:
            db_path: 데이터베이스 경로 (None이면 기본 경로 사용)
        """
        self._db = DatabaseManager(db_path)
        self._lock = threading.Lock()
        
        # 기존 JSON 데이터 마이그레이션 확인
        self._migrate_from_json_if_needed()
    
    def _migrate_from_json_if_needed(self):
        """기존 JSON 색인 데이터를 SQLite로 마이그레이션"""
        app_dir = os.path.join(os.path.expanduser("~"), ".hwp_instant_viewer")
        json_path = os.path.join(app_dir, "index.json")
        migrated_flag = os.path.join(app_dir, ".migrated")
        
        # 이미 마이그레이션 완료된 경우
        if os.path.exists(migrated_flag):
            return
        
        # JSON 파일이 없으면 마이그레이션 불필요
        if not os.path.exists(json_path):
            # 마이그레이션 완료 표시
            try:
                with open(migrated_flag, 'w') as f:
                    f.write('done')
            except:
                pass
            return
        
        try:
            print("기존 색인 데이터를 새 데이터베이스로 마이그레이션 중...")
            
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 폴더 마이그레이션
            folders = data.get('folders', [])
            for folder in folders:
                self._db.add_folder(folder)
            
            # 파일 마이그레이션 (배치 단위)
            files_data = data.get('files', {})
            file_infos = []
            
            for file_path, file_data in files_data.items():
                try:
                    # 이전 버전 호환
                    if 'indexed' not in file_data:
                        file_data['indexed'] = bool(file_data.get('content', ''))
                    
                    file_info = FileInfo(**file_data)
                    file_infos.append(file_info)
                    
                    # 배치 저장
                    if len(file_infos) >= self.BATCH_SIZE:
                        self._db.add_files_batch(file_infos)
                        file_infos = []
                except Exception as e:
                    print(f"파일 마이그레이션 스킵: {file_path} - {e}")
            
            # 남은 파일 저장
            if file_infos:
                self._db.add_files_batch(file_infos)
            
            # 마이그레이션 완료 표시
            with open(migrated_flag, 'w') as f:
                f.write('done')
            
            print(f"마이그레이션 완료: {len(folders)}개 폴더, {len(files_data)}개 파일")
            
        except Exception as e:
            print(f"마이그레이션 실패: {e}")
    
    @property
    def indexed_folders(self) -> List[str]:
        """등록된 폴더 목록 (기존 API 호환)"""
        return self._db.get_folders()
    
    @indexed_folders.setter
    def indexed_folders(self, folders: List[str]):
        """폴더 목록 설정 (기존 API 호환 - DB 초기화 시 사용)"""
        # DB 초기화 후 폴더 추가
        self._db.reset_database()
        for folder in folders:
            self._db.add_folder(folder)
    
    @property
    def files(self) -> Dict[str, FileInfo]:
        """파일 딕셔너리 (기존 API 호환 - 읽기 전용)"""
        # 주의: 대용량 데이터의 경우 성능 저하 가능
        all_files = self._db.get_all_files()
        return {f.file_path: f for f in all_files}
    
    @files.setter
    def files(self, files_dict: Dict[str, FileInfo]):
        """파일 딕셔너리 설정 (기존 API 호환 - DB 초기화 시 사용)"""
        # 기존 파일 모두 삭제 후 새로 추가
        self._db.reset_database()
        if files_dict:
            self._db.add_files_batch(list(files_dict.values()))
    
    def _save_index(self):
        """색인 저장 (기존 API 호환 - SQLite는 자동 저장되므로 noop)"""
        pass  # SQLite는 자동 커밋
    
    def add_folder(self, folder_path: str) -> bool:
        """폴더 추가"""
        folder_path = os.path.abspath(folder_path)
        if not os.path.isdir(folder_path):
            return False
        return self._db.add_folder(folder_path)
    
    def remove_folder(self, folder_path: str) -> bool:
        """폴더 제거 및 해당 폴더의 모든 색인 데이터 삭제"""
        return self._db.remove_folder(folder_path)
    
    def scan_folder_fast(self, folder_path: str) -> List[str]:
        """폴더 내 파일들을 빠르게 스캔 (os.scandir 사용)"""
        found_files = []
        
        def scan_recursive(path):
            try:
                with os.scandir(path) as entries:
                    for entry in entries:
                        try:
                            if entry.is_file(follow_symlinks=False):
                                ext = os.path.splitext(entry.name)[1].lower()
                                if ext in self.SUPPORTED_EXTENSIONS:
                                    found_files.append(entry.path)
                            elif entry.is_dir(follow_symlinks=False) and not entry.name.startswith('.'):
                                scan_recursive(entry.path)
                        except (PermissionError, OSError):
                            pass
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
        batch = []  # 배치 저장용
        
        if progress_callback:
            progress_callback(0, total, "스캔 완료, 색인 중...")
        
        def process_file(file_path):
            try:
                file_name = os.path.basename(file_path)
                stat = os.stat(file_path)
                
                # 이미 색인되어 있고 수정되지 않았으면 스킵
                existing_mtime = self._db.get_file_modified_time(file_path)
                if existing_mtime is not None and existing_mtime == stat.st_mtime:
                    return None
                
                folder_path_part = os.path.dirname(file_path)
                folder_name = os.path.basename(folder_path_part)
                ext = os.path.splitext(file_name)[1].lower()
                
                content = ""
                if extract_content:
                    try:
                        from .hwp_extractor import extract_text
                        content = extract_text(file_path)
                    except:
                        pass
                
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
            except Exception:
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
                        batch.append(result)
                        indexed_count += 1
                        
                        # 배치 저장
                        if len(batch) >= self.BATCH_SIZE:
                            self._db.add_files_batch(batch)
                            batch = []
                except Exception:
                    pass
        
        # 남은 배치 저장
        if batch:
            self._db.add_files_batch(batch)
        
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
        return self._db.get_files_in_folder(folder_path, include_subfolders)
    
    def get_all_files(self) -> List[FileInfo]:
        """모든 색인된 파일 반환"""
        return self._db.get_all_files()
    
    def get_file_info(self, file_path: str) -> Optional[FileInfo]:
        """특정 파일 정보 반환"""
        return self._db.get_file(file_path)
    
    def extract_content_for_file(self, file_path: str) -> str:
        """특정 파일의 텍스트 추출 (지연 로딩)"""
        file_info = self._db.get_file(file_path)
        
        if file_info:
            if not file_info.indexed or not file_info.content:
                try:
                    from .hwp_extractor import extract_text
                    content = extract_text(file_path)
                    self._db.update_content(file_path, content)
                    return content
                except:
                    return ""
            return file_info.content
        return ""
    
    # ==================== 새로운 메서드 ====================
    
    def search_fts(self, query: str, folder_path: Optional[str] = None) -> List[tuple]:
        """
        FTS5 전문 검색 (새 API)
        
        Args:
            query: 검색어
            folder_path: 특정 폴더로 제한 (None이면 전체)
            
        Returns:
            List[Tuple[FileInfo, match_count]]: 검색 결과
        """
        return self._db.search_fts(query, folder_path)
    
    def get_stats(self) -> dict:
        """데이터베이스 통계"""
        return self._db.get_stats()
    
    def reset_database(self):
        """데이터베이스 초기화"""
        self._db.reset_database()
    
    def sync_all_folders(self, progress_callback=None) -> dict:
        """
        모든 폴더 동기화 - 삭제된 파일 제거, 수정된 파일 업데이트
        
        Returns:
            {'total_deleted': int, 'total_updated': int}
        """
        total_deleted = 0
        total_updated = 0
        
        folders = self.indexed_folders
        
        for folder in folders:
            if not os.path.isdir(folder):
                continue
            
            # 현재 파일 시스템의 파일 목록
            current_files = self.scan_folder_fast(folder)
            
            # DB와 동기화 (삭제된 파일 제거)
            sync_result = self._db.sync_folder(folder, current_files)
            total_deleted += sync_result['deleted']
            
            # 수정된 파일 업데이트 (modified_time 비교)
            files_to_update = []
            for file_path in sync_result['to_check']:
                try:
                    stat = os.stat(file_path)
                    existing_mtime = self._db.get_file_modified_time(file_path)
                    
                    # 새 파일이거나 수정된 파일
                    if existing_mtime is None or existing_mtime != stat.st_mtime:
                        files_to_update.append(file_path)
                except Exception:
                    pass
            
            # 업데이트 필요한 파일들 재색인
            if files_to_update:
                for file_path in files_to_update:
                    try:
                        file_name = os.path.basename(file_path)
                        folder_path_part = os.path.dirname(file_path)
                        folder_name = os.path.basename(folder_path_part)
                        ext = os.path.splitext(file_name)[1].lower()
                        stat = os.stat(file_path)
                        
                        # 기존 레코드 삭제 후 새로 추가 (FTS 트리거 문제 방지)
                        self._db.delete_file(file_path)
                        
                        # 텍스트 추출
                        content = ""
                        try:
                            from .hwp_extractor import extract_text
                            content = extract_text(file_path)
                        except:
                            pass
                        
                        file_info = FileInfo(
                            file_path=file_path,
                            file_name=file_name,
                            folder_path=folder_path_part,
                            folder_name=folder_name,
                            extension=ext,
                            size=stat.st_size,
                            modified_time=stat.st_mtime,
                            content=content,
                            indexed=True
                        )
                        self._db.add_file(file_info)
                        total_updated += 1
                        
                        if progress_callback:
                            progress_callback(file_name)
                    except Exception:
                        pass
        
        return {
            'total_deleted': total_deleted,
            'total_updated': total_updated
        }
