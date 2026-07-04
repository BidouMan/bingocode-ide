# 接通地图资源管道 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `load_map('草地')` 能正常工作，完成从内置地图库 → 项目目录 → Python引擎的完整管道

**Architecture:** 创建一个简单的草地测试 .bgm 地图包，修复引擎中的路径错误，修复前端 mapLib.ts 中的路径和内置地图注册

**Tech Stack:** Python (bingo_engine.py), TypeScript (mapLib.ts), Rust (lib.rs), JSZip

## Global Constraints

- 注释和部分变量名使用中文，不要修改
- 遵循原始 PySide6 UI 的颜色和布局规范
- 资源目录：`engine/assets/` 是所有游戏资源的唯一真实来源
- 地图 .bgm 格式：ZIP 包含 `map.json` + `thumbnail.png`
- 项目目录：`~/BingoCodeIDE/Projects/default/`（每次启动清理旧资源）

---

## 问题分析

### 断裂点 1: `_try_extract_bgm` 路径错误
- 文件: `engine/bingo_engine.py:1906`
- 当前: `bgm_path = os.path.join(engine_dir, "assets", f"{map_name}.bgm")` → `engine/assets/草地.bgm`
- 应该: `engine/assets/maps/packages/草地.bgm`

### 断裂点 2: `mapLib.ts` 内置地图为空
- 文件: `src/stores/mapLib.ts:17`
- 当前: `BUILTIN_MAPS: string[] = []`
- 需要: 添加内置地图名称列表

### 断裂点 3: `mapLib.ts` 路径加载方式不一致
- 文件: `src/stores/mapLib.ts:24`
- 当前: `bgmUrl = /map_lib/${name}.bgm`（Vite publicDir 路径，但实际不在 `/map_lib/` 下）
- 应该: 使用 `invoke('get_engine_assets_dir')` 获取引擎目录，构造完整路径（与 spriteLib 一致）

### 断裂点 4: 无 .bgm 测试地图
- `engine/assets/maps/packages/` 目录为空
- 需要创建一个简单的草地测试地图

---

### Task 1: 创建草地测试地图 .bgm 文件

**Covers:** 创建内置地图资源

**Files:**
- Create: `engine/assets/maps/packages/草地.bgm`（通过 Python 脚本生成）
- Create: `scripts/create_test_map.py`（一次性生成脚本，完成后可删除）

**Interfaces:**
- Produces: `engine/assets/maps/packages/草地.bgm` — ZIP 包含 `map.json` + `thumbnail.png`

- [ ] **Step 1: 编写地图生成脚本**

```python
#!/usr/bin/env python3
"""生成测试草地地图 .bgm 文件"""
import json
import zipfile
import os

# 40x30 瓦片地图，16px 瓦片，使用 grass 瓦片铺满
WIDTH, HEIGHT = 40, 30
TILE_SIZE = 16

# tileset 引用 engine/assets/maps/tilesets/tileset.png
# firstgid=1，瓦片 ID 1 = grass
# 生成全草地瓦片数据（base64+zlib 压缩，与引擎解压格式一致）
import base64
import zlib
import struct

tile_ids = []
for y in range(HEIGHT):
    for x in range(WIDTH):
        # 边缘放砖块 (ID=2)，中间放草地 (ID=1)
        if x == 0 or x == WIDTH - 1 or y == 0 or y == HEIGHT - 1:
            tile_ids.append(2)  # brick
        else:
            tile_ids.append(1)  # grass

# 压缩为 base64+zlib（与 mapSerializer.ts 格式一致）
raw_data = struct.pack(f'<{len(tile_ids)}I', *tile_ids)
compressed = zlib.compress(raw_data)
b64_data = base64.b64encode(compressed).decode('ascii')

map_data = {
    "name": "草地",
    "width": WIDTH,
    "height": HEIGHT,
    "tileSize": TILE_SIZE,
    "offsetX": 0,
    "offsetY": 0,
    "gravity": False,
    "layers": [
        {
            "name": "背景层",
            "type": "tilelayer",
            "visible": True,
            "locked": False,
            "data": b64_data,
            "images": []
        }
    ],
    "tilesets": [
        {
            "name": "tileset",
            "image": "../tilesets/tileset.png",
            "firstgid": 1,
            "tileWidth": TILE_SIZE,
            "tileHeight": TILE_SIZE,
            "collisionType": "none",
            "collisionEnabled": False,
            "tiles": [
                {"id": 1, "collision": "none"},
                {"id": 2, "collision": "solid"}
            ]
        }
    ]
}

# 写入 .bgm (ZIP)
output_path = os.path.join(os.path.dirname(__file__), '..', 'engine', 'assets', 'maps', 'packages', '草地.bgm')
os.makedirs(os.path.dirname(output_path), exist_ok=True)

with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('map.json', json.dumps(map_data, ensure_ascii=False, indent=2))

print(f"✅ 已创建: {output_path}")
print(f"   地图: {WIDTH}x{HEIGHT} 瓦片, {TILE_SIZE}px/瓦片")
```

- [ ] **Step 2: 运行脚本生成 .bgm 文件**

Run: `python3 scripts/create_test_map.py`
Expected: 输出 `✅ 已创建: ...engine/assets/maps/packages/草地.bgm`

- [ ] **Step 3: 验证 .bgm 文件可被 Python 引擎解压**

```python
import zipfile
with zipfile.ZipFile('engine/assets/maps/packages/草地.bgm', 'r') as zf:
    print(zf.namelist())  # 应该包含 'map.json'
    data = json.loads(zf.read('map.json'))
    print(f"地图: {data['name']}, {data['width']}x{data['height']}")
```

Expected: 输出 `['map.json']` 和 `地图: 草地, 40x30`

- [ ] **Step 4: 删除临时脚本并提交**

```bash
rm scripts/create_test_map.py
git add engine/assets/maps/packages/草地.bgm
git commit -m "feat: 添加草地测试地图 .bgm 资源"
```

---

### Task 2: 修复 `_try_extract_bgm` 路径

**Covers:** 引擎地图加载路径修复

**Files:**
- Modify: `engine/bingo_engine.py:1906`

**Interfaces:**
- Consumes: `engine/assets/maps/packages/{name}.bgm`
- Produces: 正确的 .bgm 文件查找路径

- [ ] **Step 1: 修复路径**

将 `engine/bingo_engine.py:1906` 从:
```python
bgm_path = os.path.join(engine_dir, "assets", f"{map_name}.bgm")
```
改为:
```python
bgm_path = os.path.join(engine_dir, "assets", "maps", "packages", f"{map_name}.bgm")
```

- [ ] **Step 2: 验证修改**

读取修改后的代码，确认路径正确。

- [ ] **Step 3: 提交**

```bash
git add engine/bingo_engine.py
git commit -m "fix: 修复 _try_extract_bgm 的 .bgm 文件查找路径"
```

---

### Task 3: 修复 mapLib.ts 内置地图注册和路径

**Covers:** 前端地图库加载修复

**Files:**
- Modify: `src/stores/mapLib.ts:17-52`

**Interfaces:**
- Consumes: `invoke('get_engine_assets_dir')` 返回引擎资源目录路径
- Produces: 正确的 .bgm 文件 URL 列表

- [ ] **Step 1: 修改 BUILTIN_MAPS 和 loadBuiltinLibrary**

将 `src/stores/mapLib.ts` 修改为:

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import JSZip from 'jszip'

export interface MapLibItem {
  name: string
  bgmUrl: string
  thumbUrl: string
  loaded: boolean
}

export const useMapLibStore = defineStore('mapLib', () => {
  const items = ref<MapLibItem[]>([])
  const loading = ref(false)

  // 内置地图列表
  const BUILTIN_MAPS = ['草地']

  async function loadBuiltinLibrary() {
    if (items.value.length > 0) return
    loading.value = true

    // 获取引擎资源目录
    const engineDir = await invoke<string>('get_engine_assets_dir')

    // 创建所有条目
    for (const name of BUILTIN_MAPS) {
      items.value.push({
        name,
        bgmUrl: `${engineDir}/maps/packages/${name}.bgm`,
        thumbUrl: '',
        loaded: false,
      })
    }

    // 通过 Tauri 命令加载缩略图（从 .bgm zip 读取）
    for (const item of items.value) {
      try {
        const dataUrl = await invoke<string>('get_sprite_thumbnail', {
          path: item.bgmUrl,
        })
        item.thumbUrl = dataUrl
        item.loaded = true
      } catch (e) {
        console.error(`[MapLib] ${item.name}: 加载缩略图失败`, e)
      }
    }

    loading.value = false
  }

  return { items, loading, loadBuiltinLibrary }
})
```

- [ ] **Step 2: 验证 TypeScript 编译**

Run: `npx vue-tsc --noEmit` 或 IDE 无类型错误
Expected: 无错误

- [ ] **Step 3: 提交**

```bash
git add src/stores/mapLib.ts
git commit -m "feat: 注册草地内置地图并修复 .bgm 路径加载"
```

---

### Task 4: 验证完整管道

**Covers:** 端到端验证

**Files:** 无修改，仅验证

- [ ] **Step 1: 启动开发服务器**

Run: `pnpm dev`
Expected: Vite 服务正常启动

- [ ] **Step 2: 在浏览器中验证地图库页面**

打开应用 → 资源面板 → 地图 → 点击上传按钮 → 选择"库"
Expected: 看到"草地"地图卡片，有缩略图

- [ ] **Step 3: 验证地图导入**

点击"草地"卡片
Expected: 地图被导入到项目目录，资源面板中出现"草地"

- [ ] **Step 4: 验证 Python 引擎加载**

在代码编辑器中运行测试代码:
```python
hero = Sprite('弓箭手')
load_map('草地')
def loop():
    if key_down('right'):
        hero.move(5)
run()
```

Expected: 控制台输出 `✅ [BingoEngine] 加载地图: 草地` 和 `✅ [BingoEngine] 地图加载成功: 草地`，游戏窗口显示草地地图

- [ ] **Step 5: 最终提交**

```bash
git add -A
git commit -m "feat: 接通地图资源管道，支持内置地图加载"
```
