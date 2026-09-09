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
    等空闲满设定时间后自动全屏显示（适合开机自启）；
  - 在界面里按 Esc 或点右上角 ✕（网页调 quit_saver）即隐藏，下次空闲再显示；
  - 立 flag 的输入框可正常拼音输入（普通桌面 IME 可用）；
  - flag.html / flag_data.json / config.json 与本程序同目录，整体可拷贝、跨机器使用。

关联到 Windows 系统的三件事：
  1. 全局热键：RegisterHotKey 注册系统级热键，任何界面按下都能立刻呼出/隐藏屏保；
  2. 开机自启：写 HKCU\\...\\Run 注册表项（带 /bg 参数），登录即后台常驻；
  3. 空闲检测：GetLastInputInfo 取系统空闲时长，达到阈值自动弹出。

与 flag.html 的对接 JS API：
  read_flags / write_flags / quit_saver / read_config / write_config / set_autostart
"""
import os
import re
import sys
import json
import time
import ctypes
import threading
import winreg

import webview

# 命令行模式：
#   FlagSaver.exe            -> 手动运行：启动后立即全屏弹出
#   FlagSaver.exe /bg        -> 后台模式：开机自启用，隐藏等空闲再弹
BG_MODE = ('/bg' in sys.argv) or ('--bg' in sys.argv)

# 路径自动定位：打包成 exe 后取 exe 所在目录；源码运行取脚本所在目录。
# flag.html / flag_data.json / config.json 都与本程序同目录，整个文件夹可整体拷贝使用。
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

HTML_PATH = os.path.join(BASE_DIR, 'flag.html')
JSON_PATH = os.path.join(BASE_DIR, 'flag_data.json')
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')

DEFAULT_CONFIG = {
    'idle_seconds': 300,        # 空闲多少秒后自动弹出（0 = 关闭空闲弹出）
    'hotkey': 'ctrl+alt+g',     # Windows 全局热键，例如 ctrl+alt+g / win+shift+f
    'auto_time': '',            # 每天定时弹出，格式 "HH:MM"，留空关闭
    'autostart': False,         # 是否随 Windows 登录自动启动（/bg 模式）
}

# 热键被其它软件占用时的自动顺延顺序（注册失败会依次尝试，并把实际生效的写进日志/设置面板）
HOTKEY_FALLBACKS = [
    'ctrl+alt+g', 'ctrl+alt+f', 'ctrl+shift+g', 'ctrl+alt+d',
    'win+alt+g', 'win+shift+g', 'ctrl+alt+s', 'ctrl+alt+1',
]

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_NAME = 'FlagSaver'


# ---------------- 配置读写 ----------------
def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            for k in DEFAULT_CONFIG:
                if k in data:
                    cfg[k] = data[k]
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


CFG = load_config()


# ---------------- 日志（排障用，写程序目录 flagsaver.log） ----------------
LOG_PATH = os.path.join(BASE_DIR, 'flagsaver.log')


def _log(msg):
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write('%s %s\n' % (time.strftime('%H:%M:%S'), msg))
    except Exception:
        pass


# ---------------- 窗口引用与显隐 ----------------
_window = None
_shown = False


def _set_window(w):
    global _window
    _window = w


def show_window():
    global _shown
    try:
        if _window is None:
            _log('show_window: window is None')
            return
        # 注意：pywebview 的 toggle_fullscreen() 不接受参数，调用 toggle_fullscreen(True)
        # 会静默抛 TypeError。这里改用 fullscreen 属性直接强制全屏。
        try:
            _window.fullscreen = True
        except Exception as e:
            _log('fullscreen err: %r' % (e,))
        _log('show_window: calling show, shown=%s' % _shown)
        _window.show()
        _log('show_window: done')
    except Exception as e:
        _log('show_window err: %r' % (e,))
    _shown = True


def hide_window():
    global _shown
    try:
        if _window is not None:
            _log('hide_window: calling hide')
            _window.hide()
    except Exception as e:
        _log('hide_window err: %r' % (e,))
    _shown = False


def toggle_window():
    """全局热键触发：已显示则隐藏，未显示则全屏弹出。"""
    _log('toggle_window: shown=%s' % _shown)
    if _shown:
        hide_window()
    else:
        show_window()


# ---------------- Windows 开机自启（注册表） ----------------
def _launch_cmd():
    if getattr(sys, 'frozen', False):
        return '"%s" /bg' % sys.executable
    return '"%s" "%s" /bg' % (sys.executable, os.path.abspath(__file__))


def set_autostart(enabled):
    try:
        if enabled:
            key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, _launch_cmd())
            winreg.CloseKey(key)
        else:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
            try:
                winreg.DeleteValue(key, RUN_NAME)
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
        return True
    except Exception:
        return False


def get_autostart():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY)
        val, _ = winreg.QueryValueEx(key, RUN_NAME)
        winreg.CloseKey(key)
        return bool(val)
    except Exception:
        return False


# ---------------- 与 flag.html 对接的 JS API ----------------
class Api:
    def read_flags(self):
        """返回 flag_data.json 文本内容（网页负责解析）。"""
        try:
            with open(JSON_PATH, 'r', encoding='utf-8') as f:
                return f.read()
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

    def read_config(self):
        """设置面板读取配置（JSON 字符串）。"""
        cfg = dict(CFG)
        cfg['autostart'] = get_autostart()
        cfg['idle_minutes'] = round(CFG.get('idle_seconds', 0) / 60.0, 2)
        cfg['hotkey_active'] = _hotkey_active   # 实际生效的热键（被占用时会与 hotkey 不同）
        return json.dumps(cfg, ensure_ascii=False)

    def write_config(self, text):
        """设置面板保存配置：空闲时间 / 全局热键 / 定时弹出。"""
        global CFG
        try:
            data = json.loads(text)
        except Exception:
            return False
        try:
            minutes = float(data.get('idle_minutes', data.get('idle_seconds', 300) / 60.0))
        except Exception:
            minutes = 5.0
        new_cfg = dict(CFG)
        new_cfg['idle_seconds'] = int(max(0, minutes) * 60)
        new_cfg['hotkey'] = str(data.get('hotkey', '') or '').strip().lower()
        new_cfg['auto_time'] = str(data.get('auto_time', '') or '').strip()
        CFG = new_cfg
        save_config(CFG)
        _mark_hotkey_dirty()   # 热键变了：后台线程会重新注册
        return True

    def set_autostart(self, enabled):
        """开关 Windows 开机自启。"""
        ok = set_autostart(bool(enabled))
        CFG['autostart'] = bool(enabled)
        save_config(CFG)
        return ok


# ---------------- 空闲检测（GetLastInputInfo） ----------------
class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_uint)]


def get_idle_ms():
    li = LASTINPUTINFO()
    li.cbSize = ctypes.sizeof(li)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li))
    now = ctypes.windll.kernel32.GetTickCount()
    return (now - li.dwTime) & 0xFFFFFFFF


_auto_fired_date = ''


def monitor_loop():
    """后台线程：空闲达到阈值 / 到达每日定时，就显示窗口。"""
    global _auto_fired_date
    while True:
        try:
            cfg = CFG
            # 1) 空闲触发
            idle_seconds = int(cfg.get('idle_seconds', 300) or 0)
            if idle_seconds > 0 and (not _shown):
                if get_idle_ms() / 1000.0 >= idle_seconds:
                    show_window()
            # 2) 每天定时触发
            auto_time = (cfg.get('auto_time') or '').strip()
            if auto_time and (not _shown):
                now = time.localtime()
                hhmm = time.strftime('%H:%M', now)
                today = time.strftime('%Y-%m-%d', now)
                if hhmm == auto_time and _auto_fired_date != today:
                    _auto_fired_date = today
                    show_window()
        except Exception:
            pass
        time.sleep(2)


# ---------------- Windows 全局热键（RegisterHotKey） ----------------
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN = 0x0001, 0x0002, 0x0004, 0x0008
WM_HOTKEY = 0x0312
HOTKEY_ID = 1
_hotkey_dirty = False
_hotkey_current = None
_hotkey_active = ''   # 实际生效的热键（可能与配置不同，被占用时自动顺延）


def parse_hotkey(text):
    """'ctrl+alt+f' -> (mods, vk)；vk 为 None 表示解析失败。"""
    parts = [p.strip().lower() for p in re.split(r'[+\s]+', str(text or '')) if p.strip()]
    mods, vk = 0, None
    for p in parts:
        if p in ('ctrl', 'control'):
            mods |= MOD_CONTROL
        elif p in ('alt', 'menu'):
            mods |= MOD_ALT
        elif p == 'shift':
            mods |= MOD_SHIFT
        elif p in ('win', 'super', 'meta'):
            mods |= MOD_WIN
        else:
            m = re.match(r'^f(\d{1,2})$', p)
            if m:
                n = int(m.group(1))
                if 1 <= n <= 24:
                    vk = 0x6F + n
            elif len(p) == 1:
                vk = ord(p.upper())
    return mods, vk


def _mark_hotkey_dirty():
    global _hotkey_dirty
    _hotkey_dirty = True


def hotkey_loop():
    """注册系统级热键并跑消息循环；配置变更时自动重新注册。"""
    global _hotkey_dirty, _hotkey_current
    user32 = ctypes.windll.user32

    class MSG(ctypes.Structure):
        _fields_ = [('hwnd', ctypes.c_void_p), ('message', ctypes.c_uint),
                    ('wParam', ctypes.c_size_t), ('lParam', ctypes.c_ssize_t),
                    ('time', ctypes.c_uint), ('ptX', ctypes.c_long), ('ptY', ctypes.c_long)]

    global _hotkey_active

    def register(mods, vk):
        if vk is None:
            return False
        return bool(user32.RegisterHotKey(None, HOTKEY_ID, mods, vk))

    def unregister():
        try:
            user32.UnregisterHotKey(None, HOTKEY_ID)
        except Exception:
            pass

    def register_with_fallback(preferred):
        """优先用配置的热键；被占用（1409）则自动顺延到下一个可用组合。"""
        order = [preferred] + [h for h in HOTKEY_FALLBACKS if h != preferred]
        for hk in order:
            mods, vk = parse_hotkey(hk)
            if vk is None:
                continue
            if register(mods, vk):
                return hk, mods, vk
            _log('hotkey %s 注册失败(err=%s)，尝试下一个' % (hk, ctypes.windll.kernel32.GetLastError()))
        return None, 0, 0

    active, mods, vk = register_with_fallback(CFG.get('hotkey'))
    _hotkey_current = (mods, vk) if active else None
    _hotkey_active = active or ''
    if active:
        _log('hotkey active: %s (配置 %s)%s' % (active, CFG.get('hotkey'),
                                                '' if active == CFG.get('hotkey') else ' <- 被占用，已自动顺延'))
    else:
        _log('hotkey register FAILED for all candidates')

    msg = MSG()
    PM_REMOVE = 0x0001
    while True:
        try:
            if _hotkey_dirty:
                _hotkey_dirty = False
                unregister()
                active, m2, v2 = register_with_fallback(CFG.get('hotkey'))
                _hotkey_current = (m2, v2) if active else None
                _hotkey_active = active or ''
                _log('hotkey re-registered: %s' % (active or '(none)'))
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                if msg.message == WM_HOTKEY:
                    _log('WM_HOTKEY received')
                    toggle_window()
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception:
            pass
        time.sleep(0.2)


# ---------------- 启动 ----------------
def on_loaded():
    """窗口创建后回调（主线程）：手动运行则立即全屏显示，后台模式先隐藏，再启动监控与热键。"""
    _set_window(webview.windows[0])
    if BG_MODE:
        hide_window()
    else:
        show_window()
    threading.Thread(target=monitor_loop, daemon=True).start()
    threading.Thread(target=hotkey_loop, daemon=True).start()


def already_running():
    """单实例：用 Windows 命名互斥量防止多开（开机自启 + 手动双击不会重复弹窗）。"""
    try:
        ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\FlagSaverSingleton")
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            return True
    except Exception:
        pass
    return False


if __name__ == '__main__':
    if already_running():
        sys.exit(0)
    if not os.path.exists(CONFIG_PATH):
        save_config(CFG)
    webview.create_window(
        'Flag 倒计时',
        url=HTML_PATH,
        js_api=Api(),
        on_top=True,
        fullscreen=False,
    )
    webview.start(func=on_loaded, debug=False)
