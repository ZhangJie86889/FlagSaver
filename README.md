# FlagSaver · 立 Flag 倒计时屏保

> 一个 Windows 桌面「立 Flag」倒计时屏保：全屏展示你的目标清单与剩余天数，空闲自动浮现。
> 用 `pywebview`（HTML + Python）实现，界面暗色毛玻璃质感，可按拼音输入中文目标（普通桌面 IME 可用）。

![screenshot](screenshot.png)

---

## ⬇️ 下载（Windows 免安装）

| 文件 | 说明 |
|---|---|
| **[FlagSaver-Windows-v1.1.0.zip](https://github.com/ZhangJie86889/FlagSaver/releases/download/v1.1.0/FlagSaver-Windows-v1.1.0.zip)** ⭐ | 推荐。解压即用，内含 exe + `flag.html` + 中文《使用说明》 |
| [FlagSaver.exe](https://github.com/ZhangJie86889/FlagSaver/releases/download/v1.1.0/FlagSaver.exe) | 单文件程序，需自行把 `flag.html` 放在同目录 |
| [v1.0.0](https://github.com/ZhangJie86889/FlagSaver/releases/tag/v1.0.0) | 旧版（无设置面板/热键），需要可回退 |

**三步跑起来**：下载 zip → 解压到任意文件夹 → 双击 `FlagSaver.exe`。
> 首次运行若被 Windows SmartScreen 拦截，点「详细信息 → 仍要运行」。
> 想让它在空闲时自动弹出，见下方 [设为开机自启](#-设为开机自启)。

---

## ✨ 特性

- 🖥️ **全屏屏保**：空闲到点自动全屏浮现；按 `Esc` 或点 ✕ 立即隐藏
- ⌨️ **全局热键**：默认 `Ctrl+Alt+G`，Windows 任何界面按一下即呼出，再按隐藏（冲突自动顺延）
- ⏰ **定时弹出**：可设每天固定时刻（如 22:30）自动全屏
- 🔧 **可视化设置**：右上角 ⚙ 面板改空闲时间 / 热键 / 定时 / 开机自启，立即生效，无需重打包
- 🚀 **开机自启**：一键写入 Windows 注册表启动项
- 🎯 **立 Flag**：输入目标 + 截止日期，自动计算剩余天数；支持子任务勾选
- 🏷️ **完成态卡片**：到期的 Flag 卡片变色提醒，一目了然
- ⌨️ **中文输入友好**：运行在普通桌面（非系统 `.scr` 安全桌面），拼音输入法正常可用
- 💾 **本地保存**：数据存 `flag_data.json`，与程序同目录，可整体拷贝、跨机器使用
- 🌐 **浏览器可预览**：单独用 Edge 打开 `flag.html` 也能跑（localStorage / 文件访问降级）

## 🩹 v1.1.1 修复了什么

`saver_window.py` 的健壮性修复，都是实际踩出来的坑：

| # | 问题 | 修复 |
|---|---|---|
| 1 | 程序已在后台运行时**再双击 exe 毫无反应**（`already_running()` 直接 `sys.exit(0)`） | 改用命名事件通知已有实例**把窗口呼出来**，再退出本进程 |
| 2 | 热键线程里直接操作窗口，一旦卡住就**再也收不到热键**（且空闲弹出仍正常，极难排查） | 热键线程只收消息并入队，窗口显隐交给单独线程串行执行，且带超时保护 |
| 3 | 大量 `except Exception: pass` 把错误**全部吞掉**，出问题零线索 | 所有异常一律写日志 |
| 4 | 日志只有 `时:分:秒`，**跨天无法定位** | 改为 `年-月-日 时:分:秒` |
| 5 | 热键被占用自动顺延后，**用户不知道实际生效的是哪个键** | 实际键落 `config.json` 的 `hotkey_active`、设置面板显示真实键、启动时弹提示 |
| 6 | 单实例互斥量用 `Global\` 命名，**非管理员可能创建失败**导致单实例失效 | 改用 `Local\` |
| 7 | 顺延备选表里 `ctrl+alt+d/s/f/1` 在输入法、截图工具、QQ/微信里**普遍被占**，顺延过去基本白试 | 换成 `win+shift+*` / `ctrl+shift+*` / `F9` 这类冷门组合 |

> 完整说明见 [`CHANGELOG_v1.1.1.md`](CHANGELOG_v1.1.1.md)。

## 📁 文件说明

| 文件 | 作用 |
|---|---|
| `saver_window.py` | 主程序源码（pywebview 窗口 + 空闲检测 + JS API） |
| `flag.html` | 界面（时钟 / Flag 卡片 / 立 Flag 表单），纯前端 |
| `flag_data.json` | 你的 Flag 数据（**不入库**，见 `.gitignore`） |
| `flag_data.example.json` | 示例数据，别人 clone 后参考用 |

## 🚀 运行方式

### 双模式

| 方式 | 行为 |
|---|---|
| `FlagSaver.exe`（双击） | 启动后**立即全屏显示** |
| `FlagSaver.exe /bg` | 后台常驻，**空闲到点**后自动全屏（默认 5 分钟，可在 ⚙ 设置里改） |
| 程序已在后台时再双击 | **把已有窗口呼出来**（不会重复开第二个进程，也不会毫无反应） |

> 无论哪种模式，都可以随时用全局热键（默认 `Ctrl+Alt+G`）呼出/隐藏。
>
> **单实例**：同一时间只允许一个实例运行。已在后台运行时再双击 exe，程序不会静默退出，
> 而是通知已有实例把窗口显示出来 —— 所以你随时双击图标都能把屏保叫出来。

### 源码运行

```bash
# 安装依赖
pip install pywebview

# 直接运行（需要 Python 3.x）
python saver_window.py            # 立即全屏
python saver_window.py /bg        # 后台，空闲自动弹
```

### 打包成 exe

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name FlagSaver saver_window.py
```

> 打包后把 `flag.html` 和 `FlagSaver.exe` 放到**同一目录**即可使用（数据会自动生成 `flag_data.json`）。

### 打 Windows 发布包

```bash
python build_zip.py     # 生成 _zip_out/FlagSaver-Windows-v1.1.1.zip（exe + flag.html + 使用说明）
```

## 🚀 设为开机自启

1. `Win + R` 输入 `shell:startup` 回车，打开「启动」文件夹
2. 给 `FlagSaver.exe` 建一个快捷方式拖进去
3. 右键该快捷方式 → 属性 →「目标」末尾加 ` /bg`，例如：`"D:\FlagSaver\FlagSaver.exe" /bg`

> 等效命令行：`reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v FlagSaver /t REG_SZ /d "\"D:\FlagSaver\FlagSaver.exe\" /bg" /f`

## ⚙️ 设置面板 & 关联 Windows 系统

界面右上角 **⚙** 打开设置，改完立刻生效，配置写入程序目录的 `config.json`：

![settings](screenshot_settings.png)

| 选项 | 说明 | 关联到 Windows 的方式 |
|---|---|---|
| **空闲多久弹出** | 单位分钟，`0` = 关闭空闲弹出 | `GetLastInputInfo` 读系统空闲时长 |
| **全局热键** | 默认 `ctrl+alt+g`，任何界面按下即呼出，再按一次隐藏 | `RegisterHotKey` 系统级注册；**若与其它软件冲突会自动顺延**到下一个可用组合 |
| **每天定时弹出** | 例如 `22:30`，留空关闭 | 本地时间比对，每天触发一次 |
| **开机自启** | 勾选即可 | 写 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\FlagSaver`（带 `/bg`） |

`config.json` 示例：

```json
{
  "idle_seconds": 300,
  "hotkey": "ctrl+alt+g",
  "auto_time": "22:30",
  "autostart": true,
  "hotkey_active": "win+shift+g"
}
```

> `hotkey_active` 是**本次实际注册成功**的热键。它和 `hotkey` 不一样，就说明 `hotkey`
> 被别的软件占用了、程序已自动顺延，设置面板会显示 `hotkey_active` 并给出提示。

> **热键按了没反应？** 按顺序查这三件事：
> 1. **程序在不在跑** —— 全局热键必须有常驻进程；任务管理器里看不到 `FlagSaver.exe` 时按什么都没用。
>    双击一下 exe 即可（已在后台时会直接把窗口呼出来）。
> 2. **你按的是不是实际生效的那个键** —— 设置面板里的热键被别的软件占用时，程序会**自动顺延**到下一个可用组合。
>    这种情况下 ⚙ 面板里显示的就是**实际生效的键**，程序启动时也会弹一次提示。按面板里显示的那个键。
> 3. 还是不行就看程序目录的 `flagsaver.log`（带日期），里面写明了注册成功的是哪个组合、以及有没有收到按键。

> **双击 exe 没反应？** 通常是这两种情况：
> ① 程序**已经在后台运行** —— 新版会把窗口呼出来；旧版（≤v1.1.0）会静默退出，看起来就像启动失败。
> ② 被 Windows **智能应用控制**拦下了 —— 本程序未签名，从网上下载的 exe 可能被拦。
>    右键 exe → 属性 → 勾选「解除锁定」；仍不行只能关闭智能应用控制（Win11，**关闭后不可再开启**）或改用源码运行。

## 📄 关于「屏保」

Windows 系统屏保 `.scr` 运行在独立安全桌面，**不加载中文输入法**，打不了拼音。
本项目改用「普通全屏窗口 + 空闲检测」替代：运行在普通桌面，IME 正常加载，因此能拼音输入中文目标。

## 🛠️ 技术栈

- [pywebview](https://pywebview.flowrl.com/) — Python 调 WebView 渲染 HTML
- 空闲检测：`GetLastInputInfo`（Win32）
- 打包：[PyInstaller](https://pyinstaller.org/) `--onefile --noconsole`

---

## 📜 License

[MIT](LICENSE) © 2026 [ZhangJie86889](https://github.com/ZhangJie86889)

_本工具仅供个人学习与娱乐使用。_
