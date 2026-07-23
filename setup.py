"""
LiveRecord Studio 安装程序 - 单文件 exe
内嵌程序压缩包，双击运行后选择路径安装
"""
import os
import sys
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


def get_default_dir():
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "LiveRecord Studio")


def create_shortcut(target, shortcut, desc=""):
    ps = (
        f'$WshShell = New-Object -comObject WScript.Shell; '
        f'$S = $WshShell.CreateShortcut("{shortcut}"); '
        f'$S.TargetPath = "{target}"; '
        f'$S.WorkingDirectory = "{os.path.dirname(target)}"; '
        f'$S.Description = "{desc}"; '
        f'$S.Save()'
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)


def do_copy(src, dst, progress_cb=None):
    """递归复制并报告进度"""
    total = 0
    # 先计算总文件数
    for root, dirs, files in os.walk(src):
        total += len(files)

    copied = 0
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        target_dir = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(target_dir, exist_ok=True)
        for f in files:
            shutil.copy2(os.path.join(root, f), os.path.join(target_dir, f))
            copied += 1
            if progress_cb and copied % 20 == 0:
                progress_cb(copied, total)
    if progress_cb:
        progress_cb(copied, total)


class InstallWizard:
    def __init__(self, embedded_archive):
        self.embedded_archive = embedded_archive

        self.root = tk.Tk()
        self.root.title("LiveRecord Studio 安装程序")
        self.root.geometry("520x340")
        self.root.resizable(False, False)

        style = ttk.Style()
        style.theme_use("clam")

        # 标题
        ttk.Label(self.root, text="LiveRecord Studio", font=("Microsoft YaHei", 18, "bold")).pack(pady=(15, 0))
        ttk.Label(self.root, text="版本 1.0.2", font=("Microsoft YaHei", 9)).pack(pady=(0, 10))

        # 安装路径
        pf = ttk.LabelFrame(self.root, text="安装路径", padding=10)
        pf.pack(fill="x", padx=20, pady=5)

        self.path_var = tk.StringVar(value=get_default_dir())
        ttk.Entry(pf, textvariable=self.path_var, font=("Microsoft YaHei", 10)).pack(fill="x", side="left", expand=True, padx=(0, 5))
        ttk.Button(pf, text="浏览...", width=8, command=self._browse).pack(side="right")

        # 选项
        of = ttk.Frame(self.root)
        of.pack(fill="x", padx=25, pady=5)
        self.desktop_var = tk.BooleanVar(value=True)
        self.startmenu_var = tk.BooleanVar(value=True)
        self.autorun_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(of, text="创建桌面快捷方式", variable=self.desktop_var).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(of, text="创建开始菜单快捷方式", variable=self.startmenu_var).grid(row=0, column=1, sticky="w", padx=10)

        # 进度
        self.progress = ttk.Progressbar(self.root, mode="determinate", maximum=100)
        self.progress.pack(fill="x", padx=20, pady=(10, 0))

        self.status_var = tk.StringVar(value="点击「安装」开始")
        ttk.Label(self.root, textvariable=self.status_var, font=("Microsoft YaHei", 9)).pack(pady=3)

        # 按钮
        bf = ttk.Frame(self.root)
        bf.pack(pady=10)
        self.install_btn = ttk.Button(bf, text="立即安装", command=self._install)
        self.install_btn.pack(side="left", padx=5)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _browse(self):
        d = filedialog.askdirectory(initialdir=os.path.dirname(self.path_var.get()))
        if d:
            self.path_var.set(d)

    def _on_close(self):
        if self.install_btn["state"] != "disabled":
            self.root.destroy()

    def _install(self):
        target = self.path_var.get().strip()
        if not target:
            messagebox.showwarning("提示", "请选择安装路径")
            return

        self.install_btn["state"] = "disabled"
        self.status_var.set("正在解压并复制文件...")

        def run():
            try:
                # 解压内嵌的 7z 到临时目录
                import tempfile
                import zipfile

                tmpdir = tempfile.mkdtemp(prefix="LRS_install_")
                self.status_var.set("正在解压安装包...")

                # 用 7z 或 zipfile 解压
                archive_ext = os.path.splitext(self.embedded_archive)[1].lower()

                if archive_ext == ".7z":
                    # 找 7z.exe
                    candidates = [
                        os.path.join(os.environ.get("ProgramFiles", ""), "7-Zip", "7z.exe"),
                        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "7-Zip", "7z.exe"),
                    ]
                    seven_z = None
                    for c in candidates:
                        if os.path.isfile(c):
                            seven_z = c
                            break
                    if not seven_z:
                        raise RuntimeError("需要安装 7-Zip 才能解压安装包")
                    subprocess.run(
                        [seven_z, "x", "-y", f"-o{tmpdir}", self.embedded_archive],
                        capture_output=True, check=True
                    )
                else:
                    with zipfile.ZipFile(self.embedded_archive, "r") as z:
                        z.extractall(tmpdir)

                # 找到解压后的 LiveRecordStudio 目录
                extracted = os.path.join(tmpdir, "LiveRecordStudio")
                if not os.path.isdir(extracted):
                    # 可能直接解压到 tmpdir
                    if os.path.isfile(os.path.join(tmpdir, "LiveRecordStudio.exe")):
                        extracted = tmpdir
                    else:
                        raise RuntimeError("安装包内容异常")

                # 清理目标目录
                if os.path.exists(target):
                    shutil.rmtree(target)

                # 复制文件
                self.root.after(0, lambda: self.status_var.set("正在复制文件..."))

                def progress_cb(done, total):
                    pct = int(done / total * 80) + 10
                    self.root.after(0, lambda p=pct: self.progress.configure(value=p))
                    self.root.after(0, lambda d=done, t=total: self.status_var.set(
                        f"正在复制文件... ({d}/{t})"
                    ))

                do_copy(extracted, target, progress_cb)

                # 创建快捷方式
                self.root.after(0, lambda: self.status_var.set("正在创建快捷方式..."))
                exe_path = os.path.join(target, "LiveRecordStudio.exe")

                if self.desktop_var.get():
                    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
                    create_shortcut(exe_path, os.path.join(desktop, "LiveRecord Studio.lnk"), "LiveRecord Studio")

                if self.startmenu_var.get():
                    sm = os.path.join(
                        os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "LiveRecord Studio"
                    )
                    os.makedirs(sm, exist_ok=True)
                    create_shortcut(exe_path, os.path.join(sm, "LiveRecord Studio.lnk"), "LiveRecord Studio")

                # 创建卸载脚本
                uninstall = os.path.join(target, "uninstall.bat")
                with open(uninstall, "w", encoding="gbk") as f:
                    f.write("@echo off\nchcp 65001 >nul 2>&1\n")
                    f.write("echo 正在卸载 LiveRecord Studio...\n")
                    if self.desktop_var.get():
                        f.write('del "%USERPROFILE%\\Desktop\\LiveRecord Studio.lnk" 2>nul\n')
                    if self.startmenu_var.get():
                        f.write('rmdir /s /q "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\LiveRecord Studio" 2>nul\n')
                    f.write(f'timeout /t 1 /nobreak >nul\n')
                    f.write(f'rmdir /s /q "{target}"\n')
                    f.write("echo 卸载完成。\npause\n")

                # 清理临时目录
                shutil.rmtree(tmpdir, ignore_errors=True)

                self.root.after(0, lambda: self.progress.configure(value=100))
                self.root.after(0, lambda: self.status_var.set("安装完成！"))
                self.root.after(500, lambda: messagebox.showinfo(
                    "安装完成",
                    f"LiveRecord Studio 已安装到：\n{target}\n\n"
                    "桌面和开始菜单已创建快捷方式。"
                ))
                self.root.after(600, self.root.destroy)

            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"安装失败: {e}"))
                self.root.after(0, lambda: messagebox.showerror("安装失败", str(e)))
                self.root.after(0, lambda: self.install_btn.configure(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def run(self):
        self.root.mainloop()


def main():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))

    # 查找内嵌的安装包
    archive = None
    for name in ["app.7z", "app.zip", "LiveRecordStudio.7z", "LiveRecordStudio.zip"]:
        p = os.path.join(base, name)
        if os.path.isfile(p):
            archive = p
            break

    if not archive:
        # 如果在开发环境，直接用 dist 目录
        dist = os.path.join(base, "..", "dist", "LiveRecordStudio")
        if os.path.isdir(dist):
            app = InstallWizard(dist)
            app.run()
            return
        messagebox.showerror("错误", "未找到安装包文件。\n请确保 app.7z 与安装程序在同一目录。")
        sys.exit(1)

    app = InstallWizard(archive)
    app.run()


if __name__ == "__main__":
    main()