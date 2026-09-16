# -*- coding: utf-8 -*-
"""打包 Windows 开箱即用压缩包：FlagSaver-Windows-v1.2.0.zip

用法：
    python build_zip.py [源码/产物目录]

目录里需要已经有打好的 FlagSaver.exe（PyInstaller 产物）以及 flag.html / README.md 等。
不传目录时默认使用本脚本所在目录 —— 这样别人 clone 下来也能直接跑，不必改路径。
"""
import os
import shutil
import sys
import zipfile

SRC = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
STAGE = os.path.join(SRC, '_zip_stage', 'FlagSaver-Windows')
OUT_DIR = os.path.join(SRC, '_zip_out')
ZIP_NAME = 'FlagSaver-Windows-v1.2.0.zip'

GUIDE = """FlagSaver · 立 Flag 倒计时屏保（Windows 版）
==========================================

【最快开始】
1. 把整个文件夹解压到任意位置（建议不要放在需要管理员权限的目录，如 C:\\Program Files）
2. 双击 FlagSaver.exe  ->  立刻全屏弹出 Flag 倒计时界面

【三种唤起方式】
1) 直接双击 FlagSaver.exe       ：启动后立即全屏显示
                                  程序已经在后台跑着时，再双击 = 把窗口呼出来
                                  （同一时间只会有一个实例，不会重复开）
2) 全局热键 Ctrl+Alt+G（默认）  ：Windows 任何界面按一下立刻呼出，再按一次隐藏
                                  （若与其它软件冲突，程序会自动换用下一个可用组合，
                                    实际生效的是哪个键写在 flagsaver.log 里，
                                    设置面板也会显示，并在启动时弹一次提示）
3) 空闲 / 定时自动弹出          ：默认空闲 5 分钟弹出，可在界面右上角 ⚙ 里改

【月历视图（v1.2.0 新增）】
界面往下滚，Flag 卡片下面是月历：
- 点任意一天 -> 下方展开「当天面板」，看这一天的任务，也能直接加任务
- 有任务的日子在格子上显示一个小圆点 + 任务数量；当天任务全做完时圆点变绿
- 今天用暖色数字 + 底部横条标出
- 上下月用「今天 / ‹ / ›」按钮切换，键盘也能走：
    Tab 进月历 -> 方向键移动 -> Enter 打开面板 -> Esc 只关面板
    Home/End = 本周一/本周日，PageUp/PageDown = 上/下个月
- 两个日期各管各的：
    「截止日」= 这件事什么时候到期（卡片上的倒计时）
    「计划日」= 打算哪一天动手（决定它出现在月历的哪一格）
  加任务时截止日可以留空，留空就等于计划当天。
- 过去的日子可以查看，但不能往那天加新任务。
- 注意：Esc 优先关「当天面板」，面板关掉之后 Esc 才恢复为「隐藏屏保」。

【⚙ 设置面板（界面右上角齿轮）】
- 空闲多久自动弹出（分钟，0 = 关闭）
- 全局热键（如 ctrl+alt+g、win+shift+g）
- 每天定时弹出（如 22:30，留空关闭）
- 开机自启（勾选即写入 Windows 注册表启动项）
所有设置立即生效，保存在程序目录 config.json，无需重新打包。

【设置开机自启（空闲自动弹）】
1. Win + R 输入 shell:startup 回车，打开「启动」文件夹
2. 右键 FlagSaver.exe -> 发送到 -> 桌面快捷方式
3. 把桌面上的快捷方式拖进「启动」文件夹
4. 右键该快捷方式 -> 属性 -> 目标 末尾加上空格和 /bg，例如：
   "D:\\FlagSaver\\FlagSaver.exe" /bg

【目录里的文件】
- FlagSaver.exe        主程序（Windows x64，无需安装 Python）
- flag.html            全屏界面（时钟 / Flag 卡片 / 月历，可自行用浏览器/编辑器修改，改完重启程序生效）
- flag_data.example.json  数据格式示例
- LICENSE / README.md  开源信息与说明
- CHANGELOG_v1.2.0.md  本版更新说明（月历视图）
- config.json / flagsaver.log  首次运行自动生成（个人配置与运行日志）

【数据存储】
Flag 数据保存在程序同目录的 flag_data.json，程序首次「立 Flag」时会自动创建。
整个文件夹可以直接拷到 U 盘 / 另一台电脑，数据随身带走。
从旧版升级：直接覆盖 flag.html 即可，老数据不用改；第一次打开后每条数据会多出一个
空的 plan_date 字段（计划执行日），旧 Flag 的日期和显示完全不变。

【常见问题】
Q: 双击没反应？
A: 分两种情况：
   ① 程序已经在后台运行了 —— 它会直接把窗口呼出来，不会再开第二个窗口。
      如果窗口没出来，看任务管理器里有没有 FlagSaver.exe，有就说明在跑。
   ② 被 Windows「智能应用控制」拦下来了 —— 本程序未签名，从网上下载的 exe 可能
      被系统拦截（现象就是双击毫无反应、也没有任何报错）。处理办法：
      右键 FlagSaver.exe -> 属性 -> 勾选底部「解除锁定」-> 确定，再试一次；
      仍然不行就只能关闭智能应用控制（设置 -> 隐私和安全性 -> Windows 安全中心 ->
      应用和浏览器控制 -> 智能应用控制），注意关闭后只有重装 Windows 才能再打开。
      或者直接用源码跑：pip install pywebview && python saver_window.py /bg
Q: 想改空闲触发时间 / 热键 / 定时？
A: 界面右上角 ⚙ 设置面板里改，立即生效，不用改代码。
Q: 热键按了没反应？
A: 按顺序查三件事：
   ① 程序在不在跑（全局热键必须有常驻进程，任务管理器里看不到就没用）；
   ② 你按的是不是「实际生效」的那个键 —— 设置面板里的热键若被别的软件占用，
      程序会自动顺延到下一个可用组合，此时 ⚙ 面板里显示的就是实际生效的键，
      启动时也会弹提示；按面板里显示的那个键；
   ③ 还是不行就看 flagsaver.log，里面写明了注册成功的是哪个组合、以及有没有收到按键。
Q: 月历上的某天点不动 / 加不了任务？
A: 已经过去的日子只能查看，不能加新任务（这是有意的，避免把已过去的日子填满）。
   要加任务请点今天或之后的日期。
Q: 升级后月历上没看到我的旧 Flag？
A: 旧数据没有「计划日」，程序会自动按它的「截止日」来摆位置，所以请翻到对应月份查看。
   想在别的日子看到它，点进去把它删掉、再在新的日子重新加一条即可。
Q: 怎么退出全屏？
A: 按 Esc 或点界面上的 ×，窗口隐藏，下次空闲会再弹出；彻底退出在任务栏托盘/任务管理器结束进程。
   注意：如果「当天面板」开着，第一次 Esc 只关面板，再按一次才隐藏窗口。
"""

def main():
    # 不做整体删除（避免误触批量删除保护），直接覆盖同名文件即可
    os.makedirs(STAGE, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    for f in ['FlagSaver.exe', 'flag.html', 'flag_data.example.json', 'LICENSE', 'README.md',
              'CHANGELOG_v1.2.0.md']:
        shutil.copy2(os.path.join(SRC, f), os.path.join(STAGE, f))

    with open(os.path.join(STAGE, '使用说明.txt'), 'w', encoding='utf-8') as fh:
        fh.write(GUIDE)

    zip_path = os.path.join(OUT_DIR, ZIP_NAME)
    if os.path.exists(zip_path):
        # 目录里已有旧包时先删掉。若被其它程序占用（比如正在解压）会删不掉，
        # 这里不让它中断构建 —— 下面的 ZipFile(..., 'w') 本身就会覆盖目标文件。
        try:
            os.remove(zip_path)
        except OSError as e:
            print('  ! 旧包删除失败（%s），将直接覆盖：%s' % (type(e).__name__, zip_path))
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for root, _, files in os.walk(os.path.join(SRC, '_zip_stage')):
            for fn in files:
                full = os.path.join(root, fn)
                arc = os.path.relpath(full, os.path.join(SRC, '_zip_stage'))
                z.write(full, arc)
                print('  +', arc)
    print('ZIP:', zip_path, round(os.path.getsize(zip_path) / 1024 / 1024, 2), 'MB')

if __name__ == '__main__':
    main()
