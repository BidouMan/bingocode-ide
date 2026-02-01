      # 🚀 强制关闭并清理共享内存
        if self.shm:
            try: 
                self.shm.close()
                # 尝试unlink，但注意：这会影响其他进程
                # self.shm.unlink()  # 谨慎使用！
            except: 
                pass
            self.shm = None
        
        # 🚀 关键：重置画布为纯背景，确保没有残留画面
        if hasattr(self, 'canvas') and not self.canvas.isNull():
            self.canvas.fill(self._bg_color)
        
        self.first_instruction = True
        
        # 🚀 新增：重置帧计数器
        self.frame_counter = 0
        
        self.update()  # 强制重绘