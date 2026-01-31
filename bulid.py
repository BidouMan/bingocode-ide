import os
import sys
import shutil
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
        "--collect-all=jedi",
        "--collect-all=parso",
    ]

    print(f"🏗️ 正在开始新的打包任务 ({sys.platform})...")
    PyInstaller.__main__.run(params)
    print("\n✨ 打包任务完成！请查看 dist/ 目录。")

if __name__ == "__main__":
    build()