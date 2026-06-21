import os
import tempfile
import shutil
import zipfile
import json


class ProjectManager:
    DEFAULT_SCRIPT_NAME = "未命名-1.py"

    def __init__(self):
        self.project_root = ''
        self.sprite_dir = None
        self.sound_dir = None
        self.current_run_target = ""
        self.bingo_path = None
        self.last_save_dir = os.path.expanduser("~/Desktop")
        self.game_dir = None
        self.code_dir = None

        self._code_dirty = False
        self._resource_dirty = False
        self.create_temp_project()

    def mark_code_dirty(self, dirty=True):
        self._code_dirty = dirty

    def mark_resource_dirty(self, dirty=True):
        self._resource_dirty = dirty

    def reset_dirty(self):
        self._code_dirty = False
        self._resource_dirty = False

    def is_any_dirty(self):
        return self._code_dirty or self._resource_dirty

    def set_run_target(self, file_path):
        if file_path and os.path.exists(file_path):
            self.current_run_target = file_path

    def get_run_target(self):
        if self.current_run_target and os.path.exists(self.current_run_target):
            return self.current_run_target

        if self.project_root and os.path.exists(self.project_root):
            py_files = [f for f in os.listdir(self.project_root) if f.endswith('.py')]
            py_files.sort(key=lambda x: os.path.getmtime(os.path.join(self.project_root, x)), reverse=True)

            if py_files:
                target = os.path.join(self.project_root, py_files[0])
                self.current_run_target = target
                return target

        return None

    def _get_default_script_path(self):
        return os.path.join(self.project_root, self.DEFAULT_SCRIPT_NAME)

    def create_temp_project(self):
        self.project_root = tempfile.mkdtemp(prefix="BingoProject_")

        self.sprite_dir = os.path.join(self.project_root, "assets", "sprites")
        self.sound_dir = os.path.join(self.project_root, "assets", "sounds")
        self.game_dir = os.path.join(self.project_root, "game")
        self.code_dir = os.path.join(self.project_root, "code")
        os.makedirs(self.sprite_dir, exist_ok=True)
        os.makedirs(self.sound_dir, exist_ok=True)
        os.makedirs(self.game_dir, exist_ok=True)
        os.makedirs(self.code_dir, exist_ok=True)

        self.main_script_path = self._get_default_script_path()
        with open(self.main_script_path, "w", encoding="utf-8") as f:
            f.write("print('Hello Bingo!')")

        self._is_dirty = False

    def create_new_project_env(self):
        import datetime

        timestamp = datetime.datetime.now().strftime("%H%M%S")
        self.project_root = tempfile.mkdtemp(prefix=f"BingoProject_{timestamp}_")

        self.main_script_path = self._get_default_script_path()
        self.sprite_dir = os.path.join(self.project_root, "assets", "sprites")
        self.sound_dir = os.path.join(self.project_root, "assets", "sounds")
        self.game_dir = os.path.join(self.project_root, "game")
        self.code_dir = os.path.join(self.project_root, "code")

        os.makedirs(self.sprite_dir, exist_ok=True)
        os.makedirs(self.sound_dir, exist_ok=True)
        os.makedirs(self.game_dir, exist_ok=True)
        os.makedirs(self.code_dir, exist_ok=True)

        default_code = 'print("Hello Bingo!")\n'
        with open(self.main_script_path, "w", encoding="utf-8") as f:
            f.write(default_code)

        return self.main_script_path, default_code

    def new_project(self):
        import tempfile

        self.project_root = tempfile.mkdtemp(prefix="BingoProject_")

        self.main_script_path = self._get_default_script_path()
        self.game_dir = os.path.join(self.project_root, "game")
        self.code_dir = os.path.join(self.project_root, "code")
        os.makedirs(self.game_dir, exist_ok=True)
        os.makedirs(self.code_dir, exist_ok=True)

        initial_code = 'print("Hello Bingo!")'
        with open(self.main_script_path, "w", encoding="utf-8") as f:
            f.write(initial_code)

    def open_project(self, folder_path):
        if not os.path.isdir(folder_path):
            return False, "选择的路径不是有效的文件夹。"

        self.project_root = folder_path

        py_files = [f for f in os.listdir(folder_path) if f.endswith('.py')]
        if py_files:
            py_files.sort(key=lambda x: os.path.getmtime(os.path.join(folder_path, x)), reverse=True)
            self.current_run_target = os.path.join(folder_path, py_files[0])
            self.main_script_path = self.current_run_target
        else:
            self.main_script_path = self._get_default_script_path()
            self.current_run_target = ""

        self.sprite_dir = os.path.join(folder_path, "assets", "sprites")
        self.sound_dir = os.path.join(folder_path, "assets", "sounds")
        self.game_dir = os.path.join(folder_path, "game")
        self.code_dir = os.path.join(folder_path, "code")
        os.makedirs(self.sprite_dir, exist_ok=True)
        os.makedirs(self.sound_dir, exist_ok=True)
        os.makedirs(self.game_dir, exist_ok=True)
        os.makedirs(self.code_dir, exist_ok=True)

        return True, "项目已加载"

    def save_project_to(self, target_path, latest_code):
        try:
            with open(self.main_script_path, "w", encoding="utf-8") as f:
                f.write(latest_code)

            import shutil
            shutil.copytree(self.project_root, target_path, dirs_exist_ok=True)

            self.project_root = target_path
            self.main_script_path = os.path.join(target_path, os.path.basename(self.main_script_path))
            self.sprite_dir = os.path.join(target_path, "assets", "sprites")
            self.sound_dir = os.path.join(target_path, "assets", "sounds")

            return True
        except Exception as e:
            print(f"项目搬家失败: {e}")
            return False

    def quick_save(self, latest_code):
        try:
            with open(self.main_script_path, "w", encoding="utf-8") as f:
                f.write(latest_code)
            return True
        except Exception as e:
            print(f"静默保存出错: {e}")
            return False

    def pack_to_bingo(self, bingo_path):
        """将整个项目打包为 .bingo 文件（ZIP格式）"""
        try:
            with zipfile.ZipFile(bingo_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(self.project_root):
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
                    for f in files:
                        if f.startswith('.'):
                            continue
                        full_path = os.path.join(root, f)
                        arc_name = os.path.relpath(full_path, self.project_root)
                        zf.write(full_path, arc_name)
            return True
        except Exception as e:
            print(f"打包失败: {e}")
            return False

    def unpack_from_bingo(self, bingo_path):
        """解压 .bingo 文件到临时目录并加载"""
        try:
            new_root = tempfile.mkdtemp(prefix="BingoProject_")
            with zipfile.ZipFile(bingo_path, 'r') as zf:
                zf.extractall(new_root)
            return self.open_project(new_root)
        except Exception as e:
            print(f"解压失败: {e}")
            return False, str(e)
