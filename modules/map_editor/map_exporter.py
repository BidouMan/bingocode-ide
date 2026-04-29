import os
import struct
import zipfile
import shutil
from PySide6.QtWidgets import QFileDialog, QMessageBox


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
                if member == "__bgm_magic__":
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
