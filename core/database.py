"""
SQLite 데이터베이스 모듈 - FTS5 전문 검색 지원
대용량 파일 색인 및 초고속 검색을 위한 핵심 모듈
"""
import os
import sqlite3
import threading
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
from contextlib import contextmanager


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
    indexed: bool = False
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @staticmethod
    def from_dict(data: dict) -> 'FileInfo':
        if 'indexed' not in data:
            data['indexed'] = bool(data.get('content', ''))
        return FileInfo(**data)


class DatabaseManager:
    """
    SQLite 데이터베이스 관리자 - FTS5 전문 검색 지원
    
    특징:
    - FTS5를 사용한 초고속 전문 검색
    - 배치 단위 삽입으로 색인 성능 최적화
    - 스레드 안전한 연결 관리
    """
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            app_dir = os.path.join(os.path.expanduser("~"), ".hwp_instant_viewer")
            os.makedirs(app_dir, exist_ok=True)
            db_path = os.path.join(app_dir, "index.db")
        
        self.db_path = db_path
        self._local = threading.local()
        self._init_database()
    
    @contextmanager
    def _get_connection(self):
        """스레드별 연결 관리 - 컨텍스트 매니저"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.connection.row_factory = sqlite3.Row
        
        try:
            yield self._local.connection
        except Exception as e:
            self._local.connection.rollback()
            raise e
    
    def _init_database(self):
        """데이터베이스 및 테이블 초기화"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 파일 메타데이터 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    file_name TEXT NOT NULL,
                    folder_path TEXT NOT NULL,
                    folder_name TEXT NOT NULL,
                    extension TEXT NOT NULL,
                    size INTEGER DEFAULT 0,
                    modified_time REAL DEFAULT 0,
                    content TEXT DEFAULT '',
                    indexed INTEGER DEFAULT 0
                )
            """)
            
            # 파일 경로 인덱스 (빠른 조회용)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_files_folder_path 
                ON files(folder_path)
            """)
            
            # 폴더 목록 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    folder_path TEXT UNIQUE NOT NULL
                )
            """)
            
            # FTS5 전문 검색 테이블 (파일명 + 본문)
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
                    file_name,
                    content,
                    content='files',
                    content_rowid='id',
                    tokenize='unicode61'
                )
            """)
            
            # FTS 트리거 - 삽입
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS files_ai AFTER INSERT ON files BEGIN
                    INSERT INTO files_fts(rowid, file_name, content) 
                    VALUES (new.id, new.file_name, new.content);
                END
            """)
            
            # FTS 트리거 - 삭제
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS files_ad AFTER DELETE ON files BEGIN
                    INSERT INTO files_fts(files_fts, rowid, file_name, content) 
                    VALUES ('delete', old.id, old.file_name, old.content);
                END
            """)
            
            # FTS 트리거 - 업데이트
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS files_au AFTER UPDATE ON files BEGIN
                    INSERT INTO files_fts(files_fts, rowid, file_name, content) 
                    VALUES ('delete', old.id, old.file_name, old.content);
                    INSERT INTO files_fts(rowid, file_name, content) 
                    VALUES (new.id, new.file_name, new.content);
                END
            """)
            
            conn.commit()
    
    # ==================== 폴더 관리 ====================
    
    def add_folder(self, folder_path: str) -> bool:
        """폴더 추가"""
        folder_path = os.path.abspath(folder_path)
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR IGNORE INTO folders (folder_path) VALUES (?)",
                    (folder_path,)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False
    
    def remove_folder(self, folder_path: str) -> bool:
        """폴더 및 관련 파일 모두 삭제"""
        folder_path = os.path.abspath(folder_path)
        folder_path_normalized = os.path.normcase(folder_path)
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 폴더 목록에서 삭제
                cursor.execute(
                    "DELETE FROM folders WHERE folder_path = ? COLLATE NOCASE",
                    (folder_path,)
                )
                
                # 해당 폴더 및 하위 폴더의 모든 파일 삭제
                # SQLite의 LIKE 패턴 사용
                folder_prefix = folder_path_normalized.replace('\\', '/') + '/'
                cursor.execute("""
                    DELETE FROM files 
                    WHERE LOWER(REPLACE(folder_path, '\\', '/')) LIKE ? 
                       OR LOWER(REPLACE(folder_path, '\\', '/')) = ?
                """, (folder_prefix + '%', folder_path_normalized.replace('\\', '/')))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"폴더 삭제 오류: {e}")
            return False
    
    def get_folders(self) -> List[str]:
        """등록된 폴더 목록 반환"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT folder_path FROM folders")
                return [row['folder_path'] for row in cursor.fetchall()]
        except Exception:
            return []
    
    # ==================== 파일 관리 ====================
    
    def add_file(self, file_info: FileInfo) -> bool:
        """파일 추가 또는 업데이트"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO files 
                    (file_path, file_name, folder_path, folder_name, 
                     extension, size, modified_time, content, indexed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    file_info.file_path,
                    file_info.file_name,
                    file_info.folder_path,
                    file_info.folder_name,
                    file_info.extension,
                    file_info.size,
                    file_info.modified_time,
                    file_info.content,
                    1 if file_info.indexed else 0
                ))
                conn.commit()
                return True
        except Exception:
            return False
    
    def add_files_batch(self, file_infos: List[FileInfo]) -> int:
        """배치 단위 파일 추가 (성능 최적화)"""
        if not file_infos:
            return 0
        
        added = 0
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 배치 삽입
                data = [
                    (
                        fi.file_path, fi.file_name, fi.folder_path, fi.folder_name,
                        fi.extension, fi.size, fi.modified_time, fi.content,
                        1 if fi.indexed else 0
                    )
                    for fi in file_infos
                ]
                
                cursor.executemany("""
                    INSERT OR REPLACE INTO files 
                    (file_path, file_name, folder_path, folder_name,
                     extension, size, modified_time, content, indexed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, data)
                
                added = cursor.rowcount
                conn.commit()
        except Exception as e:
            print(f"배치 삽입 오류: {e}")
        
        return added
    
    def get_file(self, file_path: str) -> Optional[FileInfo]:
        """파일 정보 조회"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM files WHERE file_path = ?",
                    (file_path,)
                )
                row = cursor.fetchone()
                if row:
                    return self._row_to_fileinfo(row)
        except Exception:
            pass
        return None
    
    def update_content(self, file_path: str, content: str) -> bool:
        """파일 본문 업데이트"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE files SET content = ?, indexed = 1 
                    WHERE file_path = ?
                """, (content, file_path))
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False
    
    def get_files_in_folder(self, folder_path: str, include_subfolders: bool = True) -> List[FileInfo]:
        """폴더 내 파일 목록 조회"""
        folder_path = os.path.abspath(folder_path)
        # Windows 경로를 슬래시로 정규화
        folder_path_normalized = folder_path.replace('\\', '/')
        results = []
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                if include_subfolders:
                    # 하위 폴더 포함 - 정규화된 경로로 비교
                    folder_prefix = folder_path_normalized + '/'
                    cursor.execute("""
                        SELECT * FROM files 
                        WHERE REPLACE(folder_path, '\\', '/') LIKE ? 
                           OR REPLACE(folder_path, '\\', '/') = ?
                        ORDER BY file_name
                    """, (folder_prefix + '%', folder_path_normalized))
                else:
                    cursor.execute("""
                        SELECT * FROM files 
                        WHERE REPLACE(folder_path, '\\', '/') = ?
                        ORDER BY file_name
                    """, (folder_path_normalized,))
                
                for row in cursor.fetchall():
                    results.append(self._row_to_fileinfo(row))
        except Exception:
            pass
        
        return results
    
    def get_all_files(self) -> List[FileInfo]:
        """모든 파일 목록 조회"""
        results = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM files ORDER BY file_name")
                for row in cursor.fetchall():
                    results.append(self._row_to_fileinfo(row))
        except Exception:
            pass
        return results
    
    def file_exists(self, file_path: str) -> bool:
        """파일 존재 여부 확인"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM files WHERE file_path = ?",
                    (file_path,)
                )
                return cursor.fetchone() is not None
        except Exception:
            return False
    
    def get_file_modified_time(self, file_path: str) -> Optional[float]:
        """파일 수정 시간 조회"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT modified_time FROM files WHERE file_path = ?",
                    (file_path,)
                )
                row = cursor.fetchone()
                if row:
                    return row['modified_time']
        except Exception:
            pass
        return None
    
    # ==================== FTS5 검색 ====================
    
    def search_fts(self, query: str, folder_path: Optional[str] = None) -> List[Tuple[FileInfo, int]]:
        """
        FTS5 전문 검색 - 초고속 검색
        
        Args:
            query: 검색어
            folder_path: 특정 폴더로 제한 (None이면 전체)
            
        Returns:
            List[Tuple[FileInfo, match_count]]: 검색 결과와 매칭 횟수
        """
        if not query.strip():
            return []
        
        results = []
        
        # FTS5 검색어 준비 (특수문자 이스케이프)
        safe_query = query.replace('"', '""')
        fts_query = f'"{safe_query}"'  # 구문 검색 (정확한 매칭)
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                if folder_path:
                    folder_path = os.path.abspath(folder_path)
                    folder_path_normalized = folder_path.replace('\\', '/')
                    folder_prefix = folder_path_normalized + '/'
                    
                    cursor.execute("""
                        SELECT f.*, 1 as match_count
                        FROM files f
                        WHERE f.id IN (
                            SELECT rowid FROM files_fts WHERE files_fts MATCH ?
                        )
                        AND (REPLACE(f.folder_path, '\\', '/') LIKE ? 
                             OR REPLACE(f.folder_path, '\\', '/') = ?)
                        ORDER BY f.file_name
                    """, (fts_query, folder_prefix + '%', folder_path_normalized))
                else:
                    cursor.execute("""
                        SELECT f.*, 1 as match_count
                        FROM files f
                        WHERE f.id IN (
                            SELECT rowid FROM files_fts WHERE files_fts MATCH ?
                        )
                        ORDER BY f.file_name
                    """, (fts_query,))
                
                for row in cursor.fetchall():
                    file_info = self._row_to_fileinfo(row)
                    match_count = row['match_count'] if 'match_count' in row.keys() else 1
                    results.append((file_info, match_count))
                    
        except Exception as e:
            # FTS 실패 시 LIKE 검색으로 폴백
            results = self._search_fallback(query, folder_path)
        
        return results
    
    def _search_fallback(self, query: str, folder_path: Optional[str] = None) -> List[Tuple[FileInfo, int]]:
        """FTS 실패 시 LIKE 검색으로 폴백"""
        results = []
        like_query = f'%{query}%'
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                if folder_path:
                    folder_path = os.path.abspath(folder_path)
                    folder_prefix = folder_path.replace('\\', '/') + '/'
                    
                    cursor.execute("""
                        SELECT * FROM files
                        WHERE (file_name LIKE ? OR content LIKE ?)
                          AND (REPLACE(folder_path, '\\', '/') LIKE ? 
                               OR folder_path = ?)
                    """, (like_query, like_query, folder_prefix + '%', folder_path))
                else:
                    cursor.execute("""
                        SELECT * FROM files
                        WHERE file_name LIKE ? OR content LIKE ?
                    """, (like_query, like_query))
                
                for row in cursor.fetchall():
                    file_info = self._row_to_fileinfo(row)
                    # 간단한 매칭 횟수 계산
                    count = (file_info.file_name.lower().count(query.lower()) + 
                             file_info.content.lower().count(query.lower()))
                    results.append((file_info, max(count, 1)))
                    
        except Exception:
            pass
        
        return results
    
    # ==================== 유틸리티 ====================
    
    def _row_to_fileinfo(self, row: sqlite3.Row) -> FileInfo:
        """SQLite Row를 FileInfo로 변환"""
        return FileInfo(
            file_path=row['file_path'],
            file_name=row['file_name'],
            folder_path=row['folder_path'],
            folder_name=row['folder_name'],
            extension=row['extension'],
            size=row['size'],
            modified_time=row['modified_time'],
            content=row['content'] or '',
            indexed=bool(row['indexed'])
        )
    
    def get_stats(self) -> dict:
        """데이터베이스 통계"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) as count FROM files")
                file_count = cursor.fetchone()['count']
                
                cursor.execute("SELECT COUNT(*) as count FROM folders")
                folder_count = cursor.fetchone()['count']
                
                cursor.execute("SELECT COUNT(*) as count FROM files WHERE indexed = 1")
                indexed_count = cursor.fetchone()['count']
                
                return {
                    'total_files': file_count,
                    'total_folders': folder_count,
                    'indexed_files': indexed_count
                }
        except Exception:
            return {'total_files': 0, 'total_folders': 0, 'indexed_files': 0}
    
    def reset_database(self):
        """데이터베이스 초기화"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM files")
                cursor.execute("DELETE FROM folders")
                cursor.execute("DELETE FROM files_fts")
                conn.commit()
        except Exception:
            pass
    
    def close(self):
        """연결 종료"""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
