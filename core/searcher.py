"""
검색 엔진 모듈
"""
import re
from dataclasses import dataclass
from typing import List, Optional

from .indexer import FileInfo


@dataclass
class SearchResult:
    """검색 결과를 담는 데이터 클래스"""
    file_info: FileInfo
    match_count: int  # 검색어 언급 횟수
    matched_in_filename: bool  # 파일명에서 매칭됨
    matched_in_content: bool  # 본문에서 매칭됨
    preview: str  # 검색어 주변 미리보기 텍스트


class HWPSearcher:
    """HWP 파일 검색 엔진 - FTS5 전문 검색 지원"""
    
    def __init__(self, indexer=None):
        """
        검색 엔진 초기화
        
        Args:
            indexer: FolderIndexer 인스턴스 (FTS5 검색용)
        """
        self.last_query = ""
        self._indexer = indexer  # FTS5 검색용
    
    def set_indexer(self, indexer):
        """indexer 설정 (FTS5 검색용)"""
        self._indexer = indexer
    
    def search_fts(
        self, 
        query: str, 
        folder_path: str = None
    ) -> List[SearchResult]:
        """
        FTS5 전문 검색 (초고속)
        
        Args:
            query: 검색어
            folder_path: 특정 폴더로 제한 (None이면 전체)
            
        Returns:
            List[SearchResult]: 검색 결과 목록
        """
        if not query.strip():
            return []
        
        if not self._indexer:
            return []
        
        self.last_query = query
        results = []
        
        # FTS5 검색 수행
        fts_results = self._indexer.search_fts(query, folder_path)
        
        for file_info, match_count in fts_results:
            # 파일명/본문 매칭 여부 판단
            query_lower = query.lower()
            matched_in_filename = query_lower in file_info.file_name.lower()
            matched_in_content = query_lower in file_info.content.lower() if file_info.content else False
            
            # 미리보기 생성
            preview = self._generate_preview(file_info.content, query, re.IGNORECASE)
            
            result = SearchResult(
                file_info=file_info,
                match_count=match_count,
                matched_in_filename=matched_in_filename,
                matched_in_content=matched_in_content or not matched_in_filename,
                preview=preview
            )
            results.append(result)
        
        return results
    
    def search(
        self, 
        query: str, 
        files: List[FileInfo],
        case_sensitive: bool = False
    ) -> List[SearchResult]:
        """
        파일명 + 본문 내용 검색
        
        FTS5 검색이 가능하면 우선 사용, 아니면 기존 방식 사용
        
        Args:
            query: 검색어
            files: 검색할 파일 목록
            case_sensitive: 대소문자 구분 여부
            
        Returns:
            List[SearchResult]: 검색 결과 목록 (매칭 횟수 내림차순)
        """
        if not query.strip():
            return []
        
        self.last_query = query
        results = []
        
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(re.escape(query), flags)
        
        for file_info in files:
            # 파일명 검색
            filename_matches = pattern.findall(file_info.file_name)
            matched_in_filename = len(filename_matches) > 0
            
            # 본문 검색 - content가 비어있으면 실시간 추출
            content = file_info.content
            if not content or len(content) < 10:
                content = self._extract_content_on_demand(file_info)
            
            content_matches = pattern.findall(content)
            matched_in_content = len(content_matches) > 0
            
            if matched_in_filename or matched_in_content:
                total_matches = len(filename_matches) + len(content_matches)
                preview = self._generate_preview(content, query, flags)
                
                result = SearchResult(
                    file_info=file_info,
                    match_count=total_matches,
                    matched_in_filename=matched_in_filename,
                    matched_in_content=matched_in_content,
                    preview=preview
                )
                results.append(result)
        
        # 매칭 횟수 내림차순 정렬
        results.sort(key=lambda r: r.match_count, reverse=True)
        
        return results
    
    def _extract_content_on_demand(self, file_info: FileInfo) -> str:
        """필요 시 파일 내용 실시간 추출"""
        try:
            import os
            ext = file_info.extension.lower()
            file_path = file_info.file_path
            
            if not os.path.exists(file_path):
                return ""
            
            if ext == '.hwp' or ext == '.hwpx':
                from .hwp_extractor import extract_text
                return extract_text(file_path)
            elif ext == '.docx':
                from .hwp_extractor import extract_text_from_docx
                return extract_text_from_docx(file_path)
        except Exception:
            pass
        return ""
    
    def _generate_preview(
        self, 
        content: str, 
        query: str, 
        flags: int,
        context_chars: int = 50
    ) -> str:
        """
        검색어 주변 미리보기 텍스트 생성
        
        Args:
            content: 전체 텍스트
            query: 검색어
            flags: 정규식 플래그
            context_chars: 검색어 앞뒤로 보여줄 글자 수
            
        Returns:
            str: 미리보기 텍스트
        """
        if not content:
            return ""
        
        pattern = re.compile(re.escape(query), flags)
        match = pattern.search(content)
        
        if not match:
            return content[:100] + "..." if len(content) > 100 else content
        
        start = max(0, match.start() - context_chars)
        end = min(len(content), match.end() + context_chars)
        
        preview = content[start:end]
        
        if start > 0:
            preview = "..." + preview
        if end < len(content):
            preview = preview + "..."
        
        return preview.replace('\n', ' ').strip()
    
    def count_mentions(self, text: str, query: str, case_sensitive: bool = False) -> int:
        """
        검색어 언급 횟수 반환
        
        Args:
            text: 검색할 텍스트
            query: 검색어
            case_sensitive: 대소문자 구분 여부
            
        Returns:
            int: 언급 횟수
        """
        if not query.strip() or not text:
            return 0
        
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(re.escape(query), flags)
        
        return len(pattern.findall(text))
    
    def highlight_matches(
        self, 
        text: str, 
        query: str,
        case_sensitive: bool = False,
        html_format: bool = True
    ) -> str:
        """
        검색어를 하이라이트 (빨간색 볼드체)
        
        Args:
            text: 원본 텍스트
            query: 검색어
            case_sensitive: 대소문자 구분 여부
            html_format: HTML 형식으로 반환할지 여부
            
        Returns:
            str: 하이라이트된 텍스트
        """
        if not query.strip() or not text:
            return text
        
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(f'({re.escape(query)})', flags)
        
        if html_format:
            # HTML 형식: 빨간색 볼드체
            highlighted = pattern.sub(
                r'<span style="color: red; font-weight: bold;">\1</span>',
                text
            )
        else:
            # 텍스트 형식: **강조**
            highlighted = pattern.sub(r'**\1**', text)
        
        return highlighted
    
    def highlight_for_qt(self, text: str, query: str, case_sensitive: bool = False) -> str:
        """
        Qt QTextBrowser용 HTML 하이라이트
        
        Args:
            text: 원본 텍스트
            query: 검색어
            case_sensitive: 대소문자 구분 여부
            
        Returns:
            str: HTML 형식의 하이라이트된 텍스트
        """
        if not query.strip() or not text:
            # HTML 이스케이프
            return self._escape_html(text)
        
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(f'({re.escape(query)})', flags)
        
        # 먼저 HTML 이스케이프
        escaped_text = self._escape_html(text)
        escaped_query = self._escape_html(query)
        
        # 이스케이프된 텍스트에서 검색어 하이라이트
        pattern = re.compile(f'({re.escape(escaped_query)})', flags)
        highlighted = pattern.sub(
            r'<span style="color: #FF0000; font-weight: bold; background-color: #FFFF00;">\1</span>',
            escaped_text
        )
        
        # 줄바꿈을 <br>로 변환
        highlighted = highlighted.replace('\n', '<br>')
        
        return f'<html><body style="font-family: Malgun Gothic, sans-serif; font-size: 14px; line-height: 1.6;">{highlighted}</body></html>'
    
    def _escape_html(self, text: str) -> str:
        """HTML 특수문자 이스케이프"""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;'))
