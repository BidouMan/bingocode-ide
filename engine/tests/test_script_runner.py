# engine/tests/test_script_runner.py
import sys
import os
import tempfile
import shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from script_runner import discover_and_merge

def test_single_file():
    """测试单文件场景"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建主文件
        main_file = os.path.join(tmpdir, "main.py")
        with open(main_file, "w") as f:
            f.write("""
while True:
    x = 1
""")
        result = discover_and_merge(tmpdir)
        assert "while True:" in result
        assert "yield" in result

def test_multi_file():
    """测试多文件场景"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建主文件
        main_file = os.path.join(tmpdir, "main.py")
        with open(main_file, "w") as f:
            f.write("""
from player import create_hero

while True:
    hero = create_hero()
""")
        # 创建辅助文件
        player_file = os.path.join(tmpdir, "player.py")
        with open(player_file, "w") as f:
            f.write("""
def create_hero():
    return Sprite("洛克人")
""")
        result = discover_and_merge(tmpdir)
        assert "from player import create_hero" in result
        assert "while True:" in result

if __name__ == "__main__":
    test_single_file()
    test_multi_file()
    print("All tests passed!")
