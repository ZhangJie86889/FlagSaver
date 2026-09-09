# -*- coding: utf-8 -*-
"""
Flag 倒计时 · 普通全屏窗口版（非系统屏保 .scr）
==============================================
为什么这样改：Windows 的 .scr 屏保运行在独立的「屏保/安全桌面」，该桌面
不加载任何第三方中文输入法(IME)，所以在原屏保里只能打英文字母、无法拼音。
本程序改为「普通全屏窗口 + 空闲检测」：它运行在普通桌面，IME 正常加载，
因此在屏保界面里也能用拼音输入中文。

行为：
  - 双模式：直接运行（双击 exe）→ 启动后立即全屏显示；带 /bg 参数 → 常驻后台隐藏，
    等空闲满 IDLE_SECONDS（默认 5 分钟）后自动全屏显示（适合开机自启）；
  - 在界面里按 Esc 或点右上角 ✕（网页调 quit_saver）即隐藏，下次空闲再显示；
  - 立 flag 的输入框可正常拼音输入（普通桌面 IME 可用）；
  - flag.html / flag_data.json 与本程序同目录，整个文件夹可整体拷贝、跨机器使用。
与 flag.html 的对接：沿用 window.pywebview.api.read_flags / write_flags / quit_saver。
"""
import os
import sys
import ctypes
import threading
import time

import webview

# 命令行模式：
#   FlagSaver.exe            -> 手动运行：启动后立即全屏弹出
#   FlagSaver.exe /bg        -> 后台模式：开机自启用，隐藏等空闲再弹
BG_MODE = ('/bg' in sys.argv) or ('--bg' in sys.argv)

# 路径自动定位：打包成 exe 后取 exe 所在目录；源码运行取脚本所在目录。
# flag.html 与 flag_data.json 都与本程序放在同一目录，整个文件夹可整体拷贝到任何机器使用。
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

HTML_PATH = os.path.join(BASE_DIR, 'flag.html')
JSON_PATH = os.path.join(BASE_DIR, 'flag_data.json')
IDLE_SECONDS = 5 * 60  # 空闲 5 分钟触发全屏

# ---------------- 窗口引用与显隐 ----------------
_window = None
_shown = False


def _set_window(w):
    global _window
    _window = w


def show_window():
    global _shown
    try:
        if _window is not None:
            # 注意：pywebview 的 toggle_fullscreen() 不接受参数，调用 toggle_fullscreen(True)
            # 会静默抛 TypeError。这里改用 fullscreen 属性直接强制全屏，确保空闲到点后真正全屏。
            try:
                _window.fullscreen = True
            except Exception:
                pass
            _window.show()
    except Exception:
        pass
    _shown = True


def hide_window():
    global _shown
    try:
        if _window is not None:
            _window.hide()
    except Exception:
        pass
    _shown = False


# ---------------- 与 flag.html 对接的 JS API ----------------
class Api:
    def read_flags(self):
        """返回 flag_data.json 文本内容（网页负责解析）。"""
        try:
            with open(JSON_PATH, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return '[]'
        except Exception:
            return '[]'

    def write_flags(self, text):
        """网页立 flag 后回写 json。"""
        try:
            d = os.path.dirname(JSON_PATH)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(JSON_PATH, 'w', encoding='utf-8') as f:
                f.write(text)
            return True
        except Exception:
            return False

    def quit_saver(self):
        """网页(JS)调用：退出「屏保」（隐藏窗口），下次空闲再显示。"""
        hide_window()


# ---------------- 空闲检测（GetLastInputInfo） ----------------
class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_uint)]


def get_idle_ms():
    li = LASTINPUTINFO()
    li.cbSize = ctypes.sizeof(li)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li))
    now = ctypes.windll.kernel32.GetTickCount()
    return (now - li.dwTime) & 0xFFFFFFFF


def monitor_loop():
    """后台线程：空闲达到阈值就显示窗口。"""
    while True:
        try:
            idle = get_idle_ms() / 1000.0
            if (not _shown) and idle >= IDLE_SECONDS:
                show_window()
        except Exception:
            pass
        time.sleep(2)


def on_loaded():
    """窗口创建后回调（主线程）：手动运行则立即全屏显示，后台模式先隐藏，再启动空闲监控。"""
    _set_window(webview.windows[0])
    if BG_MODE:
        hide_window()
    else:
        show_window()
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()


def already_running():
    """单实例：用 Windows 命名互斥量防止多开（开机自启 + 手动双击不会重复弹窗）。"""
    try:
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\FlagSaverSingleton")
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            return True
    except Exception:
        pass
    return False


if __name__ == '__main__':
    if already_running():
        sys.exit(0)
    webview.create_window(
        'Flag 倒计时',
        url=HTML_PATH,
        js_api=Api(),
        on_top=True,
        fullscreen=False,
    )
    webview.start(func=on_loaded, debug=False)
