"""
Mac용 PyInstaller 빌드 스크립트
"""
import PyInstaller.__main__
import os
import shutil
import platform

print("🚀 HWP Instant Viewer (Mac) 빌드 시작...")

# Mac 전용 확인
if platform.system() != "Darwin":
    print("⚠️ 이 스크립트는 macOS에서만 실행하세요.")
    print("   Windows에서는 build.py를 사용하세요.")
    exit(1)

# 1. 기존 빌드 잔여물 정리
if os.path.exists("dist"):
    try:
        shutil.rmtree("dist")
    except:
        pass
if os.path.exists("build"):
    try:
        shutil.rmtree("build")
    except:
        pass

for f in os.listdir('.'):
    if f.endswith(".spec"):
        try:
            os.remove(f)
        except:
            pass

# 2. 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
icon_path = os.path.join(current_dir, "resources", "icon.icns")

# 아이콘이 없으면 기본값 사용
icon_arg = f'--icon={icon_path}' if os.path.exists(icon_path) else ''

print("📦 PyInstaller 빌드 중...")

# 3. PyInstaller 실행 (Mac용 경로 구분자 사용)
args = [
    'main.py',
    '--name=HWP_Instant_Viewer',
    '--onefile',
    '--clean',
    '--noconsole',
    '--windowed',  # Mac용 .app 번들
    
    # 소스 코드 포함 (Mac 경로 구분자)
    '--add-data=ui:ui',
    '--add-data=core:core',
    
    # 리소스 포함 (있으면)
    '--add-data=resources:resources' if os.path.exists('resources') else '',
    
    # 숨겨진 라이브러리 명시
    '--hidden-import=PyQt6',
    '--hidden-import=PyQt6.QtCore',
    '--hidden-import=PyQt6.QtWidgets',
    '--hidden-import=PyQt6.QtGui',
    '--hidden-import=hwp5',
    '--hidden-import=hwp5.hwp5txt',
    '--hidden-import=olefile',
    '--hidden-import=docx',
    
    # 라이브러리 통째로 수집
    '--collect-all=PyQt6',
    '--collect-all=hwp5',
    '--collect-all=olefile',
]

# 빈 문자열 제거
args = [a for a in args if a]

# 아이콘 추가
if icon_arg:
    args.append(icon_arg)

PyInstaller.__main__.run(args)

print("\n" + "=" * 50)
print("✅ 빌드 성공! [dist] 폴더 안에 'HWP_Instant_Viewer' 파일을 확인하세요.")
print("=" * 50)
