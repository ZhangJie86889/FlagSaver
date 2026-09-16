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

v1.1.1 修复（详见 PR ./CHANGELOG_v1.1.1.md）：
  ① 重复双击不再「静默失败」：程序已在后台运行时，第二次双击会通知已有实例把窗口
     呼出来（命名事件），而不是直接 sys.exit(0) 什么都不提示；
  ② 热键线程只负责收消息，窗口显隐交给单独线程串行执行 —— 窗口调用万一卡住也不会
     让热键永久失效；且所有窗口操作带超时保护；
  ③ 所有 except 不再静默吞掉，一律写入日志；日志补上日期（原来只有时分秒，跨天没法查）；
  ④ 热键被占用自动顺延时，把实际生效的键写回 config.json 并记录，设置面板显示真实键；
  ⑤ 单实例互斥量由 Global\\ 改为 Local\\（Global 命名对象在非管理员下可能创建失败，
     导致单实例保护形同虚设）；
  ⑥ 顺延备选热键换成 Win+Shift / Ctrl+Shift / F9 这类冷门组合（原表里 ctrl+alt+d/s/1
     等在很多软件和输入法里都被占用，顺延过去基本等于白试）。
v1.2.0：新增「月历视图」（全部在 flag.html 侧实现），Flag 数据多了一个 plan_date
  字段表示「计划在哪一天执行」。后端 API 与存储路径都没有变 —— read_flags /
  write_flags 本来就是原样透传 JSON 文本、不做字段白名单，所以本文件除了版本号
  之外无需任何改动。详见 ./CHANGELOG_v1.2.0.md。
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

APP_VERSION = '1.2.0'
WINDOW_TITLE = 'Flag 倒计时'

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


# ---------------- 日志（排障用，写程序目录 flagsaver.log） ----------------
# 必须先于 load_config 定义：配置读写失败时要用它记日志。
LOG_PATH = os.path.join(BASE_DIR, 'flagsaver.log')


def _log(msg):
    """带日期的日志。原来只写时分秒，跨天根本没法定位问题。"""
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write('%s %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg))
    except Exception:
        pass        # 日志本身绝不能影响主流程


DEFAULT_CONFIG = {
    'idle_seconds': 300,        # 空闲多少秒后自动弹出（0 = 关闭空闲弹出）
    'hotkey': 'ctrl+alt+g',     # Windows 全局热键，例如 ctrl+alt+g / win+shift+f
    'auto_time': '',            # 每天定时弹出，格式 "HH:MM"，留空关闭
    'autostart': False,         # 是否随 Windows 登录自动启动（/bg 模式）
    'hotkey_active': '',        # 上一次实际注册成功的热键（被占用自动顺延时与 hotkey 不同）
}

# 热键被其它软件占用时的自动顺延顺序。
# 注意：优先 Win+Shift / Ctrl+Shift / F9 这类冷门组合。ctrl+alt+单字母 在中文输入法、
# 截图工具、QQ/微信、游戏启动器里非常容易被占用，顺延到那些键基本等于白试。
HOTKEY_FALLBACKS = [
    'ctrl+alt+g', 'win+shift+g', 'ctrl+shift+g', 'alt+shift+g',
    'ctrl+alt+f9', 'ctrl+shift+f9', 'win+shift+f9', 'ctrl+alt+q',
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
    except FileNotFoundError:
        pass        # 首次运行还没有 config.json，属正常情况，不记日志
    except Exception as e:
        _log('load_config 读取失败，已改用默认配置: %r' % (e,))
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        _log('save_config 失败: %r' % (e,))
        return False


CFG = load_config()


# ---------------- Win32 句柄类 API 的调用约定 ----------------
# 注意：不显式声明 restype 时 ctypes 按 c_int 处理返回值，64 位句柄会被截断并导致崩溃。
_k32 = ctypes.WinDLL('kernel32', use_last_error=True)
_u32 = ctypes.WinDLL('user32', use_last_error=True)

_k32.CreateMutexW.restype = ctypes.c_void_p
_k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
_k32.CreateEventW.restype = ctypes.c_void_p
_k32.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p]
_k32.OpenEventW.restype = ctypes.c_void_p
_k32.OpenEventW.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_wchar_p]
_k32.SetEvent.argtypes = [ctypes.c_void_p]
_k32.SetEvent.restype = ctypes.c_int
_k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
_k32.WaitForSingleObject.restype = ctypes.c_uint
_k32.CloseHandle.argtypes = [ctypes.c_void_p]
_k32.CloseHandle.restype = ctypes.c_int


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


# ---------------- 显隐请求队列 + 专用执行线程 ----------------
# 为什么要这样拆：热键线程一旦在窗口调用里被卡住（跨线程操作窗口的经典风险），
# 它就再也回不到消息循环，热键会**永久失效**，而空闲自动弹（另一个线程）照常工作，
# 现象非常难查。现在热键线程只往队列里丢一个动作，真正的窗口操作由 window_loop
# 单独串行执行，并且带超时保护。
_pending_lock = threading.Lock()
_pending = []


def _request(action):
    """把显隐动作排队（'show' / 'hide' / 'toggle'）。任何线程都可以安全调用。"""
    with _pending_lock:
        if len(_pending) > 4:
            _log('显隐请求堆积(%d)，丢弃最旧的一个' % len(_pending))
            _pending.pop(0)
        _pending.append(action)


def _take_request():
    with _pending_lock:
        return _pending.pop(0) if _pending else None


def _run_guarded(fn, timeout=8.0):
    """带超时执行窗口操作：即便 pywebview 的窗口调用卡住，也不会把执行线程拖死。"""
    done = threading.Event()

    def _worker():
        try:
            fn()
        except Exception as e:
            _log('窗口操作异常: %r' % (e,))
        finally:
            done.set()

    threading.Thread(target=_worker, daemon=True).start()
    if not done.wait(timeout):
        _log('窗口操作超时(>%.0fs)，已放弃本次 —— 若反复出现请把本行反馈给作者' % timeout)


def window_loop():
    """专用线程：串行执行所有窗口显隐动作。"""
    while True:
        try:
            act = _take_request()
            if act == 'toggle':
                _log('toggle_window: shown=%s' % _shown)
                _run_guarded(hide_window if _shown else show_window)
            elif act == 'show':
                _run_guarded(show_window)
            elif act == 'hide':
                _run_guarded(hide_window)
        except Exception as e:
            _log('window_loop 异常: %r' % (e,))
        time.sleep(0.05)


def toggle_window():
    """显隐切换（兼容旧调用）：只入队，由 window_loop 执行。"""
    _request('toggle')


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
    except Exception as e:
        _log('set_autostart 失败: %r' % (e,))
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
        except Exception as e:
            _log('write_flags 失败: %r' % (e,))
            return False

    def quit_saver(self):
        """网页(JS)调用：退出「屏保」（隐藏窗口），下次空闲再显示。"""
        _request('hide')

    def read_config(self):
        """设置面板读取配置（JSON 字符串）。"""
        cfg = dict(CFG)
        cfg['autostart'] = get_autostart()
        cfg['idle_minutes'] = round(CFG.get('idle_seconds', 0) / 60.0, 2)
        # 实际生效的热键（被占用时会与 hotkey 不同）；优先用本次运行的真实值
        cfg['hotkey_active'] = _hotkey_active or CFG.get('hotkey_active', '')
        cfg['version'] = APP_VERSION
        return json.dumps(cfg, ensure_ascii=False)

    def write_config(self, text):
        """设置面板保存配置：空闲时间 / 全局热键 / 定时弹出。"""
        global CFG
        try:
            data = json.loads(text)
        except Exception as e:
            _log('write_config 解析失败: %r' % (e,))
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
    _u32.GetLastInputInfo(ctypes.byref(li))
    now = _k32.GetTickCount()
    return (now - li.dwTime) & 0xFFFFFFFF


_auto_fired_date = ''


def monitor_loop():
    """后台线程：响应另一个实例的呼出请求 / 空闲达到阈值 / 到达每日定时。"""
    global _auto_fired_date
    while True:
        try:
            # 0) 有别的实例被双击启动 → 它发来了「呼出窗口」请求
            if _take_show_request():
                _log('收到另一个实例的呼出请求')
                _request('show')

            cfg = CFG
            # 1) 空闲触发
            idle_seconds = int(cfg.get('idle_seconds', 300) or 0)
            if idle_seconds > 0 and (not _shown):
                if get_idle_ms() / 1000.0 >= idle_seconds:
                    _request('show')
            # 2) 每天定时触发
            auto_time = (cfg.get('auto_time') or '').strip()
            if auto_time and (not _shown):
                now = time.localtime()
                hhmm = time.strftime('%H:%M', now)
                today = time.strftime('%Y-%m-%d', now)
                if hhmm == auto_time and _auto_fired_date != today:
                    _auto_fired_date = today
                    _request('show')
        except Exception as e:
            _log('monitor_loop 异常: %r' % (e,))
        time.sleep(1)


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


def _remember_active(active):
    """把实际生效的热键记下来：写日志 + 落 config.json，供设置面板显示真实值。"""
    global _hotkey_active
    _hotkey_active = active or ''
    if _hotkey_active and CFG.get('hotkey_active') != _hotkey_active:
        CFG['hotkey_active'] = _hotkey_active
        save_config(CFG)


def hotkey_loop():
    """注册系统级热键并跑消息循环；配置变更时自动重新注册。

    本线程只做「注册 + 收消息 + 入队」，绝不直接操作窗口，
    以免窗口调用卡住后连热键一起失效。
    """
    global _hotkey_dirty, _hotkey_current
    user32 = _u32

    class MSG(ctypes.Structure):
        _fields_ = [('hwnd', ctypes.c_void_p), ('message', ctypes.c_uint),
                    ('wParam', ctypes.c_size_t), ('lParam', ctypes.c_ssize_t),
                    ('time', ctypes.c_uint), ('ptX', ctypes.c_long), ('ptY', ctypes.c_long)]

    def register(mods, vk):
        if vk is None:
            return False
        return bool(user32.RegisterHotKey(None, HOTKEY_ID, mods, vk))

    def unregister():
        try:
            user32.UnregisterHotKey(None, HOTKEY_ID)
        except Exception as e:
            _log('UnregisterHotKey 异常: %r' % (e,))

    def register_with_fallback(preferred):
        """优先用配置的热键；被占用（1409）则自动顺延到下一个可用组合。"""
        order = [preferred] + [h for h in HOTKEY_FALLBACKS if h != preferred]
        for hk in order:
            mods, vk = parse_hotkey(hk)
            if vk is None:
                _log('热键 %r 无法解析，跳过' % (hk,))
                continue
            if register(mods, vk):
                return hk, mods, vk
            _log('hotkey %s 注册失败(err=%s)，尝试下一个' % (hk, ctypes.get_last_error()))
        return None, 0, 0

    active, mods, vk = register_with_fallback(CFG.get('hotkey'))
    _hotkey_current = (mods, vk) if active else None
    _remember_active(active)
    if active:
        _log('hotkey active: %s (配置 %s)%s' % (active, CFG.get('hotkey'),
                                                '' if active == CFG.get('hotkey') else ' <- 被占用，已自动顺延'))
        if active != CFG.get('hotkey'):
            _log('提示：请在设置面板里把热键改成 %s，否则每次启动都会先撞一次被占用的键' % active)
    else:
        _log('hotkey register FAILED for all candidates（所有候选热键都被占用）')

    msg = MSG()
    PM_REMOVE = 0x0001
    while True:
        try:
            if _hotkey_dirty:
                _hotkey_dirty = False
                unregister()
                active, m2, v2 = register_with_fallback(CFG.get('hotkey'))
                _hotkey_current = (m2, v2) if active else None
                _remember_active(active)
                _log('hotkey re-registered: %s' % (active or '(none)'))
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                if msg.message == WM_HOTKEY:
                    _log('WM_HOTKEY received')
                    _request('toggle')      # 只入队，本线程不碰窗口
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception as e:
            _log('hotkey_loop 异常: %r' % (e,))
        time.sleep(0.2)


# ---------------- 单实例（互斥量 + 唤醒事件） ----------------
ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = 'Local\\FlagSaverSingleton'
SHOW_EVENT_NAME = 'Local\\FlagSaverShowEvent'
EVENT_MODIFY_STATE = 0x0002
WAIT_OBJECT_0 = 0x00000000

# 注意：用 Local\ 而不是 Global\。Global 命名对象在非管理员账户下可能直接创建失败
# （GetLastError = 5 而非 183），单实例保护会形同虚设。
_instance_mutex = None      # 句柄要一直持有到进程结束，不要 CloseHandle
_show_event = None


def _acquire_single_instance():
    """True = 本进程是唯一实例，继续启动；
    False = 已有实例在跑（此时已通知它把窗口呼出来），本进程直接退出。"""
    global _instance_mutex, _show_event
    _instance_mutex = _k32.CreateMutexW(None, False, MUTEX_NAME)
    err = ctypes.get_last_error()
    if not _instance_mutex:
        _log('CreateMutexW 失败(err=%s)，跳过单实例检查' % err)
        return True
    if err == ERROR_ALREADY_EXISTS:
        # 已有实例：请它把窗口呼出来，本进程退出。这样用户双击 exe 就是「呼出」，而不是没反应。
        ev = _k32.OpenEventW(EVENT_MODIFY_STATE, False, SHOW_EVENT_NAME)
        if ev:
            _k32.SetEvent(ctypes.c_void_p(ev))
            _k32.CloseHandle(ctypes.c_void_p(ev))
            _log('已有实例在运行 -> 已通知它呼出窗口，本进程退出')
        else:
            _log('已有实例在运行，但通知失败(err=%s)' % ctypes.get_last_error())
        return False
    _show_event = _k32.CreateEventW(None, False, False, SHOW_EVENT_NAME)   # 自动重置事件
    if not _show_event:
        _log('CreateEventW 失败(err=%s)' % ctypes.get_last_error())
    return True


def _take_show_request():
    """另一个实例（双击 exe）请求呼出窗口时返回 True（读事件时自动重置）。"""
    if not _show_event:
        return False
    return _k32.WaitForSingleObject(ctypes.c_void_p(_show_event), 0) == WAIT_OBJECT_0


# ---------------- 启动 ----------------
def on_loaded():
    """窗口创建后回调：手动运行则立即全屏显示，后台模式先隐藏，再启动监控与热键。"""
    _set_window(webview.windows[0])
    if BG_MODE:
        hide_window()
    else:
        show_window()
    for fn in (monitor_loop, window_loop, hotkey_loop):
        threading.Thread(target=fn, daemon=True).start()


if __name__ == '__main__':
    _log('=== FlagSaver v%s 启动 | 模式=%s | 目录=%s ===' %
         (APP_VERSION, '后台(/bg)' if BG_MODE else '前台', BASE_DIR))
    if not _acquire_single_instance():
        sys.exit(0)
    if not os.path.exists(CONFIG_PATH):
        save_config(CFG)
    webview.create_window(
        WINDOW_TITLE,
        url=HTML_PATH,
        js_api=Api(),
        on_top=True,
        fullscreen=False,
    )
    webview.start(func=on_loaded, debug=False)
