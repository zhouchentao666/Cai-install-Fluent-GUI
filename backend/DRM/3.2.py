#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D加密授权器（AppID 自动版）+ GL一键授权页
增强版 v3.0  –  内嵌 CW 解密，三页全支持拖入CW
by：B-I-A-O & ☆ → 优化：Kimi
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import os
import shutil
import stat
import struct
import subprocess
import sys
import time
import winreg
from pathlib import Path
from typing import Optional, List, Tuple

import psutil
from PySide6.QtCore import (
    Qt, QThread, QObject, Signal, QTimer, QPoint, QSize, Slot
)
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QTextEdit, QMessageBox,
    QFileDialog, QTabWidget, QDialog, QToolBar, QFrame, QScrollArea,
    QCheckBox, QGridLayout
)

import sponsor_qrc  # noqa: F401
from version_checker import VersionChecker
import zipfile  # 添加到现有的导入列表中

# ------------------------------------------------------------------
# --------------  内嵌 CW 解密逻辑（start）  ------------------------
# ------------------------------------------------------------------
_FIXED_KEY_SOURCE = b"af0a3329787c9e6a6f3a1b69f841fd09a67cdfcade8b182d67a4442357815f60"
AES_KEY = hashlib.sha256(_FIXED_KEY_SOURCE).digest()
AES_IV_LENGTH = 16


class DecryptResult:
    __slots__ = ("appid", "steam_id", "timeout_start", "timeout_end",
                 "ticket", "encrypted_ticket", "lua_content", "has_lua", "raw_dlcs")

    def __init__(self, appid, steam_id, timeout_start, timeout_end,
                 ticket, encrypted_ticket, lua_content, has_lua, raw_dlcs=""):
        self.appid = appid
        self.steam_id = steam_id
        self.timeout_start = timeout_start
        self.timeout_end = timeout_end
        self.ticket = ticket
        self.encrypted_ticket = encrypted_ticket
        self.lua_content = lua_content
        self.has_lua = has_lua
        self.raw_dlcs = raw_dlcs


def ts_to_str(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def decrypt_cw_file(path: str | Path) -> DecryptResult:
    data = Path(path).read_bytes()
    iv = data[:AES_IV_LENGTH]
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    cipher = AES.new(AES_KEY, AES.MODE_CBC, iv)
    decrypted = unpad(cipher.decrypt(data[AES_IV_LENGTH:]), AES.block_size)

    pos = 0
    if decrypted[pos:pos + 4] != b"CWPS":
        raise ValueError("无效文件头 (不是 CWPS 格式)")
    pos += 4

    try:
        timeout_start, timeout_end, appid, ticket_len, encrypted_len, steam_id, lua_len = \
            struct.unpack("<QQiiiQi", decrypted[pos:pos + 40])
        pos += 40
    except struct.error:
        timeout_start, timeout_end, appid, ticket_len, encrypted_len, steam_id = \
            struct.unpack("<QQiiiQ", decrypted[pos:pos + 36])
        pos += 36
        lua_len = 0

    ticket = decrypted[pos:pos + ticket_len]
    pos += ticket_len
    encrypted_ticket = decrypted[pos:pos + encrypted_len]

    # ===== 新增：把 [app::dlcs] 整段文本截出来 =====
    raw_dlcs = ""
    start = decrypted.find(b"[app::dlcs]")
    if start != -1:
        end = decrypted.find(b"\n[", start + 11)  # 下一个段
        if end == -1:
            end = len(decrypted)
        raw_dlcs = decrypted[start:end].decode('utf-8', errors='ignore').strip()

    return DecryptResult(appid, steam_id, timeout_start, timeout_end,
                         ticket, encrypted_ticket, "", False, raw_dlcs)


# ------------------------------------------------------------------
# --------------  内嵌 CW 解密逻辑（end）  --------------------------
# ------------------------------------------------------------------

def resource_path(relative_path: str) -> str:
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def str_to_int64(s: str) -> int:
    try:
        return int(s.strip())
    except Exception:
        return 0


def log(widget: QTextEdit, msg: str, debug: bool = False) -> None:
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {'[DBG] ' if debug else ''}{msg}\n"
    widget.append(line.rstrip())
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)


LOG_FILE = "日志.log"


# ------------------------------------------------------------------
# Page1：tools 一键授权 + 脱壳  （完美防卡死、防闪退多线程架构版）
# ------------------------------------------------------------------
class Page1Worker(QObject):
    """
    后台工作线程：处理所有繁重的文件IO、子进程调用和循环等待，防止UI卡死。
    """
    log_sig = Signal(str)
    # 异步信号：用于普通提示框（不阻塞线程，防卡死）
    msg_async_sig = Signal(str, str, str)
    # 同步阻塞信号：使用 object 传字典以解决 PySide6 list 按值传递导致结果永远为 False 的 bug
    ask_sync_sig = Signal(str, str, object)
    finished_sig = Signal(bool)

    def __init__(self, task_type: str, data: dict):
        super().__init__()
        self.task_type = task_type  # 'generate', 'auth'
        self.data = data

    def run(self):
        """线程入口点"""
        try:
            if self.task_type == "generate":
                patch_dir = self.generate_patch(skip_userdata=False)
                if patch_dir:
                    self._async_msg("info", "完成",
                                    f"免Steam补丁已生成在桌面：\n{patch_dir}\n\n打开文件夹后双击 steamclient_loader_x64.exe 即可启动游戏。\n要是报错e0则点击e0报错尝试修复")
                self.finished_sig.emit(True)

            elif self.task_type == "auth":
                self.one_click_auth()
                self.finished_sig.emit(True)

        except Exception as e:
            import traceback
            err_msg = f"发生未捕获异常：{e}\n{traceback.format_exc()}"
            self.log_sig.emit(err_msg)
            self._async_msg("crit", "严重错误", err_msg)
            self.finished_sig.emit(False)

    # ---------- 线程内部辅助通信方法 ----------
    def _async_msg(self, msg_type: str, title: str, text: str) -> None:
        self.msg_async_sig.emit(msg_type, title, text)

    def _sync_ask(self, title: str, text: str) -> bool:
        res_dict = {"ans": False}
        self.ask_sync_sig.emit(title, text, res_dict)
        return res_dict["ans"]

    def _extract_biao_zip(self, steam_settings_dir: Path):
        """解压 BIAO.zip 到指定 steam_settings 目录"""
        program_dir = Path(__file__).parent
        biao_zip = program_dir / "BIAO.zip"

        # 如果当前目录没有，尝试在免steam补丁文件夹中查找
        if not biao_zip.exists():
            biao_zip = program_dir / "免steam补丁" / "BIAO.zip"

        if biao_zip.exists():
            try:
                import zipfile
                with zipfile.ZipFile(biao_zip, 'r') as zip_ref:
                    # 解压到 steam_settings 目录
                    zip_ref.extractall(steam_settings_dir)
                self.log_sig.emit("已解压 BIAO.zip 内文件到 steam_settings 文件夹")
            except Exception as e:
                self.log_sig.emit(f"解压 BIAO.zip 失败：{e}")
        else:
            self.log_sig.emit("【提示】未找到 BIAO.zip 文件，跳过解压")

    # ---------- 核心生成逻辑 ----------
    def generate_patch(self, skip_userdata=False) -> Optional[Path]:
        exe_path = self.data.get("exe_path")
        appid = self.data.get("appid")
        sid64 = self.data.get("sid64")
        cw_result = self.data.get("cw_result")
        ini_path = self.data.get("ini_path")

        desktop = Page1.get_desktop()
        patch_name = f"{appid} No Steam"
        patch_dir = desktop / patch_name
        patch_dir.mkdir(exist_ok=True)

        # 拷贝基础补丁文件，但排除 steam_stubbed.dll 和 controller.zip
        src_res = Path(__file__).with_name("免steam补丁").resolve()
        if src_res.is_dir():
            for item in src_res.iterdir():
                # 跳过 steam_stubbed.dll 和 controller.zip
                if item.name.lower() in ["steam_stubbed.dll", "controller.zip"]:
                    continue
                if item.is_file():
                    shutil.copy2(item, patch_dir / item.name)
                elif item.is_dir():
                    shutil.copytree(item, patch_dir / item.name, dirs_exist_ok=True)

        settings_dir = patch_dir / "steam_settings"
        settings_dir.mkdir(exist_ok=True)

        # === 新增：自动解压 BIAO.zip 到 steam_settings 目录 ===
        self._extract_biao_zip(settings_dir)

        # 在 steam_settings 文件夹下生成 steam_appid.txt
        try:
            (settings_dir / "steam_appid.txt").write_text(str(appid), encoding="utf-8")
        except Exception as e:
            self.log_sig.emit(f"写入 steam_appid.txt 失败：{e}")

        # 写 configs.user.ini
        if cw_result:
            ini_content = Page1.make_ini_from_cw_result(cw_result)
            (settings_dir / "configs.user.ini").write_text(ini_content, encoding="utf-8")
        else:
            shutil.copy2(ini_path, settings_dir / "configs.user.ini")

        # 写 ColdClientLoader.ini
        (patch_dir / "ColdClientLoader.ini").write_text(
            f"[SteamClient]\nExe = {exe_path}\nAppId = {appid}\n"
            f"SteamClientDll = steamclient.dll\nSteamClient64Dll = steamclient64.dll\n\n"
            f"[Injection]\nexample:\nDllsToInjectFolder=extra_dlls\n",
            encoding="utf-8"
        )


        # 写 configs.app.ini
        app_ini = settings_dir / "configs.app.ini"
        if cw_result:
            dlc_entries = Page1._extract_dlc_entries_from_cw(cw_result)
            with app_ini.open('w', encoding='utf-8') as f:
                f.write("[app::dlcs]\nunlock_all=0\n")
                # 只有当有 DLC 条目时才写入
                if dlc_entries:
                    for entry in dlc_entries:
                        f.write(f"{entry}\n")
                else:
                    # 如果没有 DLC，添加注释提示
                    f.write("# 未找到 DLC 条目\n")
        elif not ini_path:
            app_ini.write_text("[app::dlcs]\nunlock_all=0\n#竖着列\n#DLCid=DLC name\n", encoding='utf-8')
        else:
            Page1._copy_user_dlc_to_app_ini(Path(ini_path), app_ini)

        # 复制 steam_stubbed.dll 到 steam_settings/load_dlls 目录
        steam_stubbed_src = src_res / "steam_stubbed.dll"
        if steam_stubbed_src.exists():
            load_dlls_dir = settings_dir / "load_dlls"
            load_dlls_dir.mkdir(exist_ok=True)
            steam_stubbed_dst = load_dlls_dir / "steam_stubbed.dll"
            try:
                shutil.copy2(steam_stubbed_src, steam_stubbed_dst)
                self.log_sig.emit("已复制 steam_stubbed.dll 到 steam_settings/load_dlls 目录")
            except Exception as e:
                self.log_sig.emit(f"复制 steam_stubbed.dll 失败：{e}")
        else:
            self.log_sig.emit("【警告】未找到 steam_stubbed.dll 文件")

        # 拷贝 userdata
        if not skip_userdata:
            steam_path = Page1.get_steam_path()
            steamid3 = str(int(sid64) - 76561197960265728)
            official_dir = Path(steam_path or "") / "userdata" / steamid3 / appid
            if not official_dir.exists():
                self._async_msg("warn", "userdata 检查",
                                f"未找到路径：{official_dir}\n\n请确认该游戏在此设备上至少成功运行过一次，\n且已产生存档/成就等数据后再重新点击“生成”。")
                self.log_sig.emit("【警告】userdata 目录不存在，已中止生成")
                shutil.rmtree(patch_dir, ignore_errors=True)
                return None

            digit_files = [f for f in official_dir.rglob("*") if f.is_file() and f.stem.isdigit()]
            if not digit_files:
                self._async_msg("warn", "userdata 检查",
                                "在 userdata 底层未找到纯数字授权文件！\n\n请确认该游戏产生过数据后再重新生成。")
                self.log_sig.emit("【警告】userdata 下无纯数字文件，已中止生成")
                shutil.rmtree(patch_dir, ignore_errors=True)
                return None

            try:
                dst_user = patch_dir / "userdata" / steamid3 / appid
                dst_user.mkdir(parents=True, exist_ok=True)
                for file in digit_files:
                    rel = file.relative_to(official_dir)
                    target = dst_user / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file, target)
            except Exception as e:
                self.log_sig.emit(f"复制 userdata 失败：{e}")

        # 移动 dll
        extra_dlls_dir = patch_dir / "extra_dlls"
        extra_dlls_dir.mkdir(exist_ok=True)
        src_extra_dll = patch_dir / "steamclient_extra_x64.dll"
        if src_extra_dll.exists():
            shutil.move(str(src_extra_dll), str(extra_dlls_dir / "steamclient_extra_x64.dll"))

        self.log_sig.emit(f"补丁生成成功：{patch_dir}")
        return patch_dir

    # ---------- 核心一键授权逻辑 ----------
    def one_click_auth(self):
        appid = self.data.get("appid")
        exe_path = self.data.get("exe_path")

        self._clean_game_env(exe_path)

        patch_dir = self.generate_patch(skip_userdata=True)
        if not patch_dir:
            return

        loader = patch_dir / "steamclient_loader_x64.exe"
        if not loader.exists():
            self._async_msg("crit", "错误", "补丁中找不到 steamclient_loader_x64.exe")
            return

        # 启动游戏
        try:
            subprocess.Popen([str(loader)], cwd=str(patch_dir))
            self.log_sig.emit("已自动启动游戏，请耐心等待...")
        except Exception as e:
            self._async_msg("crit", "启动失败", f"启动补丁失败：\n{e}")
            self.log_sig.emit(f"启动失败：{e}")
            return

        # 同步等待用户点击弹窗
        is_game_started = self._sync_ask("验证", "游戏是否成功启动并看到画面？")

        # 关闭游戏进程
        exe_name = Path(exe_path).name
        if exe_name:
            try:
                subprocess.run(["taskkill", "/F", "/IM", exe_name], capture_output=True)
                self.log_sig.emit(f"已请求结束进程：{exe_name}")
                subprocess.run(["taskkill", "/F", "/IM", "CrashReport.exe"], capture_output=True)
            except Exception:
                pass

        time.sleep(1)

        success = False
        steam_path = Page1.get_steam_path()

        # 普通游戏处理
        if is_game_started:
            if steam_path:
                src_user = patch_dir / "userdata"
                if src_user.exists():
                    try:
                        dst_user = Path(steam_path) / "userdata"
                        shutil.copytree(src_user, dst_user, dirs_exist_ok=True)
                        success = True
                    except Exception as e:
                        self.log_sig.emit(f"复制 userdata 失败：{e}")
            else:
                self.log_sig.emit("未找到 Steam 路径，跳过 userdata 复制")

        # 清理桌面补丁
        self.log_sig.emit("3 秒后将清理桌面补丁...")
        time.sleep(3)
        cleanup_success = False
        for _ in range(5):
            try:
                shutil.rmtree(patch_dir)
                cleanup_success = True
                break
            except Exception:
                time.sleep(2)

        if cleanup_success:
            self.log_sig.emit("桌面临时补丁已清理")
        else:
            self._async_msg("warn", "清理提示", "部分补丁文件被系统占用无法自动删除，稍后请手动删除桌面的补丁文件夹。")

        if success:
            self._async_msg("info", "完成", "授权成功并已恢复原始文件！\n要是报错e0则点击e0报错尝试修复")
        else:
            self._async_msg("info", "完成", "授权流程结束 ，环境已恢复。")

    def _clean_game_env(self, exe_path: str) -> None:
        """清理游戏主程序目录下的旧版破解残留文件，营造干净环境"""
        if not exe_path:
            return

        game_dir = Path(exe_path).parent
        targets_to_remove = [
            "steam_settings",
            "GameOverlayRenderer64.dll",
            "version.dll"
        ]

        has_cleaned = False
        for target in targets_to_remove:
            target_path = game_dir / target
            if target_path.exists():
                if not has_cleaned:
                    self.log_sig.emit("开始清理游戏目录旧版残留文件...")
                    has_cleaned = True
                try:
                    if target_path.is_dir():
                        shutil.rmtree(target_path, ignore_errors=True)
                    else:
                        target_path.unlink(missing_ok=True)
                except Exception as e:
                    self.log_sig.emit(f"  [x] 清理 {target} 失败 (可能文件被占用): {e}")

        userdata_dir = game_dir / "userdata"
        if userdata_dir.exists():
            for f in userdata_dir.rglob("*"):
                if f.is_file() and f.stem.isdigit():
                    if not has_cleaned:
                        self.log_sig.emit("开始清理游戏目录旧版残留文件...")
                        has_cleaned = True
                    try:
                        f.unlink(missing_ok=True)
                    except Exception as e:
                        self.log_sig.emit(f"  [x] 清理 {f.name} 失败 (可能文件被占用): {e}")


class UserDataManagerDialog(QDialog):
    def __init__(self, userdata_path: Path, parent=None):
        super().__init__(parent)
        self.userdata_path = userdata_path
        self.file_widgets = []
        self._init_ui()
        self.populate_files()

    def _init_ui(self):
        self.setWindowTitle("Userdata 数字ID文件管理器")
        self.setMinimumSize(600, 400)

        main_layout = QVBoxLayout(self)

        self.info_label = QLabel(f"扫描目录: {self.userdata_path}")
        self.info_label.setWordWrap(True)
        main_layout.addWidget(self.info_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        self.scroll_widget = QWidget()
        self.grid_layout = QGridLayout(self.scroll_widget)
        self.grid_layout.setAlignment(Qt.AlignTop)
        scroll_area.setWidget(self.scroll_widget)

        # Header for the grid
        header_file = QLabel("<b>文件</b>")
        header_readonly = QLabel("<b>只读</b>")
        self.grid_layout.addWidget(header_file, 0, 0)
        self.grid_layout.addWidget(header_readonly, 0, 1, Qt.AlignCenter)

        self.apply_button = QPushButton("应用更改并关闭")
        self.apply_button.clicked.connect(self.apply_changes)
        main_layout.addWidget(self.apply_button)

    def populate_files(self):
        if not self.userdata_path.exists():
            self.info_label.setText(f"目录不存在: {self.userdata_path}")
            self.apply_button.setEnabled(False)
            return

        try:
            digit_files = sorted([f for f in self.userdata_path.rglob("*") if f.is_file() and f.stem.isdigit()],
                                 key=lambda p: p.name)
        except Exception as e:
            no_files_label = QLabel(f"扫描文件时出错: {e}")
            self.grid_layout.addWidget(no_files_label, 1, 0, 1, 2)
            self.apply_button.setEnabled(False)
            return

        if not digit_files:
            no_files_label = QLabel("未找到纯数字ID命名的文件。")
            self.grid_layout.addWidget(no_files_label, 1, 0, 1, 2)
            self.apply_button.setEnabled(False)
            return

        row = 1
        for file_path in digit_files:
            try:
                rel_path_str = str(file_path.relative_to(self.userdata_path))
                path_label = QLabel(rel_path_str)
                path_label.setToolTip(str(file_path))

                read_only_checkbox = QCheckBox()

                is_readonly = not os.access(file_path, os.W_OK)
                read_only_checkbox.setChecked(is_readonly)

                self.grid_layout.addWidget(path_label, row, 0)
                self.grid_layout.addWidget(read_only_checkbox, row, 1, Qt.AlignCenter)

                self.file_widgets.append((file_path, read_only_checkbox))
                row += 1
            except Exception:
                continue

    def apply_changes(self):
        changed_count = 0
        error_list = []
        for path, checkbox in self.file_widgets:
            try:
                current_mode = stat.S_IMODE(os.stat(path).st_mode)
                is_currently_readonly = not bool(current_mode & stat.S_IWRITE)
                should_be_readonly = checkbox.isChecked()

                if is_currently_readonly != should_be_readonly:
                    if is_currently_readonly:
                        os.chmod(path, current_mode | stat.S_IWRITE)

                    if should_be_readonly:
                        final_mode = stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH
                    else:
                        final_mode = stat.S_IWRITE | stat.S_IREAD

                    os.chmod(path, final_mode)
                    changed_count += 1
            except Exception as e:
                error_list.append(f"{path.name}: {e}")

        if error_list:
            QMessageBox.critical(self, "错误", "应用部分更改时出错:\n" + "\n".join(error_list))
        else:
            QMessageBox.information(self, "成功", f"成功更新 {changed_count} 个文件的只读属性。")

        self.accept()


class Page1(QWidget):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self._init_ui()
        self.cw_result: Optional[DecryptResult] = None
        self.worker_thread = None
        self.worker = None

    # -------------------- UI --------------------
    def _init_ui(self):
        self.ini_edit = QLineEdit()
        self.ini_edit.setReadOnly(True)
        self.ini_edit.setPlaceholderText("拖入或浏览 configs.user.ini 或 *.cw")
        self.ini_edit.setContextMenuPolicy(Qt.NoContextMenu)

        self.steamid_edit = QLineEdit()
        self.steamid_edit.setReadOnly(True)
        self.steamid_edit.setPlaceholderText("自动解析 SteamID64")
        self.appid_edit = QLineEdit()
        self.appid_edit.setReadOnly(True)
        self.appid_edit.setPlaceholderText("自动解析 AppID")
        self.exe_edit = QLineEdit()
        self.exe_edit.setReadOnly(True)
        self.exe_edit.setPlaceholderText("请把游戏启动程序 *.exe 拖入或浏览")
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)

        self.browse_ini_btn = QPushButton("浏览")
        self.browse_exe_btn = QPushButton("浏览")
        self.run_btn = QPushButton("一键生成免Steam补丁")
        self.run_btn.setMinimumHeight(46)
        self.set_button_style(self.run_btn, "#28a745", "#218838", "#1e7e34")

        self.auth_btn = QPushButton("一键授权")
        self.auth_btn.setMinimumHeight(46)
        self.set_button_style(self.auth_btn, "#dc3545", "#c82333", "#bd2130")

        self.fix_btn = QPushButton("e0报错尝试修复")
        self.fix_btn.setMinimumHeight(46)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(10)

        def add_row(label, edit, btn=None):
            h = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setFixedWidth(100)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            h.addWidget(lbl)
            h.addWidget(edit)
            if btn:
                h.addWidget(btn)
            lay.addLayout(h)

        add_row("授权文件：", self.ini_edit, self.browse_ini_btn)
        add_row("SteamID：", self.steamid_edit)
        add_row("AppID：", self.appid_edit)
        add_row("游戏主程序：", self.exe_edit, self.browse_exe_btn)

        tip = QLabel(
            "提示：游戏能打开才能使用生成补丁，如果拖入的exe不是正确的，启动就会报错e005或者无反应")
        tip.setStyleSheet("color:#28a745;font-size:12px;font-weight:bold;")
        lay.addWidget(tip)

        lay.addWidget(QLabel("日志："))
        lay.addWidget(self.log_edit)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self.auth_btn)
        btn_row.addWidget(self.fix_btn)
        lay.addLayout(btn_row)

        self.browse_ini_btn.clicked.connect(self.browse_ini)
        self.browse_exe_btn.clicked.connect(self.browse_exe)

        # 唤起简化的生成弹窗
        self.run_btn.clicked.connect(self.show_patch_dialog)
        self.auth_btn.clicked.connect(lambda: self.start_worker_task("auth"))
        self.fix_btn.clicked.connect(self.write_reg)

    @staticmethod
    def set_button_style(btn: QPushButton, bg: str, hover: str, pressed: str):
        btn.setStyleSheet(f"""
            QPushButton{{background:{bg};border:none;border-radius:8px;padding:8px 12px;font-size:14px;font-weight:bold;color:white;}}
            QPushButton:hover{{background:{hover};}}
            QPushButton:pressed{{background:{pressed};}}
            QPushButton:disabled{{background:#6c757d;color:#ced4da;}}
        """)

    def open_userdata_manager(self):
        appid = self.appid_edit.text().strip()
        sid64_str = self.steamid_edit.text().strip()
        exe_path = self.exe_edit.text().strip()

        if not appid or not sid64_str:
            QMessageBox.warning(self, "信息不足", "请先加载授权文件以自动解析 AppID 和 SteamID。")
            return

        try:
            sid64 = int(sid64_str)
        except ValueError:
            QMessageBox.warning(self, "格式错误", "SteamID 格式不正确。")
            return

        steamid3 = str(sid64 - 76561197960265728)

        desktop = self.get_desktop()
        patch_name = f"{appid} No Steam"
        userdata_dir = desktop / patch_name / "userdata" / steamid3 / appid

        if not userdata_dir.parent.parent.exists():
            QMessageBox.warning(self, "补丁不存在",
                                f"未找到桌面补丁文件夹：{appid} No Steam\n\n请先点击\"默认生成的免steam补丁\"生成补丁。")
            return

        dlg = UserDataManagerDialog(userdata_dir, self)
        dlg.exec()

    # -------------------- 弹窗选择：移除新补丁相关，仅保留旧版及 Userdata 功能 --------------------
    def show_patch_dialog(self):
        exe_path = self.exe_edit.text().strip()
        appid = self.appid_edit.text().strip()

        if not exe_path:
            QMessageBox.warning(self, "提示", "请先浏览或拖入游戏主程序(*.exe)")
            return
        if not appid:
            QMessageBox.warning(self, "提示", "请确保 AppID 已解析（需拖入授权文件）")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("选择补丁功能")
        dlg.setFixedSize(300, 200)

        main_layout = QVBoxLayout(dlg)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        btn_default = QPushButton("默认生成的免steam补丁")
        btn_default.setMinimumHeight(60)
        self.set_button_style(btn_default, "#28a745", "#218838", "#1e7e34")
        btn_default.clicked.connect(lambda: [dlg.accept(), self.start_worker_task("generate")])

        btn_userdata = QPushButton("检查/设置 Userdata")
        btn_userdata.setMinimumHeight(50)
        self.set_button_style(btn_userdata, "#6c757d", "#5a6268", "#545b62")
        btn_userdata.clicked.connect(lambda: self.open_userdata_manager())

        main_layout.addWidget(btn_default)
        main_layout.addStretch()
        main_layout.addWidget(btn_userdata)

        dlg.exec()

    # -------------------- 拖放与浏览 --------------------
    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent):
        for url in e.mimeData().urls():
            path = url.toLocalFile()
            if not os.path.isfile(path): continue
            if path.lower().endswith(".cw"):
                self.handle_cw_drop(path)
                return
            if path.lower().endswith("configs.user.ini"):
                self.set_ini_path(path)
                return
            if path.lower().endswith(".exe"):
                self.exe_edit.setText(path)

    def browse_ini(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 configs.user.ini 或 *.cw", "", "INI (*.ini);;CW files (*.cw)")
        if path:
            if path.lower().endswith(".cw"):
                self.handle_cw_drop(path)
            else:
                self.set_ini_path(path)

    def browse_exe(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择游戏主程序", "", "EXE (*.exe)")
        if path: self.exe_edit.setText(path)

    # -------------------- 解析逻辑 --------------------
    def handle_cw_drop(self, path: str):
        try:
            res = self._decrypt_cw_with_lua(path)
        except Exception as e:
            QMessageBox.warning(self, "CW 解密失败", str(e))
            return
        self.cw_result = res
        self.ini_edit.setText(path)
        self.steamid_edit.setText(str(res.steam_id))
        self.appid_edit.setText(str(res.appid))
        log(self.log_edit, f"CW 解析成功 → AppID：{res.appid} | SteamID：{res.steam_id}")

        self.dlc_ids = [entry.split('=', 1)[0].strip() for entry in self._extract_dlc_entries_from_cw(res)]
        if self.dlc_ids:
            log(self.log_edit, "[app::dlcs] 以下 DLC ID 已提取：\n" + " ".join(self.dlc_ids))
        else:
            log(self.log_edit, "未在 CW 文本中发现 [app::dlcs] 段或其内容为空。")
        self._auto_open_game_root()

    def set_ini_path(self, path: str):
        self.ini_edit.setText(path)
        sid64 = self.parse_steamid_from_ini(path)
        self.steamid_edit.setText(sid64 or "")
        appid = self.parse_appid_from_ini(path)
        self.appid_edit.setText(appid or "")
        self.cw_result = None
        if sid64 and appid:
            log(self.log_edit, f"已解析 SteamID64：{sid64}  |  AppID：{appid}")
            self._auto_open_game_root()

    def _auto_open_game_root(self):
        appid = self.appid_edit.text().strip()
        if not appid: return
        game_root = self.resolve_path_by_appid(appid)
        if game_root:
            log(self.log_edit, f"已定位游戏目录：{game_root}")
            subprocess.Popen(f'explorer /root,"{Path(game_root)}"')
            QMessageBox.information(self, "已自动打开目录", "请找到真正的游戏启动程序（*.exe）并拖入上方“游戏主程序”框。")
        else:
            QMessageBox.warning(self, "未找到游戏", "未能根据 AppID 找到本地游戏目录，请手动拖入启动程序！")

    # -------------------- 多线程架构：启动工作流 --------------------
    def start_worker_task(self, task_type: str):
        exe_path = self.exe_edit.text().strip()
        appid = self.appid_edit.text().strip()
        sid64 = self.steamid_edit.text().strip()
        ini_path = self.ini_edit.text().strip()

        if not exe_path:
            QMessageBox.warning(self, "提示", "请输入游戏主程序路径")
            return

        if task_type in ("generate", "auth"):
            if not appid or not sid64:
                QMessageBox.warning(self, "提示", "SteamID 或 AppID 为空")
                return
            if not self.cw_result and not os.path.isfile(ini_path):
                QMessageBox.warning(self, "提示", "授权文件不存在")
                return

        self.run_btn.setEnabled(False)
        self.auth_btn.setEnabled(False)
        self.fix_btn.setEnabled(False)

        task_data = {
            "exe_path": exe_path,
            "appid": appid,
            "sid64": sid64,
            "ini_path": ini_path,
            "cw_result": self.cw_result
        }

        self.worker_thread = QThread()
        self.worker = Page1Worker(task_type, task_data)
        self.worker.moveToThread(self.worker_thread)

        self.worker.log_sig.connect(self._on_worker_log)
        self.worker.msg_async_sig.connect(self._on_worker_msg_async)
        self.worker.ask_sync_sig.connect(self._on_worker_ask, Qt.BlockingQueuedConnection)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished_sig.connect(self._on_worker_finished)
        self.worker.finished_sig.connect(self.worker_thread.quit)
        self.worker.finished_sig.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()

    # ================= 响应工作线程的专用槽函数 ================
    @Slot(str)
    def _on_worker_log(self, msg: str):
        log(self.log_edit, msg)

    @Slot(str, str, str)
    def _on_worker_msg_async(self, msg_type: str, title: str, text: str):
        if msg_type == "info":
            QMessageBox.information(self, title, text)
        elif msg_type == "warn":
            QMessageBox.warning(self, title, text)
        else:
            QMessageBox.critical(self, title, text)

    @Slot(str, str, object)
    def _on_worker_ask(self, title: str, text: str, result_dict: dict):
        ans = QMessageBox.question(self, title, text)
        result_dict["ans"] = (ans == QMessageBox.Yes)

    @Slot(bool)
    def _on_worker_finished(self, success):
        self.run_btn.setEnabled(True)
        self.auth_btn.setEnabled(True)
        self.fix_btn.setEnabled(True)

        # 新增：一键授权任务结束后，自动执行一次 e0 修复（写注册表）
        if hasattr(self, 'worker') and self.worker and self.worker.task_type == "auth":
            if success:
                log(self.log_edit, "一键授权完成，自动执行 e0 修复...")
                self.write_reg()
            else:
                log(self.log_edit, "一键授权未完全成功，跳过自动 e0 修复")

    # -------------------- e0 修复 --------------------
    def write_reg(self):
        appid = self.appid_edit.text().strip()
        steamid_str = self.steamid_edit.text().strip()
        if not appid or not steamid_str:
            QMessageBox.warning(self, "提示", "AppID 或 SteamID 为空")
            return
        steamid_qword = str_to_int64(steamid_str)
        if steamid_qword <= 0:
            QMessageBox.warning(self, "提示", "SteamID 格式非法")
            return
        try:
            key_path = rf"Software\Valve\Steam\Apps\{appid}"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, "steamID", 0, winreg.REG_QWORD, steamid_qword)
            log(self.log_edit, f"已写入注册表：HKCU\\{key_path} → steamID = {steamid_qword}")
            QMessageBox.information(self, "完成", "尝试修复成功，不包100%！")
        except Exception as e:
            log(self.log_edit, f"修复失败：{e}")
            QMessageBox.critical(self, "错误", f"修复失败：\n{e}")

    # -------------------- 全局静态/辅助方法 --------------------
    @staticmethod
    def get_desktop() -> Path:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(None, 0x0000, None, 0, buf)
        return Path(buf.value)

    @staticmethod
    def get_steam_path() -> Optional[str]:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam") as key:
                return winreg.QueryValueEx(key, "InstallPath")[0]
        except Exception:
            return None

    @staticmethod
    def parse_steamid_from_ini(path: str) -> Optional[str]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("account_steamid="):
                        return line.split("=", 1)[1].strip()
        except Exception:
            pass
        return None

    @staticmethod
    def parse_appid_from_ini(path: str) -> Optional[str]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("#") and line[1:].strip().isdigit():
                        return line[1:].strip()
        except Exception:
            pass
        return None

    def resolve_path_by_appid(self, appid: str) -> Optional[str]:
        try:
            steam_path = self.get_steam_path()
            if not steam_path: return None
            lib_file = Path(steam_path) / "steamapps" / "libraryfolders.vdf"
            if not lib_file.exists(): return None

            libraries = [Path(steam_path)]
            with lib_file.open(encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith('"path"'):
                        raw = line.strip().split('"')[3].replace("\\\\", "\\")
                        libraries.append(Path(raw))

            for lib in libraries:
                manifest = lib / "steamapps" / f"appmanifest_{appid}.acf"
                if manifest.exists():
                    with manifest.open(encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            if line.strip().startswith('"installdir"'):
                                game_dir = line.strip().split('"')[3]
                                return str(lib / "steamapps" / "common" / game_dir)
            return None
        except Exception as e:
            log(self.log_edit, f"解析路径失败：{e}")
            return None

    @staticmethod
    def make_ini_from_cw_result(res: DecryptResult) -> str:
        ticket_b64 = base64.b64encode(res.encrypted_ticket).decode()
        return f"[user::general]\naccount_name=B-I-A-O\naccount_steamid={res.steam_id}\nticket={ticket_b64}\nlanguage=schinese\nip_country=CN\n\n[user::saves]\nlocal_save_path=./path/relative/to/dll\nsaves_folder_name=GSE Saves\n\n#{res.appid}\n\n#授权生效时间：{ts_to_str(res.timeout_start)}\n#授权失效时间：{ts_to_str(res.timeout_end)}\n"

    @staticmethod
    def _copy_user_dlc_to_app_ini(user_ini: Path, app_ini: Path) -> None:
        import configparser
        cfg = configparser.ConfigParser()
        cfg.read(user_ini, encoding='utf-8')

        appid = None
        with user_ini.open(encoding='utf-8') as f:
            for line in f:
                if line.strip().startswith('#') and line[1:].strip().isdigit():
                    appid = line[1:].strip()
                    break

        has_dlcs = cfg.has_section("app::dlcs") and cfg.items("app::dlcs")

        if not has_dlcs and appid == "2054970":
            content = (
                "[app::dlcs]\nunlock_all=0\n"
                "2593180=Dragon's Dogma 2: Explorer's Camping Kit - Camping Gear\n"
                "2593190=Dragon's Dogma 2: Dragon's Dogma Music & Sound Collection - Custom Sounds\n"
                "2593200=Dragon's Dogma 2: Harpysnare Smoke Beacons - Harpy Lure Item\n"
                "2593210=Dragon's Dogma 2: Heartfelt Pendant - A Thoughtful Gift\n"
                "2593220=Dragon's Dogma 2: Ambivalent Rift Incense - Change Pawn Inclinations\n"
                "2593230=Dragon's Dogma 2: Makeshift Gaol Key - Escape from gaol!\n"
                "2593240=Dragon's Dogma 2: Art of Metamorphosis - Character Editor\n"
                "2593250=Dragon's Dogma 2: 1500 Rift Crystals - Points to Spend Beyond the Rift (A)\n"
                "2593260=Dragon's Dogma 2: Wakestone - Restore the dead to life! (A)\n"
            )
            app_ini.write_text(content, encoding='utf-8')
            return

        with app_ini.open('w', encoding='utf-8') as f:
            f.write("[app::dlcs]\nunlock_all=0\n#竖着列\n#DLCid=DLC name\n")
            if has_dlcs:
                for k, v in cfg.items("app::dlcs"):
                    f.write(f"{k}={v}\n")

    @staticmethod
    def _extract_dlc_entries_from_cw(res: DecryptResult) -> List[str]:
        # 如果 raw_dlcs 存在，需要去除可能包含的 [app::dlcs] 头部
        if res.raw_dlcs:
            lines = res.raw_dlcs.splitlines()
            # 过滤掉 [app::dlcs] 头部和可能的 unlock_all 行
            entries = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('[') and not line.startswith('unlock_all'):
                    if '=' in line:
                        entries.append(line)
            return entries

        if not res.lua_content: return []
        in_dlcs = False
        entries = []
        for line in res.lua_content.splitlines():
            line = line.strip()
            if line == "[app::dlcs]":
                in_dlcs = True
                continue
            if in_dlcs:
                if line.startswith("[") and line.endswith("]"): break
                if "=" in line and not line.startswith('unlock_all'):
                    entries.append(line)
        return entries

    def _decrypt_cw_with_lua(self, path: str) -> DecryptResult:
        data = Path(path).read_bytes()
        iv = data[:16]
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
        cipher = AES.new(AES_KEY, AES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(data[16:]), AES.block_size)

        pos = 0
        if decrypted[pos:pos + 4] != b"CWSQ": raise ValueError("无效文件头 (不是 CWSQ 格式)")
        pos += 4

        timestamp, json_len = struct.unpack("<Qi", decrypted[pos:pos + 12])
        pos += 12
        json_bytes = decrypted[pos:pos + json_len]
        cw = __import__("json").loads(json_bytes.decode("utf-8"))

        meta = cw["metadata"]
        auth = cw["auth_data"]
        ext = cw.get("extensions", {})

        raw_dlcs_text = ""
        dlcs_section = ext.get("dlcs", "")
        if dlcs_section:
            raw_dlcs_text = f"[app::dlcs]\n{dlcs_section.strip()}"

        return DecryptResult(
            appid=meta["appid"], steam_id=meta["steam_id"],
            timeout_start=meta["created_timestamp"], timeout_end=meta["expires_timestamp"],
            ticket=bytes.fromhex(auth["app_ticket"]), encrypted_ticket=bytes.fromhex(auth["encrypted_ticket"]),
            lua_content="", has_lua=False, raw_dlcs=raw_dlcs_text
        )


# ------------------------------------------------------------------
# Page2：GL 一键授权（注入+启动+清理）+ 环境还原  （完美防闪退多线程版）
# ------------------------------------------------------------------
class Page2Worker(QObject):
    """
    后台工作线程：处理注入GL、启动、同步等待验证、以及清理还原全流程。
    """
    log_sig = Signal(str)
    msg_async_sig = Signal(str, str, str)
    # 同步阻塞信号：使用 object 传字典以解决 PySide6 list 按值传递导致结果永远为 False 的 bug
    ask_sync_sig = Signal(str, str, object)
    finished_sig = Signal(bool)

    def __init__(self, task_type: str, data: dict) -> None:
        super().__init__()
        self.task_type = task_type
        self.data = data
        self._SPECIAL_APP_LIST = {
            "2054970": [
                2593180, 2593190, 2593200, 2593210, 2593220,
                2593230, 2593240, 2593250, 2593260
            ]
        }

    def run(self) -> None:
        try:
            if self.task_type == "auth":
                self.do_auth()
            elif self.task_type == "restore":
                self._run_restore_logic()
                self._async_msg("info", "完成", "GL 环境已彻底清理并还原！\n可正常启动原版 Steam。")
            self.finished_sig.emit(True)
        except Exception as e:
            import traceback
            err_msg = f"发生异常：{e}\n{traceback.format_exc()}"
            self.log_sig.emit(err_msg)
            self._async_msg("crit", "严重错误", err_msg)
            self.finished_sig.emit(False)

    def _async_msg(self, msg_type: str, title: str, text: str) -> None:
        self.msg_async_sig.emit(msg_type, title, text)

    def _sync_ask(self, title: str, text: str) -> bool:
        # 使用 dict 以确保跨线程引用修改能够生效
        res_dict = {"ans": False}
        self.ask_sync_sig.emit(title, text, res_dict)
        return res_dict["ans"]

    def do_auth(self) -> None:
        steam_path = Page2.get_steam_path()
        if not steam_path:
            self._async_msg("crit", "错误", "未能在注册表找到Steam安装路径")
            return

        src_path = self.data.get("src_path", "")
        cw_result = self.data.get("cw_result")

        if src_path.lower().endswith(".cw") and cw_result:
            if not self._deploy_cw_tickets(steam_path, cw_result):
                return
        else:
            if not self._deploy_auth(src_path, steam_path):
                self._run_restore_logic()
                return

        if not self._inject_gl(steam_path):
            self._run_restore_logic()
            return

        dll_injector = Path(steam_path) / "DLLInjector.exe"
        try:
            subprocess.Popen([str(dll_injector)], cwd=steam_path)
            self.log_sig.emit("已启动 DLLInjector → Steam 正在启动...")
        except Exception as e:
            self.log_sig.emit(f"启动失败：{e}")
            self._async_msg("crit", "启动失败", f"DLLInjector 启动失败：\n{e}")
            self._run_restore_logic()
            return

        is_success = self._sync_ask(
            "验证等待 (最后一步)",
            "GL授权已导入并启动！\n\n请登录账号并手动启动游戏，\n直到【看到游戏画面后】再点击“是”。\n\n若失败请点击“否”。"
        )

        self._run_restore_logic()

        if is_success:
            self._async_msg("info", "完成", "授权流程成功完成，GL环境已彻底清理！")
        else:
            self._async_msg("info", "完成", "授权流程已取消，环境已自动还原。")

    def _deploy_cw_tickets(self, steam_path: str, res) -> bool:
        try:
            own_dir = Path(steam_path) / "AppOwnershipTickets"
            enc_dir = Path(steam_path) / "EncryptedAppTickets"
            own_dir.mkdir(exist_ok=True)
            enc_dir.mkdir(exist_ok=True)

            (own_dir / f"Ticket.{res.appid}").write_bytes(res.ticket)
            (enc_dir / f"EncryptedTicket.{res.appid}").write_bytes(res.encrypted_ticket)
            self.log_sig.emit(f"已生成 → Ticket.{res.appid} & EncryptedTicket.{res.appid}")

            app_list_dir = Path(steam_path) / "AppList"
            app_list_dir.mkdir(exist_ok=True)

            def write_once(appid_str: str):
                for txt in app_list_dir.glob("*.txt"):
                    if txt.read_text(encoding="utf-8").strip() == appid_str:
                        return
                idx = max((int(p.stem) for p in app_list_dir.glob("*.txt")), default=-1) + 1
                (app_list_dir / f"{idx}.txt").write_text(appid_str, encoding="utf-8")
                self.log_sig.emit(f"AppList → {idx}.txt : {appid_str}")

            write_once(str(res.appid))

            dlc_entries = self.data.get("dlc_entries", [])
            dlc_ids = [e.split('=', 1)[0] for e in dlc_entries]
            for dlc in dlc_ids:
                write_once(dlc)
            if dlc_ids:
                self.log_sig.emit(f"DLC 已追加：{' '.join(dlc_ids)}")

            is_lua_script = self.data.get("is_lua_script", False)
            if is_lua_script and res.has_lua and isinstance(res.lua_content, str):
                lua_dir = Path(steam_path) / "config" / "stplug-in"
                lua_dir.mkdir(parents=True, exist_ok=True)
                lua_file = lua_dir / f"{res.appid}.lua"
                lua_file.write_text(res.lua_content, encoding='utf-8')
                self.log_sig.emit(f"Lua 脚本已写出 → {lua_file}")

            return True
        except Exception as e:
            self._async_msg("crit", "部署失败", f"CW 部署失败:\n{e}")
            return False

    def _deploy_auth(self, src_folder: str, steam_path: str) -> bool:
        own_dir = Path(steam_path) / "AppOwnershipTickets"
        enc_dir = Path(steam_path) / "EncryptedAppTickets"
        own_dir.mkdir(exist_ok=True)
        enc_dir.mkdir(exist_ok=True)

        appid = self.data.get("appid", "")
        if appid:
            try:
                app_list_dir = Path(steam_path) / "AppList"
                app_list_dir.mkdir(exist_ok=True)
                for txt_file in app_list_dir.glob("*.txt"):
                    if txt_file.read_text(encoding="utf-8").strip() == appid:
                        break
                else:
                    existing = sorted(app_list_dir.glob("*.txt"), key=lambda p: int(p.stem))
                    next_index = 0 if not existing else int(existing[-1].stem) + 1
                    (app_list_dir / f"{next_index}.txt").write_text(appid, encoding="utf-8")
                    self.log_sig.emit(f"已生成主 AppList：{appid}")
            except Exception as e:
                self.log_sig.emit(f"生成 AppList 失败：{e}")

        try:
            for fname in os.listdir(src_folder):
                src_file = Path(src_folder) / fname
                if not src_file.is_file(): continue
                if fname.startswith("Ticket."):
                    shutil.copy2(src_file, own_dir / fname)
                    self.log_sig.emit(f"拷贝 → {fname}")
                elif fname.startswith("EncryptedTicket."):
                    shutil.copy2(src_file, enc_dir / fname)
                    self.log_sig.emit(f"拷贝 → {fname}")

            if appid in self._SPECIAL_APP_LIST:
                self._write_extra_appid(steam_path, appid)
            return True
        except Exception as e:
            self._async_msg("crit", "部署失败", f"拷贝授权文件出错：\n{e}")
            return False

    def _write_extra_appid(self, steam_path: str, main_appid: str) -> None:
        app_list_dir = Path(steam_path) / "AppList"
        app_list_dir.mkdir(exist_ok=True)
        existing = sorted(app_list_dir.glob("*.txt"), key=lambda p: int(p.stem))
        next_idx = 0 if not existing else int(existing[-1].stem) + 1
        for dlc_id in self._SPECIAL_APP_LIST[main_appid]:
            for txt_file in app_list_dir.glob("*.txt"):
                try:
                    if txt_file.read_text(encoding="utf-8").strip() == str(dlc_id):
                        break
                except Exception:
                    continue
            else:
                target = app_list_dir / f"{next_idx}.txt"
                target.write_text(str(dlc_id), encoding="utf-8")
                next_idx += 1
                self.log_sig.emit(f"已追加特殊 DLC AppID → {target}")

    def _inject_gl(self, steam_path: str) -> bool:
        src_gl = Path(__file__).with_name("GreenLuma").resolve()
        if not src_gl.is_dir():
            self._async_msg("crit", "错误", "同目录下未找到 GreenLuma 文件夹")
            return False

        self._kill_steam_and_wait()

        self._backup_file(Path(steam_path) / "xinput1_4.dll")
        self._backup_file(Path(steam_path) / "dwmapi.dll")
        self._backup_file(Path(steam_path) / "bin" / "x86launcher.exe")

        file_list = [
            "GreenLuma2026_Files", "DLLInjector.exe", "DLLInjector.ini",
            "GreenLuma_2026_x64.dll", "GreenLuma_2026_x86.dll", "GreenLumaSettings_2026.exe",
            "x86launcher.exe"
        ]

        dst_path = Path(steam_path)
        try:
            for item in file_list:
                src = src_gl / item
                dst = dst_path / item
                if src.is_dir():
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
            self.log_sig.emit("GreenLuma 文件已复制完成")
        except Exception as e:
            self._async_msg("crit", "注入失败", f"复制文件出错：\n{e}")
            return False

        src_launcher = dst_path / "x86launcher.exe"
        bin_dir = dst_path / "bin"
        bin_dir.mkdir(exist_ok=True)
        if src_launcher.exists():
            try:
                shutil.move(str(src_launcher), str(bin_dir / "x86launcher.exe"))
            except Exception as e:
                self.log_sig.emit(f"移动 x86launcher.exe 失败：{e}")
        return True

    def _backup_file(self, file_path: Path) -> None:
        if not file_path.exists(): return
        backup_path = file_path.with_suffix(file_path.suffix + ".backup")
        try:
            backup_path.unlink(missing_ok=True)
            file_path.rename(backup_path)
            self.log_sig.emit(f"已备份 {file_path.name}")
        except Exception as e:
            self.log_sig.emit(f"备份 {file_path.name} 失败 (可能被占用)：{e}")

    def _kill_steam_and_wait(self) -> None:
        self.log_sig.emit("正在关闭Steam相关进程...")
        for proc in ("steam.exe", "steamwebhelper.exe", "x86launcher.exe", "DLLInjector.exe"):
            try:
                subprocess.run(["taskkill", "/F", "/IM", proc], capture_output=True, timeout=3)
            except Exception:
                pass
        time.sleep(1.5)

    def _run_restore_logic(self) -> None:
        steam_path = Page2.get_steam_path()
        if not steam_path: return
        self._kill_steam_and_wait()

        self.log_sig.emit("开始清理 GL 环境...")
        sp = Path(steam_path)

        tasks = [
            ("文件", sp / "DLLInjector.exe"),
            ("文件", sp / "DLLInjector.ini"),
            ("文件", sp / "GreenLuma_2026_x64.dll"),
            ("文件", sp / "GreenLuma_2026_x86.dll"),
            ("文件", sp / "GreenLumaSettings_2026.exe"),
            ("文件夹", sp / "GreenLuma2026_Files"),
        ]

        for kind, target in tasks:
            if not target.exists(): continue
            for attempt in range(5):
                try:
                    if kind == "文件夹":
                        shutil.rmtree(target, ignore_errors=False)
                    else:
                        target.unlink(missing_ok=False)
                    self.log_sig.emit(f"已删除 {kind}：{target.name}")
                    break
                except Exception:
                    time.sleep(1)
            else:
                self.log_sig.emit(f"警告：无法删除 {target.name}，可能仍被占用。")

        backups = [
            (sp / "xinput1_4.dll.backup", sp / "xinput1_4.dll"),
            (sp / "dwmapi.dll.backup", sp / "dwmapi.dll"),
            (sp / "bin" / "x86launcher.exe.backup", sp / "bin" / "x86launcher.exe")
        ]
        for backup_file, original_file in backups:
            if backup_file.exists():
                try:
                    if original_file.exists():
                        original_file.unlink(missing_ok=True)
                    backup_file.rename(original_file)
                    self.log_sig.emit(f"已还原备份：{original_file.name}")
                except Exception as e:
                    self.log_sig.emit(f"还原 {original_file.name} 失败：{e}")
            else:
                if original_file.name != "x86launcher.exe" and "launcher" not in str(original_file):
                    try:
                        original_file.unlink(missing_ok=True)
                    except:
                        pass

        for folder in ("AppOwnershipTickets", "EncryptedAppTickets", "AppList"):
            f = sp / folder
            if f.exists():
                shutil.rmtree(f, ignore_errors=True)
                self.log_sig.emit(f"已清理缓存：{folder}")

        self.log_sig.emit("GL 环境清理完成！")
        self._run_steambtools_after_cleanup()

    def _run_steambtools_after_cleanup(self) -> None:
        PROC_NAME = "SteamTools.exe"
        REG_KEY = r"Software\Valve\Steamtools"
        REG_VAL = "SteamPath"

        for p in psutil.process_iter(["pid", "name"]):
            if p.info["name"] and p.info["name"].lower() == PROC_NAME.lower():
                try:
                    psutil.Process(p.info["pid"]).terminate()
                except:
                    pass

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as key:
                path = winreg.QueryValueEx(key, REG_VAL)[0]
                if path:
                    exe_path = os.path.join(path, PROC_NAME)
                    if os.path.isfile(exe_path):
                        subprocess.Popen([exe_path, "/tray"], cwd=path)
                        self.log_sig.emit(f"[+] 已重启 SteamTools")
        except Exception:
            self.log_sig.emit("跳过 SteamTools 启动")


class Page2(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self._init_ui()
        self.worker_thread: Optional[QThread] = None
        self.worker: Optional[Page2Worker] = None
        self.cw_result: Optional[DecryptResult] = None
        self.dlc_entries = []
        self.is_lua_script = False

    def _init_ui(self) -> None:
        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        self.folder_edit.setPlaceholderText("拖放“GL授权”文件夹 或 *.cw")
        self.folder_edit.setContextMenuPolicy(Qt.NoContextMenu)

        self.browse_btn = QPushButton("浏览")
        self.steamid_edit = QLineEdit()
        self.steamid_edit.setPlaceholderText("无需填写自动解析")
        self.steamid_edit.setReadOnly(True)
        self.appid_edit = QLineEdit()
        self.appid_edit.setPlaceholderText("无需填写自动解析")
        self.appid_edit.setReadOnly(True)

        self.run_btn = QPushButton("一键授权(会先自动注入GL)")
        self.fix_btn = QPushButton("e0报错尝试修复")
        self.restore_btn = QPushButton("自动删除GL失败则点这手动删除GL环境")

        for btn in (self.run_btn, self.fix_btn, self.restore_btn):
            btn.setMinimumHeight(46)
        self._set_btn_style(self.run_btn, "#20c997", "#12b886")
        self._set_btn_style(self.fix_btn, "#74c0fc", "#4dabf7")
        self._set_btn_style(self.restore_btn, "#f03e3e", "#c92a2a")

        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(10)

        def add_row(label: str, edit: QLineEdit, btn: Optional[QPushButton] = None) -> None:
            h = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setFixedWidth(100)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            h.addWidget(lbl)
            h.addWidget(edit)
            if btn:
                h.addWidget(btn)
            lay.addLayout(h)

        add_row("GL授权文件：", self.folder_edit, self.browse_btn)
        add_row("SteamID：", self.steamid_edit)
        add_row("AppID：", self.appid_edit)

        lay.addWidget(QLabel("日志："))
        lay.addWidget(self.log_edit)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self.fix_btn)
        btn_row.addWidget(self.restore_btn)
        lay.addLayout(btn_row)

        self.browse_btn.clicked.connect(self.browse_folder)
        self.run_btn.clicked.connect(lambda: self.start_worker_task("auth"))
        self.restore_btn.clicked.connect(lambda: self.start_worker_task("restore"))
        self.fix_btn.clicked.connect(self.write_reg)

    @staticmethod
    def _set_btn_style(btn: QPushButton, bg: str, hover: str) -> None:
        btn.setStyleSheet(f"""
            QPushButton{{background:{bg};border:none;border-radius:8px;padding:8px 12px;font-size:14px;font-weight:bold;color:white;}}
            QPushButton:hover{{background:{hover};}}
            QPushButton:pressed{{background:{hover};}}
            QPushButton:disabled{{background:#adb5bd;color:#e9ecef;}}
        """)

    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        if e.mimeData().hasUrls() and e.mimeData().urls()[0].isLocalFile():
            path = e.mimeData().urls()[0].toLocalFile()
            if os.path.isdir(path) or path.lower().endswith(".cw"):
                e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent) -> None:
        path = e.mimeData().urls()[0].toLocalFile()
        if os.path.isdir(path):
            self.folder_edit.setText(path)
            self.scan_ticket_and_parse(path)
        elif path.lower().endswith(".cw"):
            self.handle_cw_drop(path)

    def browse_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择“GL授权”文件夹")
        if path:
            self.folder_edit.setText(path)
            self.scan_ticket_and_parse(path)
        else:
            path, _ = QFileDialog.getOpenFileName(self, "选择 *.cw", "", "CW files (*.cw)")
            if path:
                self.handle_cw_drop(path)

    def start_worker_task(self, task_type: str) -> None:
        if task_type == "auth":
            if hasattr(self.window(), "download_cw_by_auth_code"):
                cw_path = self.window().download_cw_by_auth_code(self)
                if cw_path:
                    self.handle_cw_drop(str(cw_path))

            src_path = self.folder_edit.text().strip()
            if not src_path:
                QMessageBox.warning(self, "提示", "请先选择正确的“GL授权”文件夹 或 *.cw")
                return

        self.run_btn.setEnabled(False)
        self.fix_btn.setEnabled(False)
        self.restore_btn.setEnabled(False)

        if task_type == "restore":
            self.restore_btn.setText("正在清理GL环境...")

        task_data = {
            "src_path": self.folder_edit.text().strip(),
            "appid": self.appid_edit.text().strip(),
            "cw_result": self.cw_result,
            "dlc_entries": self.dlc_entries,
            "is_lua_script": getattr(self, 'is_lua_script', False)
        }

        self.worker_thread = QThread()
        self.worker = Page2Worker(task_type, task_data)
        self.worker.moveToThread(self.worker_thread)

        self.worker.log_sig.connect(self._on_worker_log)
        self.worker.msg_async_sig.connect(self._on_worker_msg_async)
        self.worker.ask_sync_sig.connect(self._on_worker_ask, Qt.BlockingQueuedConnection)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished_sig.connect(self._on_worker_finished)
        self.worker.finished_sig.connect(self.worker_thread.quit)
        self.worker.finished_sig.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()

    # ================= 绑定给线程的槽函数 =================
    @Slot(str)
    def _on_worker_log(self, msg: str):
        """主线程安全地更新日志框"""
        self.log_edit.append(msg)

    @Slot(str, str, str)
    def _on_worker_msg_async(self, msg_type: str, title: str, text: str):
        if msg_type == "info":
            QMessageBox.information(self, title, text)
        elif msg_type == "warn":
            QMessageBox.warning(self, title, text)
        else:
            QMessageBox.critical(self, title, text)

    @Slot(str, str, object)
    def _on_worker_ask(self, title: str, text: str, result_dict: dict):
        """安全同步提问弹窗：使用 dict 防止传值拷贝失效"""
        ans = QMessageBox.question(self, title, text)
        result_dict["ans"] = (ans == QMessageBox.Yes)

    @Slot(bool)
    def _on_worker_finished(self, success):
        self.run_btn.setEnabled(True)
        self.fix_btn.setEnabled(True)
        self.restore_btn.setEnabled(True)
        self.restore_btn.setText("自动删除GL失败则点这手动删除GL环境")

        # 新增：一键授权任务结束后，自动执行一次 e0 修复（写注册表）
        if hasattr(self, 'worker') and self.worker and self.worker.task_type == "auth":
            if success:
                self.log_edit.append("一键授权完成，自动执行 e0 修复...")
                self.write_reg()
            else:
                self.log_edit.append("一键授权未完全成功，跳过自动 e0 修复")

    # -------------------- e0 修复 --------------------
    def write_reg(self) -> None:
        appid = self.appid_edit.text().strip()
        steamid_str = self.steamid_edit.text().strip()
        if not appid or not steamid_str:
            QMessageBox.warning(self, "提示", "AppID 或 SteamID 为空")
            return
        steamid_qword = str_to_int64(steamid_str)
        if steamid_qword <= 0:
            QMessageBox.warning(self, "提示", "SteamID 格式非法")
            return
        try:
            key_path = rf"Software\Valve\Steam\Apps\{appid}"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, "steamID", 0, winreg.REG_QWORD, steamid_qword)
            self.log_edit.append(f"已写入注册表：HKCU\\{key_path} → steamID(QWORD) = {steamid_qword}")
            QMessageBox.information(self, "完成", "尝试修复成功，不包100%！")
        except Exception as e:
            self.log_edit.append(f"修复失败：{e}")
            QMessageBox.critical(self, "错误", f"修复失败：\n{e}")

    def manual_clean_env(self):
        """手动清理游戏目录残留文件"""
        exe_path = self.exe_edit.text().strip()
        if not exe_path:
            QMessageBox.warning(self, "提示", "请先拖入或浏览选择游戏主程序（.exe）！")
            return

        game_dir = Path(exe_path).parent
        if not game_dir.exists():
            QMessageBox.warning(self, "提示", "未找到该游戏所在的目录路径！")
            return

        # 为了防止dll或文件被游戏占用，先尝试结束游戏进程
        exe_name = Path(exe_path).name
        if exe_name:
            try:
                subprocess.run(["taskkill", "/F", "/IM", exe_name], capture_output=True)
                subprocess.run(["taskkill", "/F", "/IM", "CrashReport.exe"], capture_output=True)
                time.sleep(0.5)
            except Exception:
                pass

        targets_to_remove = [
            "steam_settings",
            "GameOverlayRenderer64.dll",
            "version.dll"
        ]

        cleaned_any = False
        log(self.log_edit, "=== 开始手动清理游戏目录旧版残留文件 ===")
        for target in targets_to_remove:
            target_path = game_dir / target
            if target_path.exists():
                cleaned_any = True
                try:
                    if target_path.is_dir():
                        shutil.rmtree(target_path, ignore_errors=True)
                    else:
                        target_path.unlink(missing_ok=True)
                    log(self.log_edit, f"  [-] 已成功清理: {target}")
                except Exception as e:
                    log(self.log_edit, f"  [x] 清理 {target} 失败 (可能文件被占用): {e}")

        if cleaned_any:
            log(self.log_edit, "手动清理执行完成。")
            QMessageBox.information(self, "清理完成", "残留文件清理执行完毕！\n详情请查看日志。")
        else:
            log(self.log_edit, "目录很干净，未发现需要清理的残留文件。")
            QMessageBox.information(self, "提示", "未发现需要清理的残留文件。")

    def scan_ticket_and_parse(self, folder: str) -> None:
        try:
            files = [f for f in os.listdir(folder) if f.startswith("Ticket.")]
            if not files: return
            ticket_path = os.path.join(folder, files[0])
            with open(ticket_path, "rb") as f:
                data = f.read()
            steam_id = self.parse_hex_for_steamid(bytes2hex(data))
            app_id = self.parse_hex_for_appid(bytes2hex(data))
            self.steamid_edit.setText(str(steam_id) if steam_id else "")
            self.appid_edit.setText(str(app_id) if app_id else "")
            self.cw_result = None
            if steam_id and app_id:
                self.log_edit.append(f"已解析 SteamID：{steam_id}  |  AppID：{app_id}")
        except Exception:
            self.steamid_edit.clear()
            self.appid_edit.clear()

    def handle_cw_drop(self, path: str):
        try:
            res = self._decrypt_cw_for_page2(path)
        except Exception as e:
            QMessageBox.warning(self, "CW 解密失败", str(e))
            return
        self.cw_result = res
        self.folder_edit.setText(path)
        self.steamid_edit.setText(str(res.steam_id))
        self.appid_edit.setText(str(res.appid))
        self.log_edit.append(f"CW 解析成功 → AppID：{res.appid} | SteamID：{res.steam_id}")
        self.dlc_entries, self.is_lua_script = self._extract_dlc_ids_from_cw(res)

    def _extract_dlc_ids_from_cw(self, res: DecryptResult) -> Tuple[List[str], bool]:
        if not res.lua_content: return [], False
        lines, in_dlcs, entries = res.lua_content.splitlines(), False, []
        for line in lines:
            line = line.strip()
            if line == "[app::dlcs]":
                in_dlcs = True
                continue
            if in_dlcs:
                if line.startswith("[") and line.endswith("]"): break
                if "=" in line: entries.append(line.strip())
        if entries:
            return entries, False
        import re
        ids = re.findall(r"addappid\s*\(\s*(\d+)\s*,", res.lua_content)
        if ids:
            ids = list(dict.fromkeys(ids))
            entries = [f"{dlc}=1" for dlc in ids]
            return entries, True
        return [], False

    def _decrypt_cw_for_page2(self, path: str) -> DecryptResult:
        data = Path(path).read_bytes()
        iv = data[:16]
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
        cipher = AES.new(AES_KEY, AES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(data[16:]), AES.block_size)
        pos = 0
        if decrypted[pos:pos + 4] != b"CWSQ": raise ValueError("无效文件头 (不是 CWSQ 格式)")
        pos += 4
        timestamp, json_len = struct.unpack("<Qi", decrypted[pos:pos + 12])
        pos += 12
        json_bytes = decrypted[pos:pos + json_len]
        cw = __import__("json").loads(json_bytes.decode("utf-8"))
        meta = cw["metadata"]
        auth = cw["auth_data"]
        ext = cw.get("extensions", {})
        lua_text_1 = ext.get("dlcs", "")
        lua_sec = cw.get("lua_script", {})
        lua_text_2 = lua_sec.get("content", "") if lua_sec.get("enabled") else ""
        lua_content = (lua_text_1 or lua_text_2) if not (lua_text_1 and lua_text_2) else f"{lua_text_1}\n{lua_text_2}"
        return DecryptResult(
            appid=meta["appid"], steam_id=meta["steam_id"],
            timeout_start=meta["created_timestamp"], timeout_end=meta["expires_timestamp"],
            ticket=bytes.fromhex(auth["app_ticket"]), encrypted_ticket=bytes.fromhex(auth["encrypted_ticket"]),
            lua_content=lua_content, has_lua=bool(lua_content)
        )

    @staticmethod
    def parse_hex_for_steamid(hex_spaced: str) -> Optional[int]:
        try:
            data = bytes.fromhex(hex_spaced.replace(" ", ""))
            if len(data) < 24: return None
            (_, _, steam_id, _, _, _) = struct.unpack("<I I Q I H H", data[:24])
            return steam_id
        except Exception:
            return None

    @staticmethod
    def parse_hex_for_appid(hex_spaced: str) -> Optional[int]:
        try:
            data = bytes.fromhex(hex_spaced.replace(" ", ""))
            if len(data) < 24: return None
            (_, _, _, app_id, _, _) = struct.unpack("<I I Q I H H", data[:24])
            return app_id
        except Exception:
            return None

    @staticmethod
    def get_steam_path() -> Optional[str]:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam") as key:
                return winreg.QueryValueEx(key, "InstallPath")[0]
        except Exception:
            return None



# ------------------------------------------------------------------
# 工具函数：bytes → 空格 hex
# ------------------------------------------------------------------
def bytes2hex(data: bytes) -> str:
    return " ".join(f"{b:02x}" for b in data)


# ------------------------------------------------------------------
# Page4：其他工具
# ------------------------------------------------------------------
# ------------------------------------------------------------------
# Page4：其他工具
# ------------------------------------------------------------------
class Page4(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._init_ui()

    # -------------------- UI --------------------
    def _init_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(20)

        # 标题
        title_label = QLabel("其他工具")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        lay.addWidget(title_label)

        # 说明文本
        description = QLabel("以下是一些有用的工具链接，点击即可访问")
        description.setAlignment(Qt.AlignCenter)
        description.setStyleSheet("font-size: 14px; color: #7f8c8d;")
        lay.addWidget(description)
        lay.addSpacing(30)

        # 按钮容器
        button_container = QVBoxLayout()
        button_container.setSpacing(15)

        # 统一立体白色按钮样式
        btn_style = """
            QPushButton{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f0f0f0);
                border: 1px solid #c0c0c0;
                border-radius: 8px;
                padding: 12px;
                font-size: 14px;
                font-weight: bold;
                color: #212529;
                /* 立体阴影 */
                box-shadow: 2px 2px 4px rgba(0,0,0,20%);
            }
            QPushButton:hover{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #fdfdfd, stop:1 #e6e6e6);
                border-color: #a0a0a0;
            }
            QPushButton:pressed{
                background: #e6e6e6;
                border-color: #909090;
                /* 按下轻微下沉 */
                padding-top: 13px;
                padding-bottom: 11px;
            }
        """

        def add_btn(text, url, h=50):
            btn = QPushButton(text)
            btn.setMinimumHeight(h)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(lambda: self.open_website(url))
            button_container.addWidget(btn)

        add_btn("菜玩CW文件提取网站版", "https://cw.520301.xyz/", 60)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #ecf0f1; margin: 15px 0;")
        button_container.addWidget(line)

        add_btn("Steam Toolbox", "https://pan.quark.cn/s/1eec761aebf6")
        add_btn("清单提取器 v1.1", "https://pan.quark.cn/s/6a437de94e05")
        add_btn("D授权器+D授权提取工具", "https://pan.quark.cn/s/ff679bd595bf")
        add_btn("入库工具VIP版", "https://pan.quark.cn/s/4cc81bf8225c")
        add_btn("使用教程", "https://caigamer.cn/thread-11056.htm")

        button_container.addStretch()
        lay.addLayout(button_container)

    # -------------------- 通用打开网站函数 --------------------
    def open_website(self, url: str) -> None:
        import webbrowser
        try:
            webbrowser.open(url)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开浏览器: {e}")

# ------------------------------------------------------------------
# 主窗口
# ------------------------------------------------------------------
class MainWin(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setWindowTitle("Denuvo 一键授权器 v4.2 by：B-I-A-O")
        self.setFixedSize(800, 650)
        self.setWindowIcon(QIcon(resource_path("icon.ico")))

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # 添加所有页面
        self.tabs.addTab(Page1(), "tools一键授权(gbe)")
        self.tabs.addTab(Page2(), "tools一键授权(GL)")
        self.tabs.addTab(Page4(), "其他工具")  # 新增的页面



        bar = QToolBar(self)
        bar.setMovable(False)
        bar.setFloatable(False)
        sponsor_act = QAction("☕ 请作者喝奶茶~", self)
        sponsor_act.triggered.connect(self._show_sponsor)
        bar.addAction(sponsor_act)
        self.addToolBar(Qt.TopToolBarArea, bar)

        self.setStyleSheet("""
                QMainWindow{background:#f8f9fa;}

                QLineEdit{
                    border:1px solid #ced4da;border-radius:6px;padding:6px 8px;
                    font-size:13px;background:#ffffff;
                    color:#212529;
                }
                QLineEdit:focus{border-color:#4dabf7;}

                QTextEdit{
                    border:1px solid #ced4da;border-radius:6px;padding:4px;
                    font-size:12px;background:#ffffff;
                    color:#212529;
                }

                QPushButton{
                    background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #20c997,stop:1 #12b886);
                    border:none;border-radius:8px;padding:8px 12px;
                    font-size:14px;font-weight:bold;color:white;
                }
                QPushButton:hover{background:#12b886;}
                QPushButton:pressed{background:#0ca678;}

                QLabel{font-size:13px;color:#212529;}

                QTabWidget::pane{ border: none; }
                QTabBar::tab{
                    background:#e9ecef;
                    border:1px solid #dee2e6;
                    border-bottom:none;
                    border-top-left-radius:8px;
                    border-top-right-radius:8px;
                    padding:8px 18px;
                    margin-right:4px;
                    font-size:14px;
                    color:#212529;
                }
                QTabBar::tab:selected{
                    background:#ffffff;
                    border-color:#ced4da;
                    border-bottom:1px solid #ffffff;
                    color:#212529;
                    font-weight:bold;
                }
                QTabBar::tab:!selected{ margin-top:3px; }
                QTabBar::tab:hover:!selected{background:#f1f3f5;}

                /* ===== 工具栏黑色文字 ===== */
                QToolBar{background:#f8f9fa;color:#212529;}
                QToolButton{color:#212529;background:transparent;border:none;padding:4px;font-size:14px;}
                QToolButton:hover{background:#e9ecef;}
                """)

        # ===== 新增：全局授权码（三页通用） =====
        bar.addSeparator()
        self.auth_code_edit = QLineEdit()
        self.auth_code_edit.setFixedWidth(200)
        self.auth_code_edit.setPlaceholderText("菜玩授权码只有第二页有用")
        bar.addWidget(self.auth_code_edit)

        # ===== 字体透明修复（仅此两行） =====
        self._force_safe_font()
        self._patch_style_font_family()

    # -------------------------------------------------
    # 字体修复：强制安全字体 + 补全样式表字体族
    # -------------------------------------------------
    def _force_safe_font(self) -> None:
        from PySide6.QtGui import QFont
        font = QFont()
        font.setFamilies(["Microsoft YaHei", "PingFang SC", "SimSun", "Segoe UI", "Arial"])
        font.setPixelSize(14)
        self.setFont(font)
        for w in self.findChildren(QWidget):
            w.setFont(font)

    def _patch_style_font_family(self) -> None:
        style = self.styleSheet()
        selectors = ["QLabel", "QPushButton", "QLineEdit", "QTextEdit", "QTabBar::tab"]
        for sel in selectors:
            if sel in style and "font-family" not in style:
                style = style.replace(
                    sel + "{",
                    sel + '{font-family:"Microsoft YaHei","PingFang SC","SimSun",sans-serif !important;'
                )
        self.setStyleSheet(style)

    # -------------------------------------------------
    # 原赞助弹窗
    # -------------------------------------------------
    def _show_sponsor(self) -> None:
        from PySide6.QtWidgets import QHBoxLayout
        import alipay_qrc  # 新增支付宝
        import sponsor_qrc  # 原有微信

        dlg = QDialog(self)
        dlg.setWindowTitle("制作不易，感谢支持 有bug联系Q3309638756")
        dlg.setFixedSize(700, 400)  # 加宽，左右两张图
        lay = QVBoxLayout(dlg)

        # 上方提示
        tip = QLabel("感谢支持")
        tip.setAlignment(Qt.AlignCenter)
        lay.addWidget(tip)

        # 中间图片区
        hbox = QHBoxLayout()

        # 微信原图
        wx_pm = QPixmap()
        wx_pm.loadFromData(base64.b64decode(sponsor_qrc.SPONSOR_PNG))
        wx_lbl = QLabel()
        wx_lbl.setPixmap(wx_pm.scaled(280, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        wx_lbl.setAlignment(Qt.AlignCenter)
        hbox.addWidget(wx_lbl)

        # 支付宝新图
        ali_pm = QPixmap()
        ali_pm.loadFromData(base64.b64decode(alipay_qrc.ALIPAY_PNG))
        ali_lbl = QLabel()
        ali_lbl.setPixmap(ali_pm.scaled(280, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        ali_lbl.setAlignment(Qt.AlignCenter)
        hbox.addWidget(ali_lbl)

        lay.addLayout(hbox)

        # 底部关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dlg.accept)
        lay.addWidget(close_btn)
        dlg.exec()

    # -------------------- 三页通用：授权码下载 CW（实时日志） --------------------
    def download_cw_by_auth_code(self, parent: QWidget) -> Optional[Path]:
        from pathlib import Path
        import tempfile, requests, hashlib
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad

        code = self.auth_code_edit.text().strip()
        if not code:
            return None

        log_widget = parent.log_edit
        log(log_widget, f"正在使用授权码 '{code}' 下载 CW ...")
        parent.repaint()          # 立即刷新界面

        AES_KEY = hashlib.sha256(b"af0a3329787c9e6a6f3a1b69f841fd09a67cdfcade8b182d67a4442357815f60").digest()

        try:
            # 1. 拉域名
            log(log_widget, "正在获取远程 API 域名 ...")
            parent.repaint()
            domain = requests.get("https://api.ksmlc.cn/SteamUnlockFileManager/version.json", timeout=10).json()["cw_web"]
            log(log_widget, f"API 域名：{domain}")
            parent.repaint()

            # 2. 下载
            log(log_widget, "开始下载授权文件 ...")
            parent.repaint()
            rsp = requests.get(f"https://{domain}/api/auth/{code}/download", timeout=15)
            rsp.raise_for_status()
            if not rsp.content:
                raise ValueError("授权码无效或已过期")

            # 3. 解密 & 落盘
            data = rsp.content
            iv, cipher = data[:16], data[16:]
            plain = unpad(AES.new(AES_KEY, AES.MODE_CBC, iv).decrypt(cipher), 16)
            if plain[:4] != b"CWSQ":
                raise ValueError("不是合法 CW 文件")
            tmp = Path(tempfile.gettempdir()) / f"{code}.cw"
            tmp.write_bytes(data)
            log(log_widget, f"下载成功，已保存至：{tmp}")
            return tmp

        except Exception as e:
            log(log_widget, f"授权码下载失败：{e}")
            QMessageBox.critical(parent, "授权码下载失败", str(e))
            return None

# ------------------------------------------------------------------
# 统一启动入口（与 GUI.py 保持一致）
# ------------------------------------------------------------------
def perform_version_check():
    """返回 (has_new:bool|None, msg:str)"""
    try:
        from version_checker import VersionChecker
    except ImportError:
        return None, "版本检查模块未找到"

    vc = VersionChecker()
    result = [None, None]

    def on_check_done(has_new, msg):
        result[0], result[1] = has_new, msg

    vc.check_done.connect(on_check_done)

    # 事件循环同步等待
    from PySide6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    vc.check_done.connect(lambda *_: loop.quit())
    timeout = QTimer(singleShot=True)
    timeout.timeout.connect(loop.quit)

    vc.start_check()
    timeout.start(10_000)  # 10 秒超时
    loop.exec()

    return result[0], result[1]

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # ========== 启动时强制版本检测 ==========
    has_new, msg = perform_version_check()

    if has_new is True:
        reply = QMessageBox.question(
            None,
            "发现新版本",
            f"{msg}\n\n是否立即更新？\n\n如果不更新，应用将退出。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            VersionChecker.open_download_page()
        sys.exit(0)

    elif has_new is False:
        # 无新版，正常启动主界面
        win = MainWin()
        qr = win.frameGeometry()
        qr.moveCenter(win.screen().availableGeometry().center())
        win.move(qr.topLeft())
        win.show()
        sys.exit(app.exec())

    else:
        # 检测失败
        QMessageBox.critical(
            None,
            "版本检测失败",
            f"无法检测应用版本:\n\n{msg}\n\n请检查网络连接后重试。\n\n应用即将退出。"
        )
        sys.exit(1)