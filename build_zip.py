# -*- coding: utf-8 -*-
"""打包 Windows 开箱即用压缩包：FlagSaver-Windows-v1.0.0.zip"""
import os
import shutil
import zipfile

SRC = r'D:\Desktop\个人文件\FlagSaver'
STAGE = os.path.join(SRC, '_zip_stage', 'FlagSaver-Windows')
OUT_DIR = os.path.join(SRC, '_zip_out')
ZIP_NAME = 'FlagSaver-Windows-v1.1.1.zip'

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
