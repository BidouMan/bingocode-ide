"""Sprite 动画与说话气泡（Mixin）：play()、say()、逐帧动画推进。

什么时候来这里改：动画换帧、动画不播/卡住、说话气泡显示时长。
帧数据来源见 sprite_assets.py（bsf manifest / 旧 bgs 配置）。"""
import os
import time
from timing import Timer
import engine_state as st


class SpriteAnimationMixin:
    """Sprite 动画与说话气泡（由 sprite.Sprite 继承）。"""

    def say(self, text, seconds=0):
        """
        让角色说话。新话会替换旧话。
        say("你好")      → 永久显示
        say("得分+1", 2) → 2秒后自动消失
        """
        self._send_command("SAY", {"text": str(text)})
        # 新气泡先取消旧的隐藏计时器，防止旧计时器提前隐藏新话
        st._SAY_TIMERS.pop(self.id, None)
        if seconds > 0:
            def _hide():
                self._send_command("SAY", {"text": ""})
            timer = Timer(seconds, loop=False)
            st._SAY_TIMERS[self.id] = (timer, _hide)


    def play(self, animation_name, transition_time=0.1):
        """
        播放指定名称的动画
        参数: animation_name - 动画名称（如 'idle', 'walk' 等）
              transition_time - 平滑过渡时间（秒），默认0.1秒
        """
        if not self.config:
            return

        # 如果当前已经在播放这个动画，就不需要重复设置
        if (
            hasattr(self, "_current_animation")
            and self._current_animation == animation_name
        ):
            return

        # 获取动画配置
        animation_config = None
        # .bsf：优先按 clip 原始帧序列播放（支持非连续帧 / 重复帧）
        if getattr(self, "_is_bsf", False) and animation_name in getattr(self, "_bsf_clips", {}):
            clip = self._bsf_clips[animation_name]
            name_to_idx = {f.get("name"): i for i, f in enumerate(self._bsf_frames)}
            idxs = [name_to_idx[n] for n in clip.get("frames", []) if n in name_to_idx]
            if idxs:
                animation_config = {
                    "start": 1,
                    "end": len(idxs),
                    "fps": clip.get("fps", 10),
                    "loop": clip.get("loop", True),
                    "frame_indices": idxs,
                }
        if not animation_config and "segments" in self.config:
            for segment in self.config["segments"]:
                if segment.get("name") == animation_name:
                    animation_config = segment
                    break
        if not animation_config and "animations" in self.config:
            animation_config = self.config["animations"].get(animation_name)

        if not animation_config:
            # 排查友好：名字打错/片段缺失时不再静默失败，列出可用动画名
            if getattr(self, "_is_bsf", False):
                available = [c.get("name") for c in getattr(self, "_bsf_clips", {}).values()]
            else:
                available = [s.get("name") for s in (self.config.get("segments") or [])]
            print(f"[警告] 角色 '{self.config.get('name', '未知')}' 没有动画 '{animation_name}'，可用动画: {available}")
            return

        # 获取动画参数
        start = animation_config.get("start", 1)
        end = animation_config.get("end", 1)
        fps = animation_config.get("fps", 10)
        loop = animation_config.get("loop", True)
        frame_indices = animation_config.get("frame_indices")

        # 如果当前没有动画在播放，直接设置新动画
        if not hasattr(self, "animation_state") or not self.animation_state:
            self.animation_state = {
                "start": start - 1,
                "end": end - 1,
                "fps": fps,
                "loop": loop,
                "frame_indices": frame_indices,
                "current_frame": start - 1,
                "last_frame_time": time.time(),
                "frame_duration": 1.0 / fps,
                "is_playing": True,
            }
            self._current_animation = animation_name
            self._update_animation_frame()
            return

        # 直接切换动画状态，不使用复杂的过渡逻辑
        # 这样动画切换会更加流畅，没有延迟
        self.animation_state = {
            "start": start - 1,
            "end": end - 1,
            "fps": fps,
            "loop": loop,
            "frame_indices": frame_indices,
            "current_frame": start - 1,
            "last_frame_time": time.time(),
            "frame_duration": 1.0 / fps,
            "is_playing": True,
        }
        self._update_animation_frame()

        # 记录当前播放的动画名称
        self._current_animation = animation_name


    def _update_animation_frame(self):
        """更新动画帧"""
        if not hasattr(self, "animation_state") or not self.animation_state:
            return

        # 检查是否在过渡状态
        if hasattr(self, "_is_transitioning") and self._is_transitioning:
            # 计算过渡进度
            now = time.time()
            elapsed = now - self._transition_start_time
            progress = min(elapsed / self._transition_duration, 1.0)

            if progress < 0.5:
                # 前半段显示源动画的帧
                current_frame = self._source_animation["current_frame"]
            else:
                # 后半段显示目标动画的帧
                current_frame = self._target_animation["current_frame"]

            # 如果过渡完成，结束过渡状态
            if progress >= 1.0:
                self.animation_state = self._target_animation
                del self._source_animation
                del self._target_animation
                del self._transition_duration
                del self._is_transitioning
        else:
            # 正常动画播放
            current_frame = self.animation_state["current_frame"]

        # .bsf：clip 内序号映射到 sheet 帧索引，只切 UV 区域不换文件
        if getattr(self, "_is_bsf", False) and self._bsf_frames:
            indices = self.animation_state.get("frame_indices")
            if indices and 0 <= current_frame < len(indices):
                frame_idx = indices[current_frame]
            else:
                frame_idx = max(0, min(current_frame, len(self._bsf_frames) - 1))
            if frame_idx != getattr(self, "_bsf_frame_index", 0):
                self._bsf_frame_index = frame_idx
                self._setup_hitbox()  # 重新计算当前帧的 vox/voy（O(1)，来自 manifest）
                self._update_transform()
            return

        # 获取帧文件路径
        if self.config and "frames" in self.config:
            if current_frame < len(self.config["frames"]):
                frame_file = self.config["frames"][current_frame]
                self.image = os.path.join(self.sprite_dir, frame_file)

                # 更新变换和图像
                self._update_transform()
