import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 模拟引擎全局状态
_STOPPED = False

class MockGenerator:
    """模拟 generator 的测试类"""
    def __init__(self, name):
        self.name = name
        self.frames = 0

    def __next__(self):
        self.frames += 1
        if self.frames > 5:
            raise StopIteration
        return f"{self.name} frame {self.frames}"

def test_generator_scheduler():
    """测试 generator 调度器"""
    gen1 = MockGenerator("player")
    gen2 = MockGenerator("enemy")

    generators = [gen1, gen2]

    frame = 0
    while frame < 3:
        # 每帧执行所有 generator
        for gen in generators:
            try:
                next(gen)
            except StopIteration:
                generators.remove(gen)
        frame += 1

    assert gen1.frames == 3
    assert gen2.frames == 3
    print("Generator scheduler test passed!")

if __name__ == "__main__":
    test_generator_scheduler()
