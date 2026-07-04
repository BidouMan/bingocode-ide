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
    spriteLib.ts                # Built-in sprite library (.bgs files)
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
    sprites/
      packages/                 # .bgs 精灵包文件
      images/                   # 精灵图片资源
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

## Key quirks

- **Python engine runs in subprocess**: Tauri spawns `python3 -u script.py`, captures stdout JSON instructions, sends to frontend via events. stdin receives `K_DOWN:`, `K_UP:`, `M_DOWN:`, `M_UP:`, `M_MOVE:` input events.
- **Two separate tab systems**: `gameTabs` (game mode) and `codeTabs` (IDE mode). Switching mode preserves both.
- **Upload drawer**: Green `#4B9B5C` slide-up menu, appears on hover, icons from `assets/icons/`.
- **Sprite library**: 14 built-in `.bgs` files (zip with config.json + PNG frames), loaded via JSZip.
- **Monaco editor**: Custom `bingo-dark` theme matching original QSS colors. `automaticLayout` + `nextTick layout()` for proper sizing.
- **GameCanvas only mounts when running**: Prevents PixiJS from capturing mouse events when not needed.
- **Event listeners scoped to canvas**: Keyboard/mouse events only on GameCanvas element, not window, to avoid blocking Monaco.
- **Asset directory**: `engine/assets/` is the single source of truth for all game resources. Vite serves static files from here via `publicDir` config. No `public/` directory - everything goes through `engine/assets/`.
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
