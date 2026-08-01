# Project memory
_Durable project-level knowledge. Persists across all sessions in this project. Edit only content under italic instructions._

## Project context
_BingoCodeIDE_ — Tauri v2 + Vue 3 + PixiJS desktop IDE for game development with a Python engine (`bingo_engine.py`). Refactored from a PySide6 version (see sibling project MyIDE for legacy knowledge). Two modes: game mode (visual editors + code + preview) and IDE mode (Python editing + run/stop). Engine runs in subprocess, communicates via JSON over stdout/stdin.

## Rules
_Hard constraints from user that every session must respect._

- Reference original PySide6 UI files before implementing any UI — never design from scratch (see AGENTS.md)
- Comments and some variable names are in Chinese — do not change
- Respond to user in Chinese
- Game stage size is hardcoded to 640x480
- Engine uses unbuffered stdout — do not change
- Target audience is elementary school students — API must be extremely simple
- **Never reinvent the wheel** — always check official docs or peer implementations [ses_0fca6436bffe]
- **Research before implementing** — do not guess at APIs; research documentation when fixes fail [ses_0f76eaddaffe]
- **控制台输出必须干净简单** — 只显示程序实际输出，绝不显示技术信息。目标用户是小学生。[ses_09c5077a4ffe]
- **调试必须追踪代码根因** — 不要猜测，必须通过代码追踪确认根因后再修复。dev 模式验证。[ses_09c5077a4ffe]
- **代码模式运行 Python 必须用 `run_script_file`** — 不要通过 shell PTY。piped stdin/stdout/stderr，避免回映。[ses_09c5077a4ffe]

## Architecture decisions
_Major design choices with rationale._

- **PySide6 → Tauri v2 refactor**: Python engine retained as subprocess. JSON commands over stdout/stdin.
- **Two tab systems**: `gameTabs` (game mode) and `codeTabs` (IDE mode). Switching mode preserves both.
- **GameCanvas mounts only when running**: Prevents PixiJS mouse capture. Events scoped to canvas element, not window.
- **Game mode three sub-pages**: `activeEditorMode` controls `'code'`/`'sprite'`/`'map'` views. `setResourceTab()` is ONLY for sidebar switching (角色/场景/声音/代码).
- **Code mode fully isolated**: Own menu, never modifies game-mode state.
- **Two execution modes**: Default Python (terminal output) + Game engine mode (PixiJS rendering). [ses_0f3269daffe]
- **Bundled Python**: python-build-standalone. `resolve_engine_env` fallback: bundled → venv → system. [ses_0f3269daffe]
- **移除代码检查按钮**: pyflakes 静态分析与运行时 Python 异常提示高度重叠，对目标用户（小学生）无实际价值，完全移除。[ses_04894c7f7ffe]

## Discovered durable knowledge (terminal/console)

- **终端双通道**: 游戏模式 `engine.rs` 子进程（piped），代码模式 `shell.rs` PTY。完全独立 I/O。[ses_09c5077a4ffe]
- **PTY 回映不可抑制**（2次打包确认）: 内核级机制，`stty -echo` 有延迟且与输入混淆。[ses_09c5077a4ffe]
- **`input()` 提示无换行使 `read_line()` 阻塞**: 必须用 `Read::read()` 替代。[ses_09c5077a4ffe, ses_08c1fa6b0ffe]
- **`send_stdin` 追加 `\n` 不适合代码模式**: 需 `send_stdin_data`，前端 `\r` → `\n`。[ses_09c5077a4ffe]
- **输入路由用 `terminalMode`**: `isRunning` 可被提前置 false。用独立 `terminalMode`（`'shell'`/`'python'`）。[ses_09c5077a4ffe]
- **代码模式跳过 shell `runEndTimer`**: 否则 1 秒后误判脚本结束。[ses_09c5077a4ffe]
- **Python `-u` 不解缓冲文本 I/O**: 管道模式必须 `PYTHONUNBUFFERED=1`。[ses_08c1fa6b0ffe]
- **前端 RAF 缓冲延迟**: `handleCodeStdout` 已改为直接写入 xterm.js。[ses_08c1fa6b0ffe]

## compose-preferences

- execution-style: subagent

## Discovered durable knowledge
_Cross-task facts that survive across sessions._

- **pnpm PATH gotcha**: `npm install -g pnpm` does NOT add to PATH. Use full path or `npx`. `npm bin -g` removed in npm v11 — use `npm prefix -g`. [ses_0fca6436bffe]
- **Engine API design for kids**: No import needed, auto-concat args, one-line configs, no blocking in game loops. [MyIDE MEMORY]
- **`__all__` requirement**: New functions/classes in `bingo_engine.py` MUST be added to `__all__`. [MyIDE MEMORY]
- **Tauri dev mode**: `externalBin`/`resources` can be emptied for dev — `find_system_python()` resolves at runtime. [ses_0fca6436bffe]
- **Tauri v2 capabilities mandatory for window ops**: `capabilities/default.json` must declare `core:window:allow-{close,minimize,toggle-maximize,start-dragging}`. #1 trap for custom title bars. [ses_0fca6436bffe]
- **Tauri `beforeunload` 对原生关闭按钮无效**: 必须用 `getCurrentWebviewWindow().onCloseRequested()` 拦截窗口关闭。[ses_04894c7f7ffe]
- **Tauri `window.confirm()` 返回 Promise**: 在 Tauri v2 webview 中 `window.confirm()` 返回 Promise 对象而非 boolean，`if(obj)` 永远 true。必须用 `@tauri-apps/plugin-dialog` 的 `ask()`。[ses_04894c7f7ffe]
- **Tauri `onCloseRequested` + `close()` 需防重复触发**: `close()` 会再次触发 `onCloseRequested`，需用 flag 防止无限循环。[ses_04894c7f7ffe]
- **Tauri capabilities 需声明 `close` 和 `destroy`**: `appWindow.close()` 需要 `core:window:allow-close`，`appWindow.destroy()` 需要 `core:window:allow-destroy`。[ses_04894c7f7ffe]
- **Tauri v2 `emit_to("main", ...)` over `emit()`**: From background threads, `app.emit()` unreliable. Use `app.emit_to("main", event, payload)` + `"core:event:default"` capability. [ses_0f3269daffe]
- **macOS rounded corners**: CSS `border-radius` can't do window-level. Use `decorations: true` + `titleBarStyle: "Transparent"` + `hiddenTitle: true`. Windows ignores these. [ses_0fca6436bffe]
- **Qt QLayout stretches widgets**: When translating Qt to CSS flexbox, use `align-self: stretch` + `padding` on children. Don't assume natural size. [ses_0fca6436bffe]
- **Console panel always-render**: Collapsible panels: keep rendered, use internal `collapsed` state. Header bar (26px) stays visible. No `v-show`/`v-if` on wrapper. [ses_0fca6436bffe, ses_0f376fc72ffe]
- **Sprite data model**: `{name, frames[], segments[{name, start, end, fps, loop}]}`. Frames are PNGs in same dir. [ses_0fca6436bffe]
- **Sprite editor architecture**: Three-panel — costume list (100px), canvas, preview (264px). [ses_0fca6436bffe]
- **PNG must be RGBA for Tauri icons**: `generate_context!()` panics otherwise. Use `Image.convert('RGBA')`. [ses_0fca6436bffe]
- **Vue v-if + ref timing**: May need double `nextTick` or `document.querySelector` fallback. [ses_0fca6436bffe]
- **Vue watch array spread**: `watch(() => [...array])` ensures firing on in-place mutations. [ses_0fca6436bffe]
- **Pinia reactive replacement**: `obj.name = newName` may not trigger watchers. Use `{ ...obj, name: newName }`. [ses_0fca6436bffe]
- **`.editor-page-full`**: Use `flex: 1; min-width: 0; min-height: 0;` in flex parents. Missing `min-width: 0` causes overflow when sibling (side panel) grows. [ses_0f376fc72ffe, ses_04894c7f7ffe]
- See MEMORY-PixiJSMapEditor.md — PixiJS 8 patterns, map editor, drag/resize, auto-save
- **`xattr -cr` may fail under SIP**: Use `sudo xattr -cr` or "Open Anyway" in System Settings. [ses_08c1fa6b0ffe]
- **Windows `hidden_command()`**: `lib.rs` wraps `CREATE_NO_WINDOW` (0x08000000). All `Command::new()` must use it. [ses_08c1fa6b0ffe]
- **pyflakes 已从检查按钮移除**: 检查按钮（ideCheckCode）与运行时错误提示高度重叠，对小学生用户鸡肋，已完全移除。pyflakes 也从 PluginManager 内置包列表移除。[ses_04894c7f7ffe]
- **GitHub Actions matrix**: Edit `os` array in `.github/workflows/release.yml`. `workflow_dispatch` for manual. [ses_08c1fa6b0ffe]
- **Windows Python encoding**: `PYTHONIOENCODING=utf-8` required — Windows uses GBK/CP936. [ses_08c1fa6b0ffe]
- **Windows `py` launcher path trap**: `where py` returns launcher, not Python. Use `py -3 -c "import sys; print(sys.executable)"`. [ses_08c1fa6b0ffe]
- **`tasklist` locale-dependent**: Check for PID digits, not English text. [ses_08c1fa6b0ffe]
- **Tauri 资源打包**: `resources` extracts flat to `resource_dir/portable-python/`. `resolve_engine_env` searches accordingly. [ses_08c1fa6b0ffe]
- **`Child::wait()` over polling**: Cross-platform blocking wait, no tasklist needed. [ses_08c1fa6b0ffe]
- **resolve_engine_env must include venv Python**: Dev needs venv for black. [ses_08c1fa6b0ffe]
- **Monaco comment italic 光标重叠**: 斜体字视觉宽度偏移但光标按正体计算。移除 `fontStyle: 'italic'` 修复。[ses_04894c7f7ffe]
- **Monaco suggest widget 宽度不随字体缩放**: 需非 scoped CSS 设 `min-width: 360px` + `overflow: visible` on `.column-label`。[ses_04894c7f7ffe]
- **Monaco triggerCharacters 空格陷阱**: 空格触发导致每次按空格弹补全。移除后不影响 `.` 触发和 quickSuggestions 自动弹出。不要设 `quickSuggestions: false`。[ses_04894c7f7ffe]
