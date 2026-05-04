import os
import struct
import zipfile
import shutil
from PySide6.QtWidgets import QFileDialog, QMessageBox
from PySide6.QtGui import QPixmap, QPainter, QColor, QBrush, QPen
from PySide6.QtCore import QRectF, Qt
from PySide6.QtWidgets import QGraphicsScene, QGraphicsRectItem


class MapExporter:
    BGM_MAGIC = "BGM1"
    BGM_EXTENSION = ".bgm"

    def __init__(self, map_editor_manager):
        self.manager = map_editor_manager

    def export_map(self):
        if not self.manager.current_map_path:
            QMessageBox.warning(None, "导出失败", "当前没有打开的地图，无法导出。")
            return

        if not os.path.exists(self.manager.current_map_path):
            QMessageBox.warning(None, "导出失败", "当前地图文件不存在，请先保存地图。")
            return

        map_dir = os.path.dirname(self.manager.current_map_path)
        original_name = os.path.basename(map_dir)

        default_filename = f"{original_name}{self.BGM_EXTENSION}"
        save_path, _ = QFileDialog.getSaveFileName(
            None, "导出地图", default_filename, f"BGM 地图文件 (*{self.BGM_EXTENSION})"
        )
        if not save_path:
            return

        if not save_path.endswith(self.BGM_EXTENSION):
            save_path += self.BGM_EXTENSION

        export_name = os.path.splitext(os.path.basename(save_path))[0]

        try:
            self._create_bgm(map_dir, save_path, original_name, export_name)
            # QMessageBox.information(None, "导出成功", f"地图已成功导出至:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(None, "导出失败", f"导出地图时发生错误:\n{str(e)}")

    def import_map(self):
        if (
            not self.manager.project_manager
            or not self.manager.project_manager.project_root
        ):
            QMessageBox.warning(None, "导入失败", "当前没有打开的项目，无法导入地图。")
            return

        open_path, _ = QFileDialog.getOpenFileName(
            None, "导入地图", "", f"BGM 地图文件 (*{self.BGM_EXTENSION})"
        )
        if not open_path:
            return

        try:
            maps_dir = os.path.join(
                self.manager.project_manager.project_root, "assets", "maps"
            )
            os.makedirs(maps_dir, exist_ok=True)

            map_name = self._read_map_name_from_bgm(open_path)
            if not map_name:
                map_name = os.path.splitext(os.path.basename(open_path))[0]

            target_dir = os.path.join(maps_dir, map_name)
            if os.path.exists(target_dir):
                info_path = os.path.join(target_dir, f"{map_name}.info")
                if os.path.exists(info_path):
                    reply = QMessageBox.question(
                        None,
                        "地图已存在",
                        f'地图 "{map_name}" 已存在，是否覆盖？',
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if reply == QMessageBox.StandardButton.No:
                        return
                    shutil.rmtree(target_dir)

            os.makedirs(target_dir, exist_ok=True)
            self._extract_bgm(open_path, target_dir)

            info_path = os.path.join(target_dir, f"{map_name}.info")
            if not os.path.exists(info_path):
                for f in os.listdir(target_dir):
                    if f.endswith(".info"):
                        info_path = os.path.join(target_dir, f)
                        break

            if os.path.exists(info_path):
                self.manager.load_map_from_path(info_path)
                self.manager.map_imported.emit()

        except Exception as e:
            QMessageBox.critical(None, "导入失败", f"导入地图时发生错误:\n{str(e)}")

    def _create_bgm(self, map_dir, save_path, original_name, export_name):
        rename_needed = original_name != export_name

        with zipfile.ZipFile(save_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("__bgm_magic__", self.BGM_MAGIC)

            for root, dirs, files in os.walk(map_dir):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    arcname = os.path.relpath(file_path, map_dir)

                    if rename_needed:
                        arcname, data = self._remap_entry(
                            file_path, arcname, original_name, export_name
                        )
                    else:
                        data = None

                    if data is not None:
                        zf.writestr(arcname, data)
                    else:
                        zf.write(file_path, arcname)

            thumbnail_png = self._generate_thumbnail_png(map_dir)
            if thumbnail_png:
                zf.writestr("thumbnail.png", thumbnail_png)

    def _remap_entry(self, file_path, arcname, old_name, new_name):
        base, ext = os.path.splitext(arcname)
        parent = os.path.dirname(arcname)

        if (
            parent == ""
            and base == old_name
            and ext in (".info", ".tiles", ".collision", ".resources")
        ):
            new_arcname = f"{new_name}{ext}"
            if ext == ".info":
                try:
                    with open(file_path, "rb") as f:
                        data = f.read()
                    data = self._patch_info_name(data, new_name)
                    return new_arcname, data
                except Exception:
                    return arcname, None
            return new_arcname, None

        return arcname, None

    def _patch_info_name(self, info_data, new_name):
        if len(info_data) < 12:
            return info_data

        magic = struct.unpack_from("<I", info_data, 0)[0]
        if magic != 0x4D415050:
            return info_data

        version = struct.unpack_from("<I", info_data, 4)[0]
        if version < 3:
            return info_data

        old_name_length = struct.unpack_from("<I", info_data, 8)[0]
        header_end = 12 + old_name_length

        if header_end > len(info_data):
            return info_data

        rest = info_data[header_end:]
        new_name_bytes = new_name.encode("utf-8")
        new_header = (
            info_data[:8] + struct.pack("<I", len(new_name_bytes)) + new_name_bytes
        )

        return new_header + rest

    def _extract_bgm(self, bgm_path, target_dir):
        with zipfile.ZipFile(bgm_path, "r") as zf:
            for member in zf.namelist():
                if member == "__bgm_magic__" or member == "thumbnail.png":
                    continue
                member_path = os.path.normpath(os.path.join(target_dir, member))
                if not member_path.startswith(os.path.normpath(target_dir)):
                    continue
                zf.extract(member, target_dir)

    def _read_map_name_from_bgm(self, bgm_path):
        try:
            with zipfile.ZipFile(bgm_path, "r") as zf:
                for member in zf.namelist():
                    if member.endswith(".info"):
                        return os.path.splitext(os.path.basename(member))[0]
        except Exception:
            pass
        return None

    def _generate_thumbnail_png(self, map_dir, thumb_size=320):
        try:
            from models.map_model import MapDataModel

            info_file = None
            for f in os.listdir(map_dir):
                if f.endswith(".info"):
                    info_file = os.path.join(map_dir, f)
                    break
            if not info_file:
                return None

            model = MapDataModel()
            if not model.load(info_file):
                return None

            map_data = model.map_data
            width = map_data.get("width", 40)
            height = map_data.get("height", 30)
            tile_size = map_data.get("tile_size", 16)
            pixel_w = width * tile_size
            pixel_h = height * tile_size

            view_w = 640
            view_h = 480
            scene_w = max(pixel_w, view_w)
            scene_h = max(pixel_h, view_h)

            scene = QGraphicsScene(0, 0, scene_w, scene_h)

            bg_rect = QGraphicsRectItem(0, 0, scene_w, scene_h)
            bg_rect.setPen(Qt.PenStyle.NoPen)
            bg_rect.setBrush(QBrush(QColor(30, 30, 30)))
            scene.addItem(bg_rect)

            border = QGraphicsRectItem(0, 0, pixel_w, pixel_h)
            border.setPen(QPen(QColor(100, 100, 100), 1))
            border.setBrush(Qt.BrushStyle.NoBrush)
            scene.addItem(border)

            tile_sets = map_data.get("tile_sets", [])
            layer_resources_map = map_data.get("layer_resources_map", {})
            layers = map_data.get("layers", [])

            for layer in layers:
                layer_id = str(layer.get("id", 0))
                layer_type = layer.get("type", "drawing")

                if layer_type == "drawing":
                    tiles = layer.get("tiles", {})
                    if not tiles or not tile_sets:
                        continue

                    res_range = layer_resources_map.get(layer_id)
                    if not res_range:
                        continue
                    start_idx, end_idx = res_range
                    if start_idx >= len(tile_sets):
                        continue

                    layer_tileset_cache = {}
                    for i in range(start_idx, min(end_idx, len(tile_sets))):
                        res = tile_sets[i]
                        img_path = res.get("image_path", "")
                        if not img_path or not os.path.exists(img_path):
                            continue
                        src_pix = QPixmap(img_path)
                        if src_pix.isNull():
                            continue
                        tw = res.get("tile_width", 16)
                        th = res.get("tile_height", 16)
                        tcw = max(1, res.get("tile_count_w", src_pix.width() // tw))
                        layer_tileset_cache[i] = (src_pix, tw, th, tcw)

                    for (tx, ty), tid in tiles.items():
                        if tid <= 0:
                            continue
                        if tx < 0 or tx >= width or ty < 0 or ty >= height:
                            continue

                        res_idx = tid // 1000 - 1
                        tile_idx = (tid % 1000) - 1

                        if res_idx not in layer_tileset_cache:
                            continue
                        src_pix, tw, th, tcw = layer_tileset_cache[res_idx]

                        stx = (tile_idx % tcw) * tw
                        sty = (tile_idx // tcw) * th
                        if stx + tw > src_pix.width() or sty + th > src_pix.height():
                            continue
                        tile_pix = src_pix.copy(stx, sty, tw, th)
                        if not tile_pix.isNull():
                            pm_item = scene.addPixmap(tile_pix)
                            pm_item.setPos(tx * tile_size, ty * tile_size)

                elif layer_type == "image":
                    images = layer.get("images", [])
                    for img_data in images:
                        img_path = img_data.get("image_path", "")
                        if not img_path or not os.path.exists(img_path):
                            continue
                        pix = QPixmap(img_path)
                        if pix.isNull():
                            continue
                        pos = img_data.get("position", [0, 0])
                        sx = img_data.get("scale_x", img_data.get("scale", 1.0))
                        sy = img_data.get("scale_y", img_data.get("scale", 1.0))
                        if sx != 1.0 or sy != 1.0:
                            new_w = max(1, int(pix.width() * sx))
                            new_h = max(1, int(pix.height() * sy))
                            pix = pix.scaled(new_w, new_h, Qt.AspectRatioMode.IgnoreAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation)
                        pm_item = scene.addPixmap(pix)
                        pm_item.setPos(pos[0], pos[1])

            scale = min(thumb_size / view_w, thumb_size / view_h) if view_w > 0 and view_h > 0 else 1
            render_w = max(1, int(view_w * scale))
            render_h = max(1, int(view_h * scale))

            thumbnail = QPixmap(render_w, render_h)
            thumbnail.fill(QColor(30, 30, 30))
            painter = QPainter(thumbnail)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            scene.render(painter, QRectF(0, 0, render_w, render_h), QRectF(0, 0, view_w, view_h))
            painter.end()

            from PySide6.QtCore import QBuffer, QIODevice
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            thumbnail.save(buffer, "PNG")
            png_data = buffer.data().data()
            buffer.close()
            return png_data
        except Exception:
            return None
