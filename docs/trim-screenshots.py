"""裁掉截图四周的全透明边距。

macOS 用「窗口截图」（⌘⇧4 后按空格）保存的 PNG 自带透明外框/阴影留白，
直接放进文档会多出一圈空白。这里用 alpha 通道的 bbox 把真正的画面裁出来，
输出到 dist，不修改 static 里的原图。

用法：python trim-screenshots.py <源目录> <输出目录>
只有装了 Pillow 才能运行；build.ts 会优先使用 engine/venv。
无需裁切或不是 PNG 的文件原样复制。
"""

import json
import os
import shutil
import sys

MANIFEST_NAME = ".trim-manifest.json"


def trim_one(src_path: str, dest_path: str) -> None:
    """裁切单个 PNG；无需裁切时原样复制。"""
    from PIL import Image

    im = Image.open(src_path)
    if im.mode in ("RGBA", "LA", "P"):
        rgba = im.convert("RGBA")
        bbox = rgba.getchannel("A").getbbox()  # 全透明时返回 None
        if bbox and bbox != (0, 0, rgba.width, rgba.height):
            cropped = rgba.crop(bbox)
            cropped.save(dest_path, optimize=True)
            print(f"  ✂️  {os.path.basename(src_path)}: "
                  f"{rgba.width}×{rgba.height} → {cropped.width}×{cropped.height}")
            return
    shutil.copyfile(src_path, dest_path)


def load_manifest(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def main() -> None:
    if len(sys.argv) < 3:
        print("用法: python trim-screenshots.py <源目录> <输出目录>")
        sys.exit(2)

    src_root, dest_root = sys.argv[1], sys.argv[2]
    manifest_path = os.path.join(dest_root, MANIFEST_NAME)
    manifest = load_manifest(manifest_path)
    changed = False
    valid = set()

    for dirpath, _dirnames, filenames in os.walk(src_root):
        rel = os.path.relpath(dirpath, src_root)
        dest_dir = dest_root if rel == "." else os.path.join(dest_root, rel)
        os.makedirs(dest_dir, exist_ok=True)

        for name in sorted(filenames):
            if name.startswith("."):
                continue
            valid.add(os.path.relpath(os.path.join(dirpath, name), src_root))
            src_path = os.path.join(dirpath, name)
            dest_path = os.path.join(dest_dir, name)
            key = os.path.relpath(src_path, src_root)
            mtime = round(os.path.getmtime(src_path), 3)

            # 增量：源文件没改过且输出还在，就跳过（开发时只处理变化的那张）
            if manifest.get(key) == mtime and os.path.exists(dest_path):
                continue

            if name.lower().endswith(".png"):
                try:
                    trim_one(src_path, dest_path)
                except Exception as exc:  # 打开/保存失败时不能中断构建
                    print(f"  ⚠️  {name} 裁切失败，按原图复制: {exc}")
                    shutil.copyfile(src_path, dest_path)
            else:
                shutil.copyfile(src_path, dest_path)

            manifest[key] = mtime
            changed = True

    # 清掉源目录里已删除、但残留在 dist 的旧图（构建不会自动清理输出目录）
    for dirpath, _dirnames, filenames in os.walk(dest_root):
        for name in filenames:
            if name.startswith("."):
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), dest_root)
            if rel not in valid:
                os.remove(os.path.join(dirpath, name))
                manifest.pop(rel, None)
                print(f"  🗑️  清理旧图: {rel}")
                changed = True

    if changed or not os.path.exists(manifest_path):
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main()
