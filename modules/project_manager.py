import os
import tempfile
import shutil

class ProjectManager:
    def __init__(self):
        self.project_root = ''
        self.sprite_dir = None
        self.sound_dir = None
        # 新增：记录代码文件的路径
        self.current_run_target = ""
        
        self.create_temp_project()

    def set_run_target(self, file_path):
        """动态设置当前的运行目标"""
        if file_path and os.path.exists(file_path):
            self.current_run_target = file_path

    def get_run_target(self):
        """获取运行目标：优先级：手动设置 > 存在性检查 > 自动搜寻"""
        # 1. 如果当前记录的路径还有效，直接返回
        if self.current_run_target and os.path.exists(self.current_run_target):
            return self.current_run_target
        
        # 2. 如果失效了（比如文件被删），找项目根目录下第一个 .py
        if self.project_root and os.path.exists(self.project_root):
            py_files = [f for f in os.listdir(self.project_root) if f.endswith('.py')]
            # 排序确保 main.py 优先被选中
            py_files.sort(key=lambda x: (x != "main.py", x.lower()))
            
            if py_files:
                target = os.path.join(self.project_root, py_files[0])
                self.current_run_target = target
                return target
        
        return None

    def create_temp_project(self):
        """在系统临时目录下创建工作空间"""
        self.project_root = tempfile.mkdtemp(prefix="BingoProject_")
        
        # 1. 创建资源目录
        self.sprite_dir = os.path.join(self.project_root, "assets", "sprites")
        self.sound_dir = os.path.join(self.project_root, "assets", "sounds")
        os.makedirs(self.sprite_dir, exist_ok=True)
        os.makedirs(self.sound_dir, exist_ok=True)
        
        # 2. 【核心修改】创建默认的 main.py 文件
        self.main_script_path = os.path.join(self.project_root, "main.py")
        with open(self.main_script_path, "w", encoding="utf-8") as f:
            f.write("# Welcome to BingoIDE\nprint('Hello Bingo!')")
        
        print(f"📁 项目管理器：临时工作区已就绪 -> {self.project_root}")
    
    def create_new_project_env(self):
        """核心逻辑：重置管家状态，创建一个全新的临时地盘"""
        import tempfile
        import datetime
        
        # 1. 生成带时间戳的新目录名
        timestamp = datetime.datetime.now().strftime("%H%M%S")
        self.project_root = tempfile.mkdtemp(prefix=f"BingoProject_{timestamp}_")
        
        # 2. 重建目录结构
        self.main_script_path = os.path.join(self.project_root, "main.py")
        self.sprite_dir = os.path.join(self.project_root, "assets", "sprites")
        self.sound_dir = os.path.join(self.project_root, "assets", "sounds")
        
        os.makedirs(self.sprite_dir, exist_ok=True)
        os.makedirs(self.sound_dir, exist_ok=True)

        # 3. 准备一个默认的空白模版
        default_code = 'print("Hello Bingo!")\n'
        with open(self.main_script_path, "w", encoding="utf-8") as f:
            f.write(default_code)
            
        return self.main_script_path, default_code

    def new_project(self):
        """初始化后台数据：生成新的临时目录和 main.py"""
        import tempfile
        # 1. 创建新的临时文件夹
        self.project_root = tempfile.mkdtemp(prefix="BingoProject_")
        
        # 2. 定义 main.py 路径
        self.main_script_path = os.path.join(self.project_root, "main.py")
        
        # 3. 写入初始模版代码
        initial_code = 'print("Hello Bingo!")'
        with open(self.main_script_path, "w", encoding="utf-8") as f:
            f.write(initial_code)
            
        print(f"📂 后台项目已重置: {self.project_root}")
    
    def open_project(self, folder_path):
        """
        验证并切换到指定的项目目录。
        不再强制要求 main.py，只要是文件夹即可打开。
        """
        if not os.path.isdir(folder_path):
            return False, "选择的路径不是有效的文件夹。"

        # 1. 切换身份：将当前指针指向这个目录
        self.project_root = folder_path
        
        # 2. 自动寻找一个“初始”入口文件
        py_files = [f for f in os.listdir(folder_path) if f.endswith('.py')]
        if py_files:
            # 优先找 main.py，找不到就拿第一个
            py_files.sort(key=lambda x: (x != "main.py", x.lower()))
            self.current_run_target = os.path.join(folder_path, py_files[0])
            self.main_script_path = self.current_run_target # 保持兼容性
        else:
            # 如果一个 py 都没有，就预设一个 main.py 路径，但先不创建
            self.main_script_path = os.path.join(folder_path, "main.py")
            self.current_run_target = ""

        # 3. 资源目录处理（保持原有逻辑）
        self.sprite_dir = os.path.join(folder_path, "assets", "sprites")
        self.sound_dir = os.path.join(folder_path, "assets", "sounds")
        os.makedirs(self.sprite_dir, exist_ok=True)
        os.makedirs(self.sound_dir, exist_ok=True)

        return True, "项目已加载"

    def save_project_to(self, target_path, latest_code):
        """
        target_path: 用户起名后的文件夹全路径 (例如: /Users/me/Desktop/MyNewGame)
        """
        try:
            # 1. 先确保临时文件的代码是最新的
            with open(self.main_script_path, "w", encoding="utf-8") as f:
                f.write(latest_code)

            # 2. 如果文件夹已存在（用户选了个旧的），我们合并进去；如果不存在，copytree 会创建它
            # dirs_exist_ok=True 是 Python 3.8+ 的参数
            import shutil
            shutil.copytree(self.project_root, target_path, dirs_exist_ok=True)
            
            # 3. 切换身份：当前项目路径正式迁移
            self.project_root = target_path
            self.main_script_path = os.path.join(target_path, "main.py")
            self.sprite_dir = os.path.join(target_path, "assets", "sprites")
            self.sound_dir = os.path.join(target_path, "assets", "sounds")
            
            return True
        except Exception as e:
            print(f"项目搬家失败: {e}")
            return False
    
    def quick_save(self, latest_code):
        """静默保存：只写文件，不搬家"""
        try:
            with open(self.main_script_path, "w", encoding="utf-8") as f:
                f.write(latest_code)
            return True
        except Exception as e:
            print(f"静默保存出错: {e}")
            return False