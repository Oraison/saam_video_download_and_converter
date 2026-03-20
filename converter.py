import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import threading
import os
import sys
import re
import tempfile
import glob
import json
import urllib.request
from tkinterdnd2 import TkinterDnD, DND_FILES

APP_VERSION = "v1.0.0"
GITHUB_REPO = "Oraison/saam_video_download_and_converter" # GitHub '사용자명/저장소명' 형식

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class VideoConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("사암교회 미디어 툴")
        self.root.geometry("450x550")
        self.root.resizable(False, False)

        # [핵심 추가] 창 및 작업표시줄 아이콘 설정
        icon_path = resource_path('app_icon.ico')
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)

        self.input_filepath = ""
        self.output_filepath = ""
        self.total_duration = 0

        self._cleanup_old_update()

        self._setup_ui()
        self.update_version_label()
        
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.handle_drop)

    def _cleanup_old_update(self):
        def cleanup():
            current_exe = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
            old_exe = current_exe + ".old"
            
            if not os.path.exists(old_exe):
                return
                
            import time
            # 이전 프로세스가 완전히 종료될 때까지 최대 5번(2.5초) 재시도하며 삭제
            for _ in range(5):
                try:
                    os.remove(old_exe)
                    break
                except Exception:
                    time.sleep(0.5)
                    
        threading.Thread(target=cleanup, daemon=True).start()

    def _setup_ui(self):
        # --- 1. 유튜브 다운로드 섹션 ---
        tk.Label(self.root, text="▶️ 유튜브 다운로드 & 자동 변환", font=("Arial", 11, "bold")).pack(pady=(15, 5))
        
        frame_yt = tk.Frame(self.root)
        frame_yt.pack(fill="x", padx=25)
        
        self.url_entry = tk.Entry(frame_yt, width=38)
        self.url_entry.pack(side="left", padx=(0, 5), ipady=3)
        self.url_entry.insert(0, "유튜브 링크를 붙여넣으세요")
        self.url_entry.bind('<FocusIn>', lambda args: self.url_entry.delete('0', 'end') if self.url_entry.get() == "유튜브 링크를 붙여넣으세요" else None)

        self.btn_youtube = tk.Button(frame_yt, text="다운로드", command=self.start_youtube_download, bg="#FF0000", fg="white", font=("Arial", 9, "bold"))
        self.btn_youtube.pack(side="left")

        tk.Frame(self.root, height=1, bg="gray").pack(fill="x", padx=20, pady=15)

        # --- 2. PC 동영상 변환 섹션 ---
        tk.Label(self.root, text="🔄 PC 동영상 변환", font=("Arial", 11, "bold")).pack(pady=(5, 5))
        
        self.drop_zone = tk.Label(self.root, text="📁 창 어디에든 동영상 파일을 드래그 앤 드롭하세요", 
                                  bg="#e0e0e0", width=45, height=3, relief="groove")
        self.drop_zone.pack(pady=5)

        tk.Button(self.root, text="또는 파일 탐색기로 열기", command=self.select_input).pack(pady=5)

        self.lbl_input = tk.Label(self.root, text="원본: 선택된 파일 없음", fg="gray")
        self.lbl_input.pack()
        self.lbl_output = tk.Label(self.root, text="출력: (자동 지정됨)", fg="gray")
        self.lbl_output.pack(pady=5)

        # --- 3. 공통 상태 표시창 및 버튼 ---
        tk.Frame(self.root, height=1, bg="#e0e0e0").pack(fill="x", padx=20, pady=10)

        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=350, mode="determinate")
        self.progress.pack(pady=(5, 5))

        self.lbl_status = tk.Label(self.root, text="대기 중", font=("Arial", 10))
        self.lbl_status.pack()

        self.btn_convert = tk.Button(self.root, text="변환 시작", command=self.start_conversion, bg="#4CAF50", fg="white", font=("Arial", 11, "bold"))
        self.btn_convert.pack(pady=(10, 5))

        self.btn_open_folder = tk.Button(self.root, text="📂 완료된 파일 열기", command=self.open_output_folder, bg="#2196F3", fg="white", font=("Arial", 10, "bold"))

        # --- 4. 업데이트 섹션 ---
        tk.Frame(self.root, height=1, bg="#e0e0e0").pack(fill="x", padx=20, pady=(15, 5))
        update_frame = tk.Frame(self.root)
        update_frame.pack(fill="x", padx=25, side="bottom", pady=(0, 15))
        
        self.btn_app_update = tk.Button(update_frame, text="프로그램 업데이트", command=self.check_app_update, relief="groove")
        self.btn_app_update.pack(side="left")
        self.app_version_label = tk.Label(update_frame, text=f"앱: {APP_VERSION}", font=("Arial", 9, "italic"), fg="gray")
        self.app_version_label.pack(side="left", padx=5)

        self.btn_update = tk.Button(update_frame, text="엔진 업데이트", command=self.start_yt_dlp_update, relief="groove")
        self.btn_update.pack(side="right")
        self.version_label = tk.Label(update_frame, text="", font=("Arial", 9, "italic"), fg="gray")
        self.version_label.pack(side="right", padx=5)


    # ==========================================
    # 코어 변환 로직 (H.264 인코딩)
    # ==========================================
    def _execute_ffmpeg(self, status_prefix="변환 중..."):
        self.total_duration = self.get_video_duration()
        ffmpeg_exe_path = resource_path('ffmpeg.exe')
        
        command = [
            ffmpeg_exe_path, '-y', 
            '-i', self.input_filepath,
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '192k',
            self.output_filepath
        ]
        
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', errors='ignore', startupinfo=startupinfo, universal_newlines=True)
        
        if process.stderr:
            for line in process.stderr:
                line_str = str(line if line else "")
                if self.total_duration > 0:
                    match = re.search(r"time=(\d{2}):(\d{2}):(\d{2}\.\d+)", line_str)
                    if match:
                        hours, minutes, seconds = map(float, match.groups())
                        current_time = (hours * 3600) + (minutes * 60) + seconds
                        percent = (current_time / self.total_duration) * 100
                        self.root.after(0, self.update_progress_ui, percent, f"{status_prefix} {percent:.1f}%")

        process.wait()
        return process.returncode == 0

    # ==========================================
    # 유튜브 다운로드 관련 로직
    # ==========================================
    def start_youtube_download(self):
        url = self.url_entry.get().strip()
        if not url or url == "유튜브 링크를 붙여넣으세요":
            messagebox.showwarning("입력 오류", "유튜브 링크를 입력해주세요.")
            return

        save_dir = filedialog.askdirectory(title="최종 저장할 폴더 선택")
        if not save_dir:
            return

        self._disable_buttons()
        self.progress['value'] = 0
        self.lbl_status.config(text="유튜브 다운로드 준비 중...", fg="blue")

        threading.Thread(target=self.run_youtube_download_and_convert, args=(url, save_dir), daemon=True).start()

    def run_youtube_download_and_convert(self, url, save_dir):
        yt_dlp_path = resource_path('yt-dlp.exe')
        ffmpeg_path = resource_path('ffmpeg.exe')

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # 1. Get metadata JSON from yt-dlp
                self.root.after(0, self.update_progress_ui, 0, "영상 정보 가져오는 중...")
                get_meta_command = [yt_dlp_path, '--print-json', '--skip-download', '--no-warnings', url]
                
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
                meta_proc = subprocess.run(get_meta_command, capture_output=True, text=True, encoding='utf-8', errors='ignore', startupinfo=startupinfo)
                
                if meta_proc.returncode != 0:
                    raise RuntimeError(f"영상 정보를 가져오지 못했습니다: {meta_proc.stderr}")
                
                try:
                    metadata = json.loads(meta_proc.stdout)
                except json.JSONDecodeError:
                    raise RuntimeError("영상 정보(JSON)를 파싱할 수 없습니다.")

                title = metadata.get('title', 'youtube_video')
                safe_title = re.sub(r'[\\/*?:"<>|]', "", title)

                # 2. Download video with a fixed temporary name
                temp_output_path = os.path.join(temp_dir, 'temp_video.%(ext)s')
                download_command = [
                    yt_dlp_path,
                    '-f', 'bestvideo+bestaudio/best',
                    '--ffmpeg-location', ffmpeg_path,
                    '--progress',
                    '--no-warnings',
                    '-o', temp_output_path,
                    url
                ]

                process = subprocess.Popen(download_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, encoding='utf-8', errors='ignore', startupinfo=startupinfo)

                full_output = []
                for line in iter(process.stdout.readline, ''):
                    if not line:
                        break
                    full_output.append(line)
                    
                    # Progress parsing
                    progress_match = re.search(r'\[download\]\s+([0-9.]+)? of.* at (.*?/s) ETA (.*)', line)
                    if progress_match:
                        percent_str, speed, eta = progress_match.groups()
                        if percent_str:
                            percent = float(percent_str.replace('%',''))
                            self.root.after(0, self.update_progress_ui, percent, f"다운로드 중... {percent:.1f}% ({speed.strip()} ETA {eta.strip()})")
                
                process.wait()

                if process.returncode != 0:
                    raise RuntimeError(f"다운로드 실패 (코드: {process.returncode}):\n{''.join(full_output)}")
                
                self.root.after(0, self.update_progress_ui, 100, "다운로드 완료! 변환 준비 중...")

                # 3. Find the downloaded file using glob
                downloaded_files = glob.glob(os.path.join(temp_dir, 'temp_video.*'))
                if not downloaded_files:
                    raise FileNotFoundError("다운로드된 임시 파일을 찾을 수 없습니다.")

                self.input_filepath = downloaded_files[0]
                new_filename = f"{safe_title}.mp4" 
                self.output_filepath = os.path.join(save_dir, new_filename)

                # 4. Start conversion
                self.root.after(0, self.update_progress_ui, 0, "최적화 중...")
                success = self._execute_ffmpeg(status_prefix="인코딩 중...")

                if success:
                    self.root.after(0, self.update_ui_after_task, "🎉 다운로드 및 변환 완료!", "green")
                else:
                    self.root.after(0, self.update_ui_after_task, "❌ 변환 과정에서 오류 발생", "red")

            except Exception as e:
                self.root.after(0, self.update_ui_after_task, "❌ 다운로드 실패 (엔진 업데이트 권장)", "red")
                self.root.after(0, lambda err=e: messagebox.showwarning("다운로드 오류", f"유튜브 영상 다운로드에 실패했습니다.\n우측 하단의 [엔진 업데이트] 버튼을 눌러 최신 버전으로 업데이트한 후 다시 시도해 주세요.\n\n상세 오류:\n{str(err)[:300]}"))
                print("YouTube Error:", e)

    # ==========================================
    # 로컬 파일 변환 관련 로직
    # ==========================================
    def process_selected_file(self, file_path):
        self.input_filepath = file_path
        dir_name = os.path.dirname(file_path)
        base_name = os.path.basename(file_path)
        name_without_ext = os.path.splitext(base_name)[0]
        
        new_filename = f"converted_{name_without_ext}.mp4"
        self.output_filepath = os.path.join(dir_name, new_filename)
        
        self.lbl_input.config(text=f"원본: {base_name}", fg="black")
        self.lbl_output.config(text=f"출력: {new_filename}", fg="blue")
        self.drop_zone.config(bg="#d4edda", text="✅ 파일 인식 완료!\n아래 변환 시작 버튼을 눌러주세요.")
        
        self.progress['value'] = 0
        self.lbl_status.config(text="대기 중", fg="black")
        self.btn_open_folder.pack_forget()

    def handle_drop(self, event):
        file_path = event.data
        if file_path.startswith('{') and file_path.endswith('}'):
            file_path = file_path[1:-1]
        self.process_selected_file(file_path)

    def select_input(self):
        file_path = filedialog.askopenfilename(title="동영상 파일 선택", filetypes=[("Video Files", "*.mp4 *.avi *.mkv *.mov *.flv *.wmv")])
        if file_path:
            self.process_selected_file(file_path)

    def get_video_duration(self):
        ffmpeg_exe_path = resource_path('ffmpeg.exe')
        command = [ffmpeg_exe_path, '-i', self.input_filepath]
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        try:
            process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', errors='ignore', startupinfo=startupinfo)
            stderr_text = str(process.stderr if process.stderr else "")
            match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d+)", stderr_text)
            if match:
                hours, minutes, seconds = map(float, match.groups())
                return (hours * 3600) + (minutes * 60) + seconds
        except Exception:
            pass
        return 0

    def start_conversion(self):
        if not self.input_filepath:
            messagebox.showwarning("입력 오류", "먼저 변환할 동영상 파일을 넣어주세요.")
            return

        self._disable_buttons()
        self.progress['value'] = 0
        self.lbl_status.config(text="영상 정보 분석 중...", fg="blue")

        threading.Thread(target=self.run_ffmpeg, daemon=True).start()

    def run_ffmpeg(self):
        try:
            success = self._execute_ffmpeg(status_prefix="인코딩 중...")
            if success:
                self.root.after(0, self.update_ui_after_task, "🎉 변환 완료! (100%)", "green")
            else:
                self.root.after(0, self.update_ui_after_task, "❌ 변환 실패 (권한 또는 코덱 문제)", "red")
        except Exception as e:
            self.root.after(0, self.update_ui_after_task, f"알 수 없는 오류: {e}", "red")

    # ==========================================
    # 공통 UI 업데이트 로직
    # ==========================================
    def _disable_buttons(self):
        self.btn_convert.config(state=tk.DISABLED, bg="gray")
        self.btn_youtube.config(state=tk.DISABLED, bg="gray")
        self.btn_open_folder.pack_forget()

    def update_progress_ui(self, percent, text_msg):
        self.progress['value'] = percent
        self.lbl_status.config(text=text_msg, fg="blue")

    def update_ui_after_task(self, message, color):
        if color == "green":
            self.progress['value'] = 100 
            self.btn_open_folder.pack(pady=5)

        self.lbl_status.config(text=message, fg=color)
        self.btn_convert.config(state=tk.NORMAL, bg="#4CAF50")
        self.btn_youtube.config(state=tk.NORMAL, bg="#FF0000")
        self.drop_zone.config(bg="#e0e0e0", text="📁 창 어디에든 동영상 파일을 드래그 앤 드롭하세요")

    def open_output_folder(self):
        if self.output_filepath and os.path.exists(self.output_filepath):
            if os.name == 'nt':
                subprocess.run(['explorer', '/select,', os.path.normpath(self.output_filepath)])
            else:
                folder_path = os.path.dirname(self.output_filepath)
                os.startfile(folder_path) if hasattr(os, 'startfile') else subprocess.run(['open', folder_path])
        else:
            messagebox.showerror("오류", "파일을 찾을 수 없습니다.")

    def start_yt_dlp_update(self):
        if messagebox.askyesno("업데이트 확인", "최신 버전의 유튜브 다운로드 엔진을 다운로드합니다.\n계속하시겠습니까?"):
            self.lbl_status.config(text="엔진 업데이트 확인 중...", fg="blue")
            self.btn_update.config(state=tk.DISABLED)
            threading.Thread(target=self.run_yt_dlp_update, daemon=True).start()

    def run_yt_dlp_update(self):
        try:
            yt_dlp_path = resource_path('yt-dlp.exe')
            command = [yt_dlp_path, '-U']
            
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', errors='ignore', startupinfo=startupinfo)
            stdout, stderr = process.communicate()
            
            output = stdout + stderr

            if process.returncode == 0:
                if "is up to date" in output:
                    message = "엔진이 이미 최신 버전입니다."
                elif "Updated yt-dlp to" in output:
                    message = "엔진이 성공적으로 업데이트되었습니다."
                else:
                    message = output # show other success messages
                self.root.after(0, lambda: messagebox.showinfo("업데이트 완료", message))
            else:
                self.root.after(0, lambda: messagebox.showerror("업데이트 오류", f"엔진 업데이트 중 오류가 발생했습니다:\n\n{output}"))

        except FileNotFoundError:
             self.root.after(0, lambda: messagebox.showerror("오류", "yt-dlp.exe를 찾을 수 없습니다. 프로그램 폴더에 파일이 있는지 확인하세요."))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("알 수 없는 오류", f"업데이트 중 알 수 없는 오류가 발생했습니다:\n{e}"))
        finally:
            self.root.after(0, self.update_version_label)
            self.root.after(0, self.lbl_status.config, {"text": "대기 중", "fg": "black"})
            self.root.after(0, self.btn_update.config, {"state": tk.NORMAL})

    def update_version_label(self):
        try:
            yt_dlp_path = resource_path('yt-dlp.exe')
            command = [yt_dlp_path, '--version']
            
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            version_output = subprocess.check_output(command, startupinfo=startupinfo, encoding='utf-8', errors='ignore').strip()
            self.version_label.config(text=f"현재 v.{version_output}")
        except Exception:
            self.version_label.config(text="버전 확인 불가")

    # ==========================================
    # 프로그램 자체 업데이트 (GitHub Releases)
    # ==========================================
    def check_app_update(self):
        self.btn_app_update.config(state=tk.DISABLED)
        self.lbl_status.config(text="업데이트 확인 중...", fg="blue")
        threading.Thread(target=self._run_app_update_check, daemon=True).start()

    def _run_app_update_check(self):
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())

            latest_version = data.get("tag_name")
            if latest_version and latest_version != APP_VERSION:
                assets = data.get("assets", [])
                download_url = None
                for asset in assets:
                    if asset["name"].endswith(".exe"):
                        download_url = asset["browser_download_url"]
                        break

                if download_url:
                    self.root.after(0, self._prompt_app_update, latest_version, download_url)
                else:
                    self.root.after(0, lambda: messagebox.showinfo("업데이트", "최신 버전이 릴리즈되었으나 .exe 파일이 없습니다."))
                    self.root.after(0, self._reset_app_update_ui)
            else:
                self.root.after(0, lambda: messagebox.showinfo("업데이트", "이미 최신 버전입니다."))
                self.root.after(0, self._reset_app_update_ui)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("오류", f"버전 확인 실패:\n{e}"))
            self.root.after(0, self._reset_app_update_ui)

    def _prompt_app_update(self, latest_version, download_url):
        if messagebox.askyesno("업데이트 발견", f"새로운 버전({latest_version})이 있습니다.\n업데이트하시겠습니까?"):
            self.lbl_status.config(text="프로그램 다운로드 중...", fg="blue")
            threading.Thread(target=self._download_and_apply_update, args=(download_url,), daemon=True).start()
        else:
            self._reset_app_update_ui()

    def _download_and_apply_update(self, download_url):
        try:
            current_exe = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
            if not current_exe.endswith('.exe'):
                self.root.after(0, lambda: messagebox.showerror("알림", "파이썬 스크립트(.py) 상태에서는 업데이트가 불가능합니다.\n빌드된 .exe 환경에서 테스트해주세요."))
                self.root.after(0, self._reset_app_update_ui)
                return

            new_exe = current_exe + ".new"
            
            req = urllib.request.Request(download_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                total_size = int(response.info().get('Content-Length', -1))
                downloaded = 0
                with open(new_exe, 'wb') as out_file:
                    while True:
                        chunk = response.read(8192) # 8KB씩 안전하게 분할 다운로드
                        if not chunk:
                            break
                        out_file.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            self.root.after(0, self.lbl_status.config, {"text": f"프로그램 업데이트 중... {percent:.1f}%", "fg": "blue"})
                        else:
                            self.root.after(0, self.lbl_status.config, {"text": f"프로그램 업데이트 중... ({downloaded // 1024} KB)", "fg": "blue"})

            # --- 배치 파일 방식 대신 안전한 파일명 변경(Rename) 트릭 사용 ---
            old_exe = current_exe + ".old"
            
            if os.path.exists(old_exe):
                try:
                    os.remove(old_exe)
                except Exception:
                    pass
                    
            # 1. 윈도우는 실행 중인 파일의 이름 변경을 허용함
            os.rename(current_exe, old_exe)
            
            # 2. 새 파일을 원래 이름으로 변경
            os.rename(new_exe, current_exe)
            
            # PyInstaller 환경 변수 상속 완벽 차단 (대소문자 무시 및 PATH 내부 찌꺼기까지 완벽 제거)
            clean_env = os.environ.copy()
            for k in list(clean_env.keys()):
                if '_MEI' in k.upper() or 'PYINSTALLER' in k.upper():
                    clean_env.pop(k, None)
                    
            if 'PATH' in clean_env:
                paths = clean_env['PATH'].split(os.pathsep)
                clean_env['PATH'] = os.pathsep.join([p for p in paths if '_MEI' not in p.upper()])
            
            # 3. 파이썬에서 새 버전을 직접 실행하고 종료 (배치파일을 거치지 않으므로 환경변수가 절대 오염되지 않음)
            subprocess.Popen([current_exe], env=clean_env)
            os._exit(0)

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("오류", f"적용 중 문제 발생:\n{e}"))
            self.root.after(0, self._reset_app_update_ui)

    def _reset_app_update_ui(self):
        self.lbl_status.config(text="대기 중", fg="black")
        self.btn_app_update.config(state=tk.NORMAL)

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = VideoConverterApp(root)
    root.mainloop()