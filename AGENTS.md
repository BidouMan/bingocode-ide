# AGENTS.md

## What is this

BingoCodeIDE — Tauri v2 + Vue 3 + PixiJS desktop IDE for game development with a Python engine (`bingo_engine.py`). Refactored from a PySide6 version. Has two modes:
- **Game mode**: Visual editors (sprite, map, collision) + code editor + live preview + resource panel with drawer menus
- **IDE mode**: Standard Python code editing with run/stop/undo/redo

## Run

```bash
pnpm dev          # Frontend dev server (Vite)
pnpm tauri dev    # Desktop app (Tauri)
```

## UI 规格参考（原 PySide6 版已归档删除）

原 PySide6 版完整源码（`legacy/`）已于 2026-10-20 从仓库移除，仅保留一份本机归档：`~/BingoCodeIDE-legacy-pyside6-archive-20261020.tar.gz`（含 ui/*.py、qss、图标、字体等，已排除 .venv）。需要查阅原始布局/交互细节时从归档解压临时目录阅读，不要恢复回仓库。

- UI 颜色/尺寸规格以本文末尾「Original QSS color reference」为准
- **不要凭空设计 UI**：新 UI 应与现有 Vue 组件风格及原版 QSS 规格保持一致

## 素材目录约定

- **应用内 UI 图标唯一存放处：`src/assets/icons/`**（svg，前端直接 import）。不要在其它目录放应用图标的副本——改图标只改这里
- 游戏资源（精灵/地图/音效/字体）唯一存放处：`engine/assets/`（详见 Architecture 一节）
- **内置图块尺寸约定**：`maps/tiles/*.png` 是单张图块（尺寸 = 图片边长，16/32 自动识别）；`maps/tilesets/<16|32>/*.png` 是多格图集（**目录名就是格子尺寸**）；`maps/tilesets/` 根目录下的图集不标尺寸，导入时**按当前地图格子切**。资源库导入时会按当前地图格子自动换算（整数倍最近邻缩放，原图保留），不要按尺寸再分一个资源库分类。

## Architecture

```
src/
  components/
    layout/MainLayout.vue       # Main app layout (menu bar + sidebar + editor area)
    canvas/GameCanvas.vue       # PixiJS game renderer (640×480 logic)
    editor/CodeEditor.vue       # Monaco code editor
    terminal/TerminalPanel.vue  # xterm.js console
    sprite-editor/              # Sprite editor (costumes, animations, preview)
    map-editor/                 # Map editor (tiles, layers, collision)
    resource-panel/             # Resource panel + upload drawer + sprite library
  stores/
    editor.ts                   # Tabs (game/code separate), mode, run state
    render.ts                   # Sprite rendering, camera, FPS
    project.ts                  # Project root, dirty flags
    terminal.ts                 # Console output (30ms throttle, 5000 lines)
    map.ts                      # Map data, layers, tile sets
    resource.ts                 # Resource items (sprites, maps, sounds, code)
    spriteLib.ts                # Built-in sprite library (.bgs/.bsf files)
    theme.ts                    # Theme system (dark/light/one-dark/nord/gruvbox)
  composables/
    useEngine.ts                # Tauri IPC: run/stop/sendInput, event listeners
    useFileDialog.ts            # Browser file open/save (Tauri-ready)
    useSpriteData.ts            # .bgs (zip) reader via JSZip
  utils/
    mapSerializer.ts            # Map JSON serialization with compression
  types/engine.ts               # Engine JSON protocol types
src-tauri/
  src/lib.rs                    # Tauri commands (file I/O, Python process)
  src/engine.rs                 # Python subprocess management (stdout/stdin)
engine/
  bingo_engine.py               # 引擎门面：引导 + 重导出公共 API + __all__（只做导出，别在这里加实现）
  game_loop.py                  # 主循环/启动/generator 调度（入口层）
  sprite.py / sprite_physics.py / sprite_assets.py / sprite_animation.py  # Sprite 主类 + 三个 Mixin
  map_runtime.py / markers.py   # 地图运行时 / 标记与射线
  camera.py / input_api.py / timing.py / game_control.py / audio.py / effects.py / collision_geometry.py
  engine_state.py               # 所有跨模块共享的可变状态（唯一存放处）
  ENGINE_MAP.md                 # 引擎模块地图（改引擎前先查这里）
  models/                       # Data models
  assets/                       # 唯一游戏资源库（Vite publicDir 指向此处）
    sprites/                     # 按分类目录组织（目录名=库标签，自动发现）
      characters/                # 角色分类（显示名"角色"）
        packages/                # .bgs / .bsf 精灵包文件
        images/                  # 精灵图片资源
      items/                     # 道具分类（显示名"道具"，结构同上）
    maps/
      packages/                 # .bgm 地图包文件（JSON格式）
      images/                   # 地图图像素材
      tiles/                    # 单张瓦片图片
      tilesets/                 # 瓦片集图片
    sounds/                     # 音效资源（.wav）
    ui/                         # UI 资源（favicon, icons）
```

## 引擎模块地图（改引擎前必读）

`engine/bingo_engine.py` 已经拆分为多个平铺模块（**不要**整目录大范围 grep，按下表直接打开）。完整版见 [engine/ENGINE_MAP.md](engine/ENGINE_MAP.md)。

| 改动内容 | 打开 |
| --- | --- |
| 用户可调用的 API（`__all__` / 导出） | `bingo_engine.py`（新增 API 还要同步 `game_loop.py` 的 `exec_globals`） |
| 帧循环、启动、暂停语义、generator | `game_loop.py` |
| 角色公开方法/属性 | `sprite.py` |
| 卡墙、穿模、斜坡、贴地、`is_touch` | `sprite_physics.py` |
| 角色图片/bsf/bgs、碰撞盒、挂点坐标 | `sprite_assets.py` |
| 动画播放、说话气泡 | `sprite_animation.py` |
| 地图加载/瓦片渲染/地图碰撞/感应区 | `map_runtime.py` |
| `get_marker(s)`、`raycast` | `markers.py` |
| 镜头跟随 | `camera.py` |
| 键鼠输入、`input()` | `input_api.py` |
| 计时器、`time_passed` | `timing.py` |
| 暂停/停止/广播/FPS | `game_control.py` |
| 音效 | `audio.py` |
| 文字/震动/随机数/显示碰撞 | `effects.py` |
| 碰撞几何纯算法 | `collision_geometry.py` |
| 跨模块共享状态（`_SPRITES`/`_STOPPED`…） | `engine_state.py` |

- **共享状态只能 `import engine_state as st` + `st._X`**，禁止 `from engine_state import _X`（值拷贝不同步）。
- **依赖单向**：`bingo_engine → game_loop → camera/map/sprite/effects → … → engine_state`；反向引用用函数内局部导入并注释原因。
- **不要新建 `engine/` 子目录**：打包只收录 `engine/*.py` 与 `engine/models/*.py`，子目录只在打包版缺失。

## 超大文件地图（前端 / Rust）

原则：**先按区块名 grep 定位，再局部阅读**，不要整文件通读。

| 文件 | 约行数 | 内部区块（搜索这些注释/符号名） | 后续拆分方向 |
| --- | --- | --- | --- |
| `src/components/map-editor/MapCanvas.vue` | ~4830 | script 约 4300 行：`图片模式`、`矢量绘制覆盖层`、`矢量绘制（覆盖层 + Paper.js 引擎）` | 矢量绘制 → `useMapVectorDrawing.ts`；位图工具 → `useMapBitmapTools.ts` |
| `src/components/layout/MainLayout.vue` | ~2750（样式已抽到 `MainLayout.css`） | `图片作为地图导入`、更新检查、菜单命令、项目操作 | 素材导入 / 更新检查 → `composables/` |
| `src/components/paint-editor/composables/usePaperScope.ts` | ~4050 | 单个 `usePaperScope()`（工具/历史/快捷键全在一起） | 按工具分组拆子 composable，再组合 |
| `src/components/sprite-editor/SpriteEditorView.vue` | ~1840（样式已抽到 `SpriteEditorView.css`） | `标记放置`、帧列表、预览 | 标记/碰撞标注 → composable |
| `src/components/map-editor/PropertyPanel.vue` | ~1910（样式已抽到 `PropertyPanel.css`） | `场景标记检视器`、`碰撞检视器`、`碰撞列表`、`图像变换`、`相机跟随`、`图块模式` | 每块一个子组件（props/emit 直连 store） |
| `src/components/paint-editor/composables/useBitmapCanvas.ts` | ~1690 | 单个 `useBitmapCanvas()` | 画笔/填充/选区拆子 composable |
| `src/components/canvas/GameCanvas.vue` | ~1200 | `getTexture`/`getCachedSpriteTextureSync`/`syncDrawTexts`/`syncHitboxes`/`gameLoop` | 纹理缓存、协议同步拆 `utils/render*` |
| `src/stores/map.ts` | ~1110 | `图块笔刷调色板`、`场景标记`、`图层 / 图像选中`、`碰撞层` | 纯计算挪 `utils/map*`，store 只留状态/action |
| `src/components/file-explorer/FileExplorer.vue` | ~560（样式已抽到 `FileExplorer.css`） | 树渲染 / 右键菜单 / 拖拽 | 右键菜单拆子组件 |
| `src-tauri/src/*.rs` | 已拆分 | `lib.rs` 只留状态与注册；命令按域在 `fs_ops/project/python_env/pack/media/pip.rs` | 新增命令请加到对应域文件并注册到 `run()` |

拆分前端 `<script setup>` 属于中高风险改动：必须 `pnpm build` + 手动点一遍相关面板（编辑器交互无法用单测覆盖）。

## Rules

- **Never reinvent the wheel** — always check official docs or peer implementations before coding custom solutions
- **Reference original PySide6 UI files before implementing any UI** — never design from scratch
- **Comments and some variable names are in Chinese** — do not change
- **Respond to user in Chinese**
- **Cross-platform safety (Mac + Windows)**: This project is a dual-platform (macOS + Windows) desktop app. When fixing Windows-specific bugs, NEVER break macOS functionality. Always check if a change uses platform-specific code paths before modifying. If the fix requires platform branching, use `#[cfg(target_os = "windows")]` / `#[cfg(target_os = "macos")]` in Rust, or `process.platform` checks in TypeScript. When in doubt, preserve the existing Mac behavior and only add Windows-specific handling.
- **每次打包发版必须更新 `CHANGELOG_USER.md`**（唯一更新日志，给普通用户看）：
  - 按 **新增 / 修复 / 改进** 分类记录，语言必须**通俗易懂、无技术术语**（面向中小学生）。只写用户能感知到的变化，不写内部实现、重构、性能开销等开发细节。
  - 未发版的 master 改动记入「未发布」小节，发版时移入正式版本号。
  - CI（`.github/workflows/release.yml`）会自动从 `CHANGELOG_USER.md` 提取当前版本的内容写入 `latest.json` 的 `notes` 字段，客户端检查更新弹窗直接展示该内容。因此日志的措辞直接决定用户看到的更新说明，务必认真写。
  - 同步更新 README 顶部「功能特性」中的当前版本号，并在 README「更新日志」一节刷新"当前最新版本"一句话摘要。
  - 纯内部修复的静默版本可以不新增日志条目：CI（`release.yml` 的 awk）与客户端（`MainLayout.vue` 的 `extractChangelogNotes`）都会自动沿用最新一条日志，用户看到的仍是上一版的说明。

## Key quirks

- **Python engine runs in subprocess**: Tauri spawns `python3 -u script.py`, captures stdout JSON instructions, sends to frontend via events. stdin receives `K_DOWN:`, `K_UP:`, `M_DOWN:`, `M_UP:`, `M_MOVE:` input events.
- **Two separate tab systems**: `gameTabs` (game mode) and `codeTabs` (IDE mode). Switching mode preserves both.
- **Upload drawer**: Green `#4B9B5C` slide-up menu, appears on hover, icons from `assets/icons/`.
- **Sprite library**: Built-in `.bgs` files (zip with config.json + PNG frames) and `.bsf` files (zip with manifest.json + sheet.png, sheet-atlas format from BingoPacker) loaded via JSZip.
- **`.bsf` runtime model**: imported into project as extracted dir (`manifest.json + sheet.png`, one texture per sprite); engine reads manifest clips and sends `frame_rect` in CREATE/UPDATE protocol, frontend `GameCanvas` swaps UV sub-textures (`getSpriteTexture`) instead of swapping files. Engine x/y for `.bsf` sprites = manifest `pivot` (per bsf-api §4); `vox/voy` computed O(1) from rect/offset/pivot — no PIL per frame. Thumbnails/previews for `.bsf` are cropped from sheet in TS (`getBsfThumbnail`), not in Rust. Sprite editor opens `.bsf` as read-only frames + editable clips (`saveBsfManifest`); frame pixel editing requires re-pack in BingoPacker. Old `.bgs` (config.json + per-frame PNG) path stays supported. `engine/assets/sprites/` 下按分类子目录组织（characters/items/...），`spriteLib.ts` 自动发现分类并在库页面显示分类标签（`CATEGORY_LABELS` 控制中文名，默认显示"角色"）。新分类=新建子目录（含 packages/ 与 images/），无需改代码。
- **单图角色标注（pivot/碰撞/挂点）**: 中心点/碰撞/标记只能由 `.bsf` manifest 承载，单张 png 角色因此长期没有标注入口。现在角色编辑器打开单图角色时在内存合成单帧 bsf 元数据（`buildSingleFrameBsfMeta`：canvas=图片尺寸、帧 rect=非透明内容框、pivot=内容框中心 —— 与引擎原「x/y=内容重心 + 自动碰撞=内容框」完全等价），**首次标注落盘时转正为 `.bsf` 目录**（`imageSpriteToBsfDir`：sheet.png=原图，资源 path/缩略图同步切换）。图片角色追加帧、绘制页保存回图片角色也统一产出 `.bsf`（原为 `.bgs`）。引擎 `_load_sprite_config` 兼容 `Sprite("角色1.png")` 式带扩展名引用（回退同名目录）。
- **Monaco editor**: Custom `bingo-dark` theme matching original QSS colors. `automaticLayout` + `nextTick layout()` for proper sizing.
- **GameCanvas only mounts when running**: Prevents PixiJS from capturing mouse events when not needed.
- **Event listeners scoped to canvas**: Keyboard/mouse events only on GameCanvas element, not window, to avoid blocking Monaco.
- **Asset directory**: `engine/assets/` is the single source of truth for all game resources. Vite serves static files from here via `publicDir` config. No `public/` directory - everything goes through `engine/assets/`.
- **Stale `_up_` resource copy (dev)**: `src-tauri/target/debug/_up_/engine/` is Tauri's incremental resource copy — it does NOT remove deleted files, so reorganizing `engine/assets/` leaves stale dirs behind and `get_engine_assets_dir`/`resolve_engine_env` used to hit them first. Fixed: both now prefer the source tree (cwd upward search) under `debug_assertions`; packaged builds unchanged. If dev behavior looks stale after a reorg, `rm -rf src-tauri/target/debug/_up_`.
- **更新检查必须走 Tauri 更新插件 `check()`**: 请求由 Rust 侧发出，不受网页跨域限制。**绝不能用网页 `fetch()` 去取 GitHub 上的 `latest.json`** —— GitHub Release 资源的 302 跳转链路不带 `Access-Control-Allow-Origin`，正式包里 fetch 必定失败并报「无法获取更新信息」，而 dev 模式因为另走了内置日志分支看不到这个坑。已是最新版时弹窗里的更新说明读打包进前端的 `CHANGELOG_USER.md`（`?raw` 导入），离线可用。
- **Map format**: JSON with base64+zlib compressed tile data. `.bgm` files are zips containing `map.json` + `thumbnail.png`. No binary format.
- **Default project directory**: `~/BingoCodeIDE/Projects/default/` - cleaned on startup, stores user-created sprites and maps.

## Original QSS color reference

- Background: `rgb(34, 37, 43)` / `#22252B`
- Editor area: `rgb(41, 44, 52)` / `#292C34`
- Border: `rgb(12, 12, 12)` / `#0C0C0C`
- Hover: `rgb(61, 64, 72)` / `#3D4048`
- Accent green: `rgb(91, 251, 132)` / `#5BFB84`
- Upload drawer green: `#4B9B5C`
- Upload drawer hover: `#5bc772`
- Tab active border: `rgb(91, 251, 132)`
- Run red: `rgb(95, 45, 39)` / `#5F2D27`

## Dependencies

```
pnpm install
```

Frontend: Vue 3, Pinia, PixiJS 8, Monaco Editor, xterm.js, TailwindCSS, JSZip, pako
Desktop: Tauri v2, Rust, tauri-plugin-shell
Engine: Python 3, Pillow, NumPy (in `engine/venv/`)

## Cross-computer sync

```
bash setup.sh        # 首次: 创建 MEMORY.md 符号链接
bash sync-memory.sh  # 日常: 同步记忆 ↔ .mimocode/memory/
```

**Workflow:**
1. 公司电脑: `git pull` → `bash setup.sh` → `bash sync-memory.sh`
2. 编码
3. 公司电脑: `bash sync-memory.sh` → `git add .mimocode/memory/` → `git commit && git push`
4. 家里电脑: `git pull` → `bash setup.sh` → `bash sync-memory.sh`
5. 编码...
6. 家里电脑: 同步骤 3
7. 公司电脑: 同步骤 1
