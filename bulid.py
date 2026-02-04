import os
import sys
import shutil
from pathlib import Path
import PyInstaller.__main__

def build():
    # 1. 配置项
    entry_point = "main.py"
    app_name = "BingoCodeIDE"
    spec_file = f"{app_name}.spec" # 自动生成的配置文件名

    # 2. 🚀 自动化清理：打包前清理 build, dist 和 spec 文件
    # 这样能保证 100% 解决样式不更新、代码不生效等诡异问题
    cleanup_list = ['build', 'dist', spec_file]
    
    print("🧹 正在清理旧的构建文件...")
    for item in cleanup_list:
        if os.path.exists(item):
            if os.path.isdir(item):
                shutil.rmtree(item)
            else:
                os.remove(item)
            print(f"   已删除: {item}")

    # 3. 路径分隔符
    sep = ":" if sys.platform != "win32" else ";"

    # 4. 重新配置打包参数 (切换到 --onedir 模式以加速启动)
    params = [
        entry_point,
        f"--name={app_name}",
        "--noconsole",
        "--windowed",
        # 🚀 放弃 --onefile，改用 --onedir (默认就是 onedir)
        # 这会让你的 IDE 启动速度像 VSCode 一样快
        "--onedir", 
        
        f"--add-data=assets{sep}assets",
        f"--add-data=modules{sep}modules",

        "--hidden-import=arcade",
        "--hidden-import=pyglet",
        "--hidden-import=PIL",
        "--hidden-import=PIL.Image",
        
  
        "--collect-all=jedi",
        "--collect-all=parso",
    ]

    print(f"🏗️ 正在开始新的打包任务 ({sys.platform})...")
    PyInstaller.__main__.run(params)
    print("\n✨ 打包任务完成！请查看 dist/ 目录。")

    # 🚀 关键：针对 macOS 的双 Bundle 补丁
    if sys.platform == "darwin":
        patch_macos_bundle(app_name)

def patch_macos_bundle(app_name):
    """
    在 .app 内部创建一个隐藏图标的子进程启动器
    """
    print("🍎 正在为 macOS 生成隐身子进程启动器...")
    app_path = Path(f"dist/{app_name}.app")
    contents_path = app_path / "Contents"
    helpers_path = contents_path / "Helpers"
    helpers_path.mkdir(exist_ok=True)

    # 1. 复制主执行文件到 Helpers 目录，改名为 ScriptRunner
    # 这个 ScriptRunner 本质上还是你的 main.py 打包后的程序
    src_exe = contents_path / "MacOS" / app_name
    dest_exe = helpers_path / "ScriptRunner"
    shutil.copy(src_exe, dest_exe)

    # 2. 为 ScriptRunner 创建一个独立的 Info.plist
    # 核心是 LSUIElement = 1，告诉系统这个进程没有 UI 图标
    runner_plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>ScriptRunner</string>
    <key>CFBundleIdentifier</key>
    <string>com.bingo.scriptrunner</string>
    <key>LSUIElement</key>
    <string>1</string>
</dict>
</plist>
"""
    with open(helpers_path / "Info.plist", "w") as f:
        f.write(runner_plist)
    print("✅ 隐身启动器已就位。")

if __name__ == "__main__":
    build()

if __name__ == "__main__":
    build()