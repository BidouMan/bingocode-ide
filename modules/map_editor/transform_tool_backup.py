    def itemChange(self, change, value):
        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionChange
            and self.enabledSignals
        ):
            # 检查父项是否存在
            parent = self.parentItem()
            if not parent:
                return super().itemChange(change, value)

            new_pos = value
            rect = parent.rect()
            original_rect = QRectF(rect)

            # 获取父项的初始宽高比（用于等比缩放）
            initial_ratio = parent.initial_ratio

            # 检查是否按下了Shift键
            from PySide6.QtWidgets import QApplication
            is_shift_pressed = QApplication.keyboardModifiers() & Qt.ShiftModifier

            # 根据不同位置的手柄限制移动方向
            if self.pos_key == "tl":  # 左上角：可以调整宽高
                # 手动计算差值，避免使用 QPointF 减法运算符
                dx = new_pos.x() - rect.left()
                dy = new_pos.y() - rect.top()
                new_width = rect.width() - dx
                new_height = rect.height() - dy
                if new_width > 5 and new_height > 5:
                    if is_shift_pressed:
                        # 等比缩放：保持初始宽高比
                        new_height = new_width / initial_ratio
                    # 新的矩形大小
                    new_rect = QRectF(new_pos.x(), new_pos.y(), new_width, new_height)
                    rect = new_rect
                    # 调整父项位置，保持矩形的场景位置不变
                    old_pos = parent.pos()
                    parent.setPos(old_pos.x() + dx, old_pos.y() + dy)
            elif self.pos_key == "tr":  # 右上角：可以调整宽高
                # 手动计算差值，避免使用 QPointF 减法运算符
                new_width = new_pos.x() - rect.left()
                new_height = rect.bottom() - new_pos.y()
                if new_width > 5 and new_height > 5:
                    if is_shift_pressed:
                        # 等比缩放：保持初始宽高比
                        new_height = new_width / initial_ratio
                    # 新的矩形大小（保持左上角不变）
                    new_rect = QRectF(rect.left(), new_pos.y(), new_width, new_height)
                    rect = new_rect
                    # 调整父项Y位置
                    dy = new_pos.y() - rect.top()
                    old_pos = parent.pos()
                    parent.setPos(old_pos.x(), old_pos.y() + dy)
            elif self.pos_key == "bl":  # 左下角：可以调整宽高
                # 手动计算差值，避免使用 QPointF 减法运算符
                new_width = rect.right() - new_pos.x()
                new_height = new_pos.y() - rect.top()
                if new_width > 5 and new_height > 5:
                    if is_shift_pressed:
                        # 等比缩放：保持初始宽高比
                        new_width = new_height * initial_ratio
                    # 新的矩形大小（保持左上角不变）
                    new_rect = QRectF(new_pos.x(), rect.top(), new_width, new_height)
                    rect = new_rect
                    # 调整父项X位置
                    dx = new_pos.x() - rect.left()
                    old_pos = parent.pos()
                    parent.setPos(old_pos.x() + dx, old_pos.y())
            elif self.pos_key == "br":  # 右下角：可以调整宽高
                # 手动计算差值，避免使用 QPointF 减法运算符
                new_width = new_pos.x() - rect.left()
                new_height = new_pos.y() - rect.top()
                if new_width > 5 and new_height > 5:
                    if is_shift_pressed:
                        # 等比缩放：保持初始宽高比
                        new_height = new_width / initial_ratio
                    # 新的矩形大小（保持左上角不变）
                    new_rect = QRectF(rect.left(), rect.top(), new_width, new_height)
                    rect = new_rect

            # 如果矩形尺寸没有变化（达到最小限制），阻止手柄移动
            if rect == original_rect:
                # 返回手柄应该在的位置（选框角落）
                if self.pos_key == "tl":
                    return rect.topLeft()
                elif self.pos_key == "tr":
                    return rect.topRight()
                elif self.pos_key == "bl":
                    return rect.bottomLeft()
                elif self.pos_key == "br":
                    return rect.bottomRight()

            # 像素吸附：将矩形坐标对齐到整数像素
            aligned_rect = QRectF(
                round(rect.left()),
                round(rect.top()),
                round(rect.width()),
                round(rect.height())
            )
            parent.setRect(aligned_rect)
            parent.update_handles_pos()

            # 实时更新图像变换
            if hasattr(parent, 'update_transform'):
                parent.update_transform()

            # 返回手柄的新位置（应该是矩形的角落）
            if self.pos_key == "tl":
                return rect.topLeft()
            elif self.pos_key == "tr":
                return rect.topRight()
            elif self.pos_key == "bl":
                return rect.bottomLeft()
            elif self.pos_key == "br":
                return rect.bottomRight()

        return super().itemChange(change, value)