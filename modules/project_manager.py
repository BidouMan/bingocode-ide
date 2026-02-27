import os
import tempfile
import shutil

class ProjectManager:
    def __init__(self):
        self.project_root = None
        self.sprite_dir = None
        self.sound_dir = None
        # 新增：记录代码文件的路径
        self.main_script_path = None 
        
        self.create_temp_project()

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
        验证并切换到指定的项目目录
        返回: (success, main_script_content)
        """
        main_py = os.path.join(folder_path, "main.py")
        
        # 1. 验证合法性
        if not os.path.exists(main_py):
            return False, "该文件夹不包含 main.py，不是有效的项目。"

        # 2. 身份切换：将当前指针指向这个旧家
        self.project_root = folder_path
        self.main_script_path = main_py
        self.sprite_dir = os.path.join(folder_path, "assets", "sprites")
        self.sound_dir = os.path.join(folder_path, "assets", "sounds")
        
        # 3. 自动补全可能缺失的素材目录（增强稳健性）
        os.makedirs(self.sprite_dir, exist_ok=True)
        os.makedirs(self.sound_dir, exist_ok=True)

        # 4. 读取代码内容返回给编辑器
        try:
            with open(main_py, "r", encoding="utf-8") as f:
                content = f.read()
            return True, content
        except Exception as e:
            return False, f"读取文件失败: {e}"

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