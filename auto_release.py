import os
import re
import shutil
import subprocess
import sys

def update_version_in_code(new_version):
    target_file = 'converter.py'
    with open(target_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 앱 소스코드 내부의 APP_VERSION = "v..." 부분을 찾아서 새 버전으로 자동 교체
    content = re.sub(r'APP_VERSION\s*=\s*"[^"]+"', f'APP_VERSION = "{new_version}"', content)
    
    with open(target_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"[*] {target_file} 내부의 버전이 '{new_version}'으로 자동 수정되었습니다.")

def main():
    print("="*50)
    print("🚀 앱 빌드 & GitHub 자동 배포 스크립트")
    print("="*50)
    
    new_version = input("\n1. 릴리즈할 새 버전을 입력하세요 (예: v1.0.1) : ").strip()
    release_note = input("2. 이번 업데이트의 핵심 내용을 입력하세요 : ").strip()

    # 1. 파이썬 코드 내의 버전 변경
    update_version_in_code(new_version)

    # 2. PyInstaller 빌드 진행
    print("\n[*] PyInstaller로 단일 실행 파일(.exe) 빌드를 시작합니다. (잠시만 기다려주세요...)")
    # 필요에 따라 아래 빌드 명령어 옵션을 수정해서 사용하세요.
    build_cmd = "pyinstaller --noconsole --onefile --icon=app_icon.ico --add-binary \"ffmpeg.exe;.\" --add-binary \"yt-dlp.exe;.\" converter.py"
    subprocess.run(build_cmd, shell=True)

    # 3. GitHub Release 업로드
    exe_path = os.path.join("dist", "converter.exe")
    if not os.path.exists(exe_path):
        print(f"\n[!] 빌드 실패: {exe_path} 파일을 찾을 수 없습니다.")
        sys.exit(1)

    print(f"\n[*] GitHub에 '{new_version}' 릴리즈를 생성하고 파일을 업로드합니다...")
    gh_cmd = f'gh release create {new_version} "{exe_path}" --title "{new_version} - {release_note}" --notes "{release_note}"'
    
    result = subprocess.run(gh_cmd, shell=True)
    
    if result.returncode == 0:
        print(f"\n[+] 🎉 배포 성공! 새 버전이 GitHub에 완벽하게 업로드되었습니다.")
    else:
        print(f"\n[!] 업로드 실패. GitHub CLI(gh)가 설치되어 있고 로그인이 되어있는지 확인하세요.")
        print("    (로그인 확인 명령어: gh auth status)")

    # 4. 잔여 파일 정리 (Cleanup)
    print("\n[*] 빌드 잔여 파일(build 폴더, .spec)을 정리합니다...")
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("converter.spec"):
        os.remove("converter.spec")

if __name__ == "__main__":
    main()