import os
import sys
import shutil
from pathlib import Path
import PyInstaller.__main__

def build():
    entry_point = "main.py"
    app_name = "BingoCodeIDE"
    spec_file = f"{app_name}.spec"

    cleanup_list = ['build', 'dist', spec_file]
    print("🧹 正在清理旧的构建文件...")
    for item in cleanup_list:
        if os.path.exists(item):
            if os.path.isdir(item): shutil.rmtree(item)
            else: os.remove(item)

    sep = ":" if sys.platform != "win32" else ";"
    params = [
        entry_point,
        f"--name={app_name}",
        "--noconsole",
        "--windowed",
        "--onedir", 
        f"--add-data=assets{sep}assets",
        f"--add-data=modules{sep}modules",
        # "--hidden-import=arcade",
        # "--hidden-import=pyglet",
        "--collect-submodules=arcade",
        # "--collect-all=arcade",  # 🚀 显式收集 arcade 的所有资源文件，解决 VERSION 报错
        "--collect-all=pyglet",

        "--hidden-import=PIL",
        "--hidden-import=PIL.Image",
        "--collect-all=jedi",
        "--collect-all=parso",
    ]

    print(f"🏗️ 正在开始打包任务 ({sys.platform})...")
    PyInstaller.__main__.run(params)

    if sys.platform == "darwin":
        patch_macos_bundle(app_name)

def patch_macos_bundle(app_name):
    print("🍎 正在构建标准嵌套 App 壳子以彻底隐藏 Dock...")
    app_path = Path(f"dist/{app_name}.app")
    contents_path = app_path / "Contents"
    helpers_path = contents_path / "Helpers"
    
    runner_app_path = helpers_path / "ScriptRunner.app"
    runner_contents = runner_app_path / "Contents"
    runner_macos = runner_contents / "MacOS"
    
    if helpers_path.exists(): shutil.rmtree(helpers_path)
    runner_macos.mkdir(parents=True)

    # 软链接指向主程序
    os.symlink(f"../../../../MacOS/{app_name}", runner_macos / "ScriptRunner")

    # 🚀 最终版 Info.plist：确保使用了 <true/> 标签
    runner_plist = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>ScriptRunner</string>
    <key>CFBundleIdentifier</key>
    <string>com.bingo.ide.runner</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleName</key>
    <string>ScriptRunner</string>
    <key>LSUIElement</key>
    <true/>
    <key>LSBackgroundOnly</key>
    <true/>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
"""
    with open(runner_contents / "Info.plist", "w") as f:
        f.write(runner_plist)
    print("✨ 嵌套 App 构建完成。")

if __name__ == "__main__":
    build()