# -*- coding: utf-8 -*-
"""打包 Windows 开箱即用压缩包：FlagSaver-Windows-v1.0.0.zip"""
import os
import shutil
import zipfile

SRC = r'D:\Desktop\个人文件\FlagSaver'
STAGE = os.path.join(SRC, '_zip_stage', 'FlagSaver-Windows')
OUT_DIR = os.path.join(SRC, '_zip_out')
ZIP_NAME = 'FlagSaver-Windows-v1.1.0.zip'

GUIDE = """FlagSaver · 立 Flag 倒计时屏保（Windows 版）
==========================================

【最快开始】
1. 把整个文件夹解压到任意位置（建议不要放在需要管理员权限的目录，如 C:\\Program Files）
2. 双击 FlagSaver.exe  ->  立刻全屏弹出 Flag 倒计时界面

【三种唤起方式】
1) 直接双击 FlagSaver.exe       ：启动后立即全屏显示
2) 全局热键 Ctrl+Alt+G（默认）  ：Windows 任何界面按一下立刻呼出，再按一次隐藏
                                  （若与其它软件冲突，程序会自动换用下一个可用组合，
                                    实际使用的按键记录在 flagsaver.log 里）
3) 空闲 / 定时自动弹出          ：默认空闲 5 分钟弹出，可在界面右上角 ⚙ 里改

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
- flag.html            全屏界面（可自行用浏览器/编辑器修改，改完重启程序生效）
- flag_data.example.json  数据格式示例
- LICENSE / README.md  开源信息与说明
- config.json / flagsaver.log  首次运行自动生成（个人配置与运行日志）

【数据存储】
Flag 数据保存在程序同目录的 flag_data.json，程序首次「立 Flag」时会自动创建。
整个文件夹可以直接拷到 U 盘 / 另一台电脑，数据随身带走。

【常见问题】
Q: 双击没反应？
A: 首次运行可能被 Windows SmartScreen 拦截，点「详细信息 -> 仍要运行」即可。
Q: 想改空闲触发时间 / 热键 / 定时？
A: 界面右上角 ⚙ 设置面板里改，立即生效，不用改代码。
Q: 热键按了没反应？
A: 大概率被别的软件占用了。程序会自动顺延到可用组合，打开 flagsaver.log 能看到
   实际生效的是哪个；也可以自己在 ⚙ 里换一个（比如 win+shift+g）。
Q: 怎么退出全屏？
A: 按 Esc 或点界面上的 ×，窗口隐藏，下次空闲会再弹出；彻底退出在任务栏托盘/任务管理器结束进程。
"""

def main():
    # 不做整体删除（避免误触批量删除保护），直接覆盖同名文件即可
    os.makedirs(STAGE, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    for f in ['FlagSaver.exe', 'flag.html', 'flag_data.example.json', 'LICENSE', 'README.md']:
        shutil.copy2(os.path.join(SRC, f), os.path.join(STAGE, f))

    with open(os.path.join(STAGE, '使用说明.txt'), 'w', encoding='utf-8') as fh:
        fh.write(GUIDE)

    zip_path = os.path.join(OUT_DIR, ZIP_NAME)
    if os.path.exists(zip_path):
        os.remove(zip_path)
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
