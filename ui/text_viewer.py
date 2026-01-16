"""
텍스트 뷰어 위젯
HWP 파일 내용을 표시하고 검색어를 하이라이트
표와 이미지도 지원
"""
import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTextBrowser, QLabel, QHBoxLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from core.searcher import HWPSearcher


class TextViewerWidget(QWidget):
    """
    HWP 파일 텍스트 뷰어
    - QTextBrowser 사용 (HTML 지원)
    - 표 렌더링 지원
    - 이미지 표시 (또는 플레이스홀더)
    - 검색어 하이라이트 (빨간색 볼드체)
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file = ""
        self._current_html = ""
        self._current_query = ""
        self._images = []
        self._searcher = HWPSearcher()
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 헤더
        header_layout = QHBoxLayout()
        
        header = QLabel("📖 텍스트 뷰어")
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
        header_layout.addWidget(header)
        
        # 매칭 횟수 표시
        self.match_count_label = QLabel("")
        self.match_count_label.setStyleSheet("""
            QLabel {
                color: #ff6b6b;
                font-size: 12px;
                font-weight: bold;
                padding: 8px;
            }
        """)
        header_layout.addWidget(self.match_count_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # 파일명 표시
        self.file_label = QLabel("파일을 선택하세요")
        self.file_label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 12px;
                padding: 5px;
                background-color: #252526;
                border-radius: 3px;
            }
        """)
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)
        
        # 텍스트 브라우저
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(False)
        self.text_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 15px;
                font-size: 14px;
                line-height: 1.8;
            }
        """)
        
        # 폰트 설정
        font = QFont("Malgun Gothic", 12)
        self.text_browser.setFont(font)
        
        layout.addWidget(self.text_browser)
    
    def set_content(self, file_path: str, html_content: str, images: list, query: str = ""):
        """
        HTML 콘텐츠 설정 및 표시
        
        Args:
            file_path: 파일 경로
            html_content: HTML 형식 텍스트
            images: 이미지 정보 리스트
            query: 하이라이트할 검색어
        """
        self._current_file = file_path
        self._current_html = html_content
        self._images = images
        self._current_query = query
        
        # 파일명 표시
        file_name = os.path.basename(file_path) if file_path else "파일 없음"
        self.file_label.setText(f"📄 {file_name}")
        
        # 이미지 플레이스홀더 삽입
        display_html = self._insert_image_placeholders(html_content, images)
        
        # 검색어 하이라이트
        if query:
            plain_text = re.sub(r'<[^>]+>', '', html_content)
            match_count = self._searcher.count_mentions(plain_text, query)
            self.match_count_label.setText(f"🔍 '{query}' {match_count}회 발견")
            display_html = self._highlight_query(display_html, query)
        else:
            self.match_count_label.setText("")
        
        # 최종 HTML 렌더링
        final_html = self._wrap_html(display_html)
        self.text_browser.setHtml(final_html)
    
    def set_text(self, file_path: str, text: str, query: str = ""):
        """
        일반 텍스트 설정 (레거시 호환)
        """
        # 텍스트를 HTML로 변환
        html_content = self._text_to_html(text)
        self.set_content(file_path, html_content, [], query)
    
    def _text_to_html(self, text: str) -> str:
        """일반 텍스트를 HTML로 변환"""
        text = self._escape_html(text)
        text = text.replace('\n', '<br>\n')
        return text
    
    def _insert_image_placeholders(self, html: str, images: list) -> str:
        """이미지 플레이스홀더 또는 실제 이미지 삽입"""
        if not images:
            # 이미지 태그가 있지만 데이터가 없으면 플레이스홀더로 교체
            img_pattern = re.compile(r'<img[^>]*>', re.IGNORECASE)
            html = img_pattern.sub(
                '<div style="border: 2px dashed #666; padding: 30px; text-align: center; '
                'margin: 15px 0; background: linear-gradient(135deg, #2a2a2a 0%, #1e1e1e 100%); '
                'border-radius: 8px; color: #888;">'
                '<span style="font-size: 40px;">🖼️</span><br>'
                '<span style="font-size: 12px; color: #666;">이미지 위치</span>'
                '</div>',
                html
            )
            return html
        
        # 이미지 데이터가 있으면 base64 인라인 이미지로 삽입
        for i, img in enumerate(images):
            if img.get('placeholder'):
                placeholder = (
                    '<div style="border: 2px dashed #666; padding: 30px; text-align: center; '
                    'margin: 15px 0; background: linear-gradient(135deg, #2a2a2a 0%, #1e1e1e 100%); '
                    'border-radius: 8px; color: #888;">'
                    '<span style="font-size: 40px;">🖼️</span><br>'
                    '<span style="font-size: 12px; color: #666;">이미지 위치</span>'
                    '</div>'
                )
                # img 태그를 플레이스홀더로 교체
                img_pattern = re.compile(r'<img[^>]*>', re.IGNORECASE)
                html = img_pattern.sub(placeholder, html, count=1)
            elif img.get('data'):
                # base64 인라인 이미지
                data_uri = f"data:{img['mime_type']};base64,{img['data']}"
                img_tag = (
                    f'<div style="text-align: center; margin: 15px 0;">'
                    f'<img src="{data_uri}" style="max-width: 100%; border-radius: 8px; '
                    f'box-shadow: 0 4px 6px rgba(0,0,0,0.3);" />'
                    f'</div>'
                )
                img_pattern = re.compile(r'<img[^>]*>', re.IGNORECASE)
                html = img_pattern.sub(img_tag, html, count=1)
        
        return html
    
    def _highlight_query(self, html: str, query: str) -> str:
        """검색어 하이라이트 (태그 내부는 건너뜀)"""
        if not query:
            return html
        
        # 검색어를 하이라이트 span으로 치환
        def highlight_text(text):
            pattern = re.compile(f'({re.escape(query)})', re.IGNORECASE)
            return pattern.sub(
                r'<span style="color: #FF0000; font-weight: bold; '
                r'background-color: #FFFF00; padding: 2px 4px; border-radius: 3px;">\1</span>',
                text
            )
        
        # 태그 사이의 텍스트만 처리 (m.group(1)이 실제 텍스트)
        def replace_match(m):
            text_between_tags = m.group(1)
            highlighted = highlight_text(text_between_tags)
            return '>' + highlighted + '<'
        
        # 태그 사이의 텍스트 찾아서 치환
        result = re.sub(r'>([^<]+)<', replace_match, '>' + html + '<')
        
        # 앞뒤에 붙인 >< 제거
        return result[1:-1]

    
    def _wrap_html(self, content: str) -> str:
        """HTML 감싸기 - 다크 테마 스타일 적용"""
        return f'''
        <html>
        <head>
            <style>
                body {{
                    font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
                    font-size: 14px;
                    line-height: 1.8;
                    color: #d4d4d4;
                    background-color: #1e1e1e;
                    padding: 10px;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 15px 0;
                    background-color: #252526;
                    border-radius: 8px;
                    overflow: hidden;
                }}
                th, td {{
                    border: 1px solid #3d3d3d;
                    padding: 12px;
                    text-align: left;
                }}
                th {{
                    background-color: #2d2d2d;
                    font-weight: bold;
                    color: #ffffff;
                }}
                tr:nth-child(even) {{
                    background-color: #2a2a2a;
                }}
                tr:hover {{
                    background-color: #333333;
                }}
                p {{
                    margin: 10px 0;
                }}
                br {{
                    line-height: 1.8;
                }}
            </style>
        </head>
        <body>
            {content}
        </body>
        </html>
        '''
    
    def set_query(self, query: str):
        """검색어만 변경하여 하이라이트 업데이트"""
        if self._current_html:
            self.set_content(self._current_file, self._current_html, self._images, query)
    
    def clear(self):
        """뷰어 초기화"""
        self._current_file = ""
        self._current_html = ""
        self._current_query = ""
        self._images = []
        self.file_label.setText("파일을 선택하세요")
        self.match_count_label.setText("")
        self.text_browser.clear()
        self.text_browser.setHtml(self._wrap_html('''
            <div style="text-align: center; padding-top: 100px; color: #888888;">
                <p style="font-size: 48px;">📂</p>
                <p>왼쪽에서 폴더를 선택하고<br>파일을 클릭하면 내용이 여기에 표시됩니다.</p>
            </div>
        '''))
    
    def _escape_html(self, text: str) -> str:
        """HTML 특수문자 이스케이프"""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;'))
    
    def get_current_file(self) -> str:
        """현재 표시 중인 파일 경로 반환"""
        return self._current_file
    
    def get_current_text(self) -> str:
        """현재 표시 중인 텍스트 반환 (순수 텍스트)"""
        return re.sub(r'<[^>]+>', '', self._current_html)
