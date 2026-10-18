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

## Critical Rule: Reference Original First

**Before implementing ANY UI or interaction, ALWAYS read the original PySide6 UI files first:**

- `legacy/ui/main_window_ui.py` — Main layout, all widget hierarchy
- `legacy/ui/file_menu_ui.py` — File menu popup
- `legacy/ui/upload_menu_ui.py` — Sprite upload drawer
- `legacy/ui/map_upload_ui.py` — Map upload drawer
- `legacy/ui/sound_upload_ui.py` — Sound upload drawer
- `legacy/ui/map_resource_import_ui.py` — Map resource import dialog
- `legacy/assets/qss/dark_style.qss` — All styling (colors, sizes, spacing)
- `legacy/assets/qss/sprite_editor_style.qss` — Sprite editor styles
- `legacy/assets/qss/map_editor_style.qss` — Map editor styles

**Never design UI from scratch.** The original has carefully crafted layouts, colors, and interaction patterns. Match them exactly.

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
  bingo_engine.py               # Game engine (runs in Python subprocess)
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

## Rules

- **Never reinvent the wheel** — always check official docs or peer implementations before coding custom solutions
- **Reference original PySide6 UI files before implementing any UI** — never design from scratch
- **Comments and some variable names are in Chinese** — do not change
- **Respond to user in Chinese**
- **Cross-platform safety (Mac + Windows)**: This project is a dual-platform (macOS + Windows) desktop app. When fixing Windows-specific bugs, NEVER break macOS functionality. Always check if a change uses platform-specific code paths before modifying. If the fix requires platform branching, use `#[cfg(target_os = "windows")]` / `#[cfg(target_os = "macos")]` in Rust, or `process.platform` checks in TypeScript. When in doubt, preserve the existing Mac behavior and only add Windows-specific handling.
- **每次打包发版必须更新 CHANGELOG.md**：打 tag 发布前，在根目录 `CHANGELOG.md` 的「更新日志」中为该版本号添加条目（最新在前），按 **新增 / 修复 / 优化 / 资源** 分类写清新功能与修复的 bug。未发版的 master 改动记入「未发布」小节，发版时移入正式版本号。同步更新 README 顶部「功能特性」中的当前版本号，并在 README「更新日志」一节刷新"当前最新版本"一句话摘要。

## Key quirks

- **Python engine runs in subprocess**: Tauri spawns `python3 -u script.py`, captures stdout JSON instructions, sends to frontend via events. stdin receives `K_DOWN:`, `K_UP:`, `M_DOWN:`, `M_UP:`, `M_MOVE:` input events.
- **Two separate tab systems**: `gameTabs` (game mode) and `codeTabs` (IDE mode). Switching mode preserves both.
- **Upload drawer**: Green `#4B9B5C` slide-up menu, appears on hover, icons from `assets/icons/`.
- **Sprite library**: Built-in `.bgs` files (zip with config.json + PNG frames) and `.bsf` files (zip with manifest.json + sheet.png, sheet-atlas format from BingoPacker) loaded via JSZip.
- **`.bsf` runtime model**: imported into project as extracted dir (`manifest.json + sheet.png`, one texture per sprite); engine reads manifest clips and sends `frame_rect` in CREATE/UPDATE protocol, frontend `GameCanvas` swaps UV sub-textures (`getSpriteTexture`) instead of swapping files. Engine x/y for `.bsf` sprites = manifest `pivot` (per bsf-api §4); `vox/voy` computed O(1) from rect/offset/pivot — no PIL per frame. Thumbnails/previews for `.bsf` are cropped from sheet in TS (`getBsfThumbnail`), not in Rust. Sprite editor opens `.bsf` as read-only frames + editable clips (`saveBsfManifest`); frame pixel editing requires re-pack in BingoPacker. Old `.bgs` (config.json + per-frame PNG) path stays supported. `engine/assets/sprites/` 下按分类子目录组织（characters/items/...），`spriteLib.ts` 自动发现分类并在库页面显示分类标签（`CATEGORY_LABELS` 控制中文名，默认显示"角色"）。新分类=新建子目录（含 packages/ 与 images/），无需改代码。
- **Monaco editor**: Custom `bingo-dark` theme matching original QSS colors. `automaticLayout` + `nextTick layout()` for proper sizing.
- **GameCanvas only mounts when running**: Prevents PixiJS from capturing mouse events when not needed.
- **Event listeners scoped to canvas**: Keyboard/mouse events only on GameCanvas element, not window, to avoid blocking Monaco.
- **Asset directory**: `engine/assets/` is the single source of truth for all game resources. Vite serves static files from here via `publicDir` config. No `public/` directory - everything goes through `engine/assets/`.
- **Stale `_up_` resource copy (dev)**: `src-tauri/target/debug/_up_/engine/` is Tauri's incremental resource copy — it does NOT remove deleted files, so reorganizing `engine/assets/` leaves stale dirs behind and `get_engine_assets_dir`/`resolve_engine_env` used to hit them first. Fixed: both now prefer the source tree (cwd upward search) under `debug_assertions`; packaged builds unchanged. If dev behavior looks stale after a reorg, `rm -rf src-tauri/target/debug/_up_`.
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
