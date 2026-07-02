# Project memory
_Durable project-level knowledge. Persists across all sessions in this project. Edit only content under italic instructions._

## Project context
_BingoCodeIDE_ is a Tauri v2 + Vue 3 + PixiJS desktop IDE for a custom 2D game engine ("BingoEngine"), refactored from a PySide6 version. Visual game development with sprites, tile-based maps, sounds, and Python scripting. Two modes: game mode (visual editors + code editor + live preview) and IDE mode (pure code editing). Python engine runs as subprocess, communicates via JSON commands over stdin/stdout. Original PySide6 version preserved in `backup/pre-refactor` branch.

## Rules
_Hard constraints from user that every session must respect._

- AGENTS.md should be maintained at repo root: `/Users/amixc/MyWorkSpace/CodeStaction/BingoCodeIDE/AGENTS.md`
- **ALWAYS reference original PySide6 UI files before implementing ANY UI**: Read `legacy/ui/*.py` and `legacy/assets/qss/*.qss` first. Never design UI from scratch — the original has carefully crafted layouts, colors, and interaction patterns. Match them exactly.
- **NEVER reinvent the wheel for solved problems**: Before implementing any feature, research how established apps (Scratch, Godot, Unity, etc.) solve the same problem. Use proven libraries and patterns. Drag-and-drop, file operations, undo/redo, etc. are solved problems — find and use existing solutions. Only deviate if the original truly doesn't cover the case.
- **Systematic debugging before fixes**: User explicitly rejects guesswork. Must add debug logging, trace execution paths bottom-up, identify exact failure point first.

## Architecture decisions
_Major design choices with rationale. The "why" matters more than the "what" for future sessions._

- **Engine as subprocess**: `bingo_engine.py` runs as a Tauri-spawned subprocess (Rust `Command::spawn()`). Isolates user script crashes from IDE. Engine sends JSON commands to stdout; keyboard input piped via stdin.
- **JSON command protocol (15 types)**: CREATE, UPDATE, DELETE, SAY, CREATE_BATCH, CAMERA_UPDATE, SCENE_UPDATE, PLAY_SOUND, DRAW_TEXT, STOP_SOUND, SCREEN_SHAKE, FPS_UPDATE, UI_COMMAND, PLAY_ANIMATION, RESET. Engine sends absolute paths — web version needs file:// URL resolution.
- **Full rewrite to Tauri + Vue 3 + PixiJS**: Old PySide6 version in `backup/pre-refactor` (commit `87bbc32`). Engine stays Python; only IDE shell and renderer replaced.
- **Tauri v2 as desktop shell**: File I/O, Python process spawning, stdout streaming. Rust core minimal — no business logic.
- **PixiJS replaces QGraphicsView**: WebGL rendering for tiles, sprites, collision. Spatial Hashing + Chunked Map Data for infinite maps. Texture Atlas limit 2048×2048.
- **Standard stage**: 640×480 fixed engine resolution. All collision, camera, rendering assumes this.
- **Two separate tab systems**: `gameTabs` (game mode) and `codeTabs` (IDE mode). Switching mode preserves both.
- **UI layout must match original PySide6**: Left sidebar (340px): game preview (320×240) + resource tabs/lists. Right: tab bar + code editor + console splitter. NOT VS Code-like.
- **Editor area uses stacked-page architecture**: Like original `editor_stacked` QStackedWidget — each mode (game/sprite/map/code) is a full independent page. Sprite/map/IDE editors hide sidebar+tabs+console entirely.
- **Map format → JSON**: User confirmed migrating back to JSON (originally JSON before binary). Must preserve all functionality.
- **Map editor features after full audit**: Move tool, right-click image rotation, scroll-wheel scaling, collision polygon closing/edge insertion, auto-save (500ms debounce to localStorage), layer locking, context menu prevention.
- **Sprite library uses built-in .bgs files**: 14 packs in `public/sprite_lib/`. Read via JSZip in browser. Sprite editor also reads .bgs directly via JSZip.
- **Code tab has no upload drawer**: User explicitly requested. Only sprite/map/sound tabs show upload button. Drawer overlaps upload button via negative margin.
- **Terminal throttling**: 30ms throttle buffer + 5000 line cap on frontend.
- **Environment isolation**: All deps project-local. Python uses `engine/venv/`.

## Discovered durable knowledge
_Cross-task facts that survive across sessions. Promoted from session checkpoints' §7 when proven durable._

### Toolchain & framework quirks
- **`@monaco-editor/loader` dynamic import**: Returns `{ default: loaderFunction }`. Use `const loader = mod.default || mod` before `loader.init()`.
- **Monaco editor sizing in flex**: `flex: 1; min-height: 0` on parent+child. `nextTick(() => { editor.layout(); editor.focus() })` after creation. Focus issues: `position: absolute; inset: 0` on container.
- **Vite SVG icon import (MANDATORY)**: All icons via ES module `import` in `<script setup>`, NEVER raw `src` strings. Dynamic `:src="`...${var}`"` doesn't work. Type declarations at `src/types/assets.d.ts`. Enforced project-wide.
- **PixiJS captures events globally**: Use `v-if` to prevent mounting when not needed. Scope event listeners to canvas element. Canvas intercepts drag events — must register on `document` or parent HTML.
- **Vite 8 uses rolldown bundler**, needs `esbuild` (`pnpm approve-builds`), build target `es2020` (not `safari13`).
- **TypeScript 6.0 deprecates `baseUrl`**: Need `"ignoreDeprecations": "6.0"` in tsconfig.json.
- **TailwindCSS 4**: Uses `@tailwindcss/vite` plugin (not PostCSS).
- **Vite cache stale code**: Clear `node_modules/.vite` + `dist/`, restart dev server, hard-refresh (Cmd+Shift+R) after changes.
- **Tauri devtools**: `Cmd+Option+I` on macOS (not F12). Console tab for JS logs.

### Vue patterns
- **Vue reactivity**: Direct array index assignment doesn't trigger reactivity. Use `splice()`, `push()`, `pop()`, or `toSpliced()`.
- **Vue `v-for="n in count"` is 1-based**: Data is 0-indexed — use `i-1` offset.
- **Native `<select>` can't be styled**: Dropdown popup is system-controlled. Use `CustomSelect.vue` for full theme control.

### File formats
- **`.bgs` (sprite pack)**: ZIP with `config.json` + PNG frames. Config: `{ name, count, frames[], segments[{name, start, end}] }`. Read via JSZip.
- **`.bgm` (map data)**: ZIP with .info/.tiles/.collision/.resources + `thumbnail.png`. Same JSZip pattern. Thumbnail 150×110.
- **`.bingo` (zipped game project)**.
- **Tile ID encoding**: `(global_resource_index + 1) * 1000 + tile_index + 1`. Resource 0 tile 0 = 1001.

### Map editor
- **Per-layer resource isolation**: Each layer has its own `resources: MapResource[]`. Flat global `mapResources` is dead code after refactor — causes rendering bugs.
- **Two modes**: Image mode (`activeLayer.type === 'image'`) for placing full images freely. Drawing mode (`activeLayer.type === 'drawing'`) for painting tiles on grid. ResourceListPanel branches UI on layer type.
- **ImageData interface**: `{ imagePath, position: [x,y], rotation, scale, scaleX, scaleY, opacity, width, height, collisionType, collisionEnabled, collisionShape? }`.
- **`placeImage`**: Loads actual image dimensions via `loadImage(path)`, fallback 64×64. Stored in `layer.images[]` (part of `mapData`, auto-saved).
- **Resource library adds tilesets, not maps**: `onResLibImported` calls `mapStore.addResource()`. Never `resourceStore.addItem({ type: 'map' })`.
- **Tile rendering (PixiJS 8)**: Per-layer `PIXI.Container` with `zIndex`. Tile textures sliced via offscreen canvas. Source images cached in `Map<string, HTMLImageElement>`.
- **Collision editor**: tileSet index must use `globalResourceOffset` (layer-local → global). `loadCollision` reads points into editor state — don't invert.
- **`addResource` must create matching TileSet**: Otherwise `setTileCollision()` silently fails.
- **Flood fill bounds check mandatory**: Without it, filling empty map crashes browser.
- **`addLayer` ID must use `Math.max`**: `layers.length` collides with imported IDs.
- **Map switching must preserve/restore data**: Fresh empty maps discard tile work. Load from saved state or localStorage.
- **PixiJS drag events in Tauri**: HTML5 drag-and-drop API (`dragover`/`drop`) never fires in Tauri webview — not on `app.canvas`, not on `document`, not anywhere. This is a Tauri/Electron compatibility issue, not a PixiJS issue. Use mousedown/mousemove/mouseup pattern with CustomEvent dispatch instead (proven by Scratch, Godot, etc.). See `ResourceListPanel.vue` `onResourceMouseDown` and `MapCanvas.vue` `onScratchDrop` for implementation.
- **Click-to-place vs drag-and-drop**: Both call `placeImage()` → `renderAllLayers()` pipeline. Click-to-place (via `screenToWorld()`) works. Scratch-style drag (via manual coordinate calculation in `onScratchDrop`) may produce wrong world coordinates if `app.stage.x/y` or `currentScale` values are unexpected. Always use `screenToWorld()` for coordinate conversion.

### Map editor UI conventions (match original PySide6)
- **Panel width**: Left/right 272px = 256px content + 8px margin each side. Content areas `margin: 0 8px`, `background: rgb(30,30,30)` for visual distinction.
- **No blue focus borders**: User rejected `#528bff`. Focus = hover color (`rgb(65,69,82)`).
- **PropertyPanel**: att-frame gap 16px. Physical attribute tag input only shows when "自定义" selected.
- **Import callback rule**: Library imports return to main page (`currentPage = 0`) but must NOT call `setActiveEditorMode`. Only double-click navigates to editor.
- **Square card grid pattern**: `aspect-ratio: 1` on `.lib-card`, `grid-auto-rows: max-content` + `align-content: start`. Gap 8px.

### Engine & subprocess
- **macOS stdin writing**: Must hold `child.stdin` handle from `Command::spawn()` and write via `stdin.write_all()`.
- **Physics runs at 60Hz** with accumulator pattern. Camera follow triggers re-render when movement ≥ `tile_size // 2`.
- **Engine sends absolute paths** in CREATE/UPDATE commands — web version needs file:// URL resolution.
- **Python deps (Pillow/NumPy) are for engine, not IDE**.

### User workflow rules
- **Systematic debugging before fixes**: User explicitly rejects guesswork. Must add debug logging, trace execution paths bottom-up, identify exact failure point first.
- **Honest code-trace audit required**: "Function exists" ≠ "function works". Must verify actual execution, not just code presence.
- **Browser file ops**: `<input type="file">` for open, `<a download>` for save. Temporary Tauri replacement.
- **Resource auto-selection**: Sidebar lists auto-select first item on tab switch and list changes.
