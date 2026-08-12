#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube to MP3/MP4 Downloader (GUI)
====================================
โปรแกรมแปลงไฟล์จาก YouTube URL เป็น MP3 (เสียงคุณภาพสูงสุด) หรือ MP4 (วิดีโอคุณภาพสูงสุด)

การติดตั้งก่อนใช้งาน:
    1) ติดตั้ง Python 3.8 หรือใหม่กว่า (ต้องมี tkinter ติดมาด้วย - บน macOS/Windows
       ที่ติดตั้งจาก python.org จะมีอยู่แล้ว)
    2) ติดตั้งไลบรารีที่จำเป็น:
           pip install -r requirements.txt
       หรือ
           pip install yt-dlp
    3) ติดตั้ง ffmpeg (จำเป็นสำหรับการแปลง/รวมไฟล์คุณภาพสูงสุด):
           - Windows: https://ffmpeg.org/download.html (แล้วเพิ่มลง PATH)
           - macOS:   brew install ffmpeg
           - Linux:   sudo apt install ffmpeg

วิธีใช้งาน:
    python yt_downloader_gui.py

หมายเหตุด้านลิขสิทธิ์:
    กรุณาใช้โปรแกรมนี้ดาวน์โหลดเฉพาะเนื้อหาที่ท่านมีสิทธิ์ใช้งาน (เช่น วิดีโอของตัวเอง,
    เนื้อหาที่อนุญาตให้ดาวน์โหลด หรือเพื่อการใช้งานส่วนตัวตามที่กฎหมายในประเทศของท่านอนุญาต)
    การดาวน์โหลดเนื้อหาที่มีลิขสิทธิ์โดยไม่ได้รับอนุญาตอาจขัดต่อข้อกำหนดการใช้งานของ YouTube
    และกฎหมายลิขสิทธิ์ในบางประเทศ
"""

import os
import sys
import threading
import queue
import subprocess
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except ImportError:
    print("ไม่พบโมดูล tkinter กรุณาติดตั้ง Python เวอร์ชันที่มี tkinter รวมอยู่ด้วย")
    sys.exit(1)

try:
    import yt_dlp
except ImportError:
    print("ไม่พบไลบรารี yt-dlp กรุณาติดตั้งด้วยคำสั่ง:\n    pip install yt-dlp")
    sys.exit(1)


APP_TITLE = "YouTube to MP3/MP4 Downloader"


def check_ffmpeg() -> bool:
    """คืนค่า True ถ้าเครื่องนี้มี ffmpeg ให้ใช้งาน"""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return True
    except FileNotFoundError:
        return False


class DownloaderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title(APP_TITLE)
        root.geometry("580x460")
        root.resizable(False, False)

        self.msg_queue: "queue.Queue" = queue.Queue()
        self.download_thread = None

        default_dir = str(Path.home() / "Downloads")
        if not os.path.isdir(default_dir):
            default_dir = str(Path.home())

        self.output_dir = tk.StringVar(value=default_dir)
        self.format_var = tk.StringVar(value="mp3")
        self.url_var = tk.StringVar()

        self._build_ui()
        self._poll_queue()

        if not check_ffmpeg():
            messagebox.showwarning(
                "ไม่พบ ffmpeg",
                "โปรแกรมนี้ต้องใช้ ffmpeg เพื่อแปลง/รวมไฟล์คุณภาพสูงสุด\n\n"
                "กรุณาติดตั้ง ffmpeg ก่อนใช้งาน:\n"
                "  Windows: https://ffmpeg.org/download.html\n"
                "  macOS:   brew install ffmpeg\n"
                "  Linux:   sudo apt install ffmpeg",
            )

    # ---------------------------------------------------------------- UI ---
    def _build_ui(self):
        pad = {"padx": 14, "pady": 6}

        tk.Label(
            self.root, text="วาง YouTube URL:", font=("TkDefaultFont", 10, "bold")
        ).pack(anchor="w", **pad)

        url_entry = tk.Entry(self.root, textvariable=self.url_var, width=68)
        url_entry.pack(padx=14, fill="x")
        url_entry.focus()

        fmt_frame = tk.LabelFrame(self.root, text="รูปแบบไฟล์ผลลัพธ์")
        fmt_frame.pack(anchor="w", fill="x", **pad)
        tk.Radiobutton(
            fmt_frame,
            text="🎵 MP3 — เสียงคุณภาพสูงสุด (320 kbps)",
            variable=self.format_var,
            value="mp3",
        ).pack(anchor="w", padx=10, pady=2)
        tk.Radiobutton(
            fmt_frame,
            text="🎬 MP4 — วิดีโอคุณภาพสูงสุดที่มี (รวมเสียง+ภาพที่ดีที่สุด)",
            variable=self.format_var,
            value="mp4",
        ).pack(anchor="w", padx=10, pady=2)

        dir_frame = tk.Frame(self.root)
        dir_frame.pack(anchor="w", fill="x", **pad)
        tk.Label(dir_frame, text="บันทึกไปที่โฟลเดอร์:").pack(side="left")
        tk.Entry(dir_frame, textvariable=self.output_dir, width=38).pack(
            side="left", padx=6
        )
        tk.Button(dir_frame, text="เลือกโฟลเดอร์...", command=self._choose_dir).pack(
            side="left"
        )

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=10)
        self.download_btn = tk.Button(
            btn_frame,
            text="⬇  ดาวน์โหลด",
            width=20,
            height=1,
            bg="#e63946",
            fg="white",
            activebackground="#c1121f",
            command=self._start_download,
        )
        self.download_btn.pack(side="left", padx=6)
        tk.Button(
            btn_frame, text="เปิดโฟลเดอร์ผลลัพธ์", command=self._open_output_dir
        ).pack(side="left", padx=6)

        self.progress = ttk.Progressbar(
            self.root, orient="horizontal", length=540, mode="determinate"
        )
        self.progress.pack(padx=14, pady=(4, 2))

        self.status_var = tk.StringVar(value="พร้อมทำงาน")
        tk.Label(self.root, textvariable=self.status_var, fg="#333").pack(
            anchor="w", padx=14
        )

        self.log_text = tk.Text(
            self.root, height=9, width=72, state="disabled", bg="#f7f7f7"
        )
        self.log_text.pack(padx=14, pady=8)

    # ------------------------------------------------------------- helpers ---
    def _choose_dir(self):
        d = filedialog.askdirectory(initialdir=self.output_dir.get())
        if d:
            self.output_dir.set(d)

    def _open_output_dir(self):
        path = self.output_dir.get()
        if not os.path.isdir(path):
            messagebox.showerror("ผิดพลาด", "ไม่พบโฟลเดอร์นี้")
            return
        if sys.platform == "darwin":
            subprocess.run(["open", path])
        elif sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", path])

    def _log(self, message: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # -------------------------------------------------------------- action ---
    def _start_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("แจ้งเตือน", "กรุณาวาง URL ของ YouTube ก่อน")
            return
        if not check_ffmpeg():
            messagebox.showerror(
                "ไม่พบ ffmpeg", "กรุณาติดตั้ง ffmpeg ก่อนใช้งานโปรแกรมนี้"
            )
            return

        out_dir = self.output_dir.get().strip()
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError as e:
            messagebox.showerror("ผิดพลาด", f"ไม่สามารถสร้างโฟลเดอร์ปลายทางได้: {e}")
            return

        self.download_btn.config(state="disabled", text="กำลังดาวน์โหลด...")
        self.progress["value"] = 0
        self.status_var.set("กำลังเริ่มดาวน์โหลด...")
        self._log(f"เริ่มดาวน์โหลด: {url}")

        self.download_thread = threading.Thread(
            target=self._download_worker,
            args=(url, self.format_var.get(), out_dir),
            daemon=True,
        )
        self.download_thread.start()

    def _progress_hook(self, d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            if total:
                pct = downloaded / total * 100
                self.msg_queue.put(("progress", pct))
            speed = d.get("speed")
            speed_str = f"{speed / 1024 / 1024:.2f} MB/s" if speed else "กำลังคำนวณ..."
            self.msg_queue.put(("status", f"กำลังดาวน์โหลด... ({speed_str})"))
        elif d.get("status") == "finished":
            self.msg_queue.put(("status", "ดาวน์โหลดเสร็จ กำลังแปลง/รวมไฟล์..."))
            self.msg_queue.put(("progress", 100))

    def _download_worker(self, url: str, fmt: str, out_dir: str):
        outtmpl = os.path.join(out_dir, "%(title)s.%(ext)s")
        try:
            if fmt == "mp3":
                ydl_opts = {
                    "format": "bestaudio/best",
                    "outtmpl": outtmpl,
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "320",
                        }
                    ],
                    "progress_hooks": [self._progress_hook],
                    "noplaylist": True,
                    "quiet": True,
                    "no_warnings": True,
                }
            else:
                ydl_opts = {
                    # เลือกวิดีโอ+เสียงคุณภาพสูงสุดที่มีแยกกัน แล้วให้ ffmpeg รวมเป็น mp4
                    "format": "bestvideo*+bestaudio/best",
                    "merge_output_format": "mp4",
                    "outtmpl": outtmpl,
                    "progress_hooks": [self._progress_hook],
                    "noplaylist": True,
                    "quiet": True,
                    "no_warnings": True,
                }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "ไฟล์")

            self.msg_queue.put(("done", title))
        except Exception as e:  # noqa: BLE001 - แสดงข้อผิดพลาดให้ผู้ใช้เห็นตรงๆ
            self.msg_queue.put(("error", str(e)))

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "progress":
                    self.progress["value"] = payload
                elif kind == "status":
                    self.status_var.set(payload)
                    self._log(payload)
                elif kind == "done":
                    self.status_var.set(f"เสร็จสมบูรณ์: {payload}")
                    self._log(f"✅ ดาวน์โหลดเสร็จสมบูรณ์: {payload}")
                    self.progress["value"] = 100
                    self.download_btn.config(state="normal", text="⬇  ดาวน์โหลด")
                    messagebox.showinfo(
                        "เสร็จสมบูรณ์", f'ดาวน์โหลด "{payload}" เรียบร้อยแล้ว'
                    )
                elif kind == "error":
                    self.status_var.set("เกิดข้อผิดพลาด")
                    self._log(f"❌ ข้อผิดพลาด: {payload}")
                    self.download_btn.config(state="normal", text="⬇  ดาวน์โหลด")
                    messagebox.showerror("เกิดข้อผิดพลาด", payload)
        except queue.Empty:
            pass
        self.root.after(150, self._poll_queue)


def main():
    root = tk.Tk()
    DownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
