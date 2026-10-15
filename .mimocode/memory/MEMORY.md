Topic: BingoCodeIDE 项目记忆 — Tauri v2 + Vue 3 + PixiJS 游戏IDE，Python引擎子进程，服务60节Python游戏启蒙课

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
- **Game mode navigation invariant**: All `setGameMode()` calls in game mode must pass `true`. Only `toggleGameMode()` (user-facing mode toggle) may set it to `false`. When navigating between editors within game mode, only `setActiveEditorMode()` should change — never touch `isGameMode`. [ses_f4cfba0c5ffe]
- **Code mode fully isolated**: Own menu, never modifies game-mode state.
- **Two execution modes**: Default Python (terminal output) + Game engine mode (PixiJS rendering). [ses_0f3269daffe]
- **Bundled Python**: python-build-standalone. `resolve_engine_env` fallback: bundled → venv → system. [ses_0f3269daffe]
- **移除代码检查按钮**: pyflakes 静态分析与运行时 Python 异常提示高度重叠，对目标用户（小学生）无实际价值，完全移除。pyflakes 也从 PluginManager 内置包列表移除。[ses_04894c7f7ffe]
- **本地图片统一用 invoke 读取**: 不使用 `convertFileSrc` + `fetch`。`convertFileSrc` 生成的 asset protocol URL 对中文路径编码有问题，`fetch` 对本地路径无效。统一用 `invoke('read_image_as_data_url')` 读取本地图片返回 data URL。适用于：缩略图加载、地图编辑器瓦片集加载、GameCanvas 运行时渲染。[ses_f4cfba0c5ffe]
- **课程产品定位**: 引擎服务一套 Python 游戏启蒙课——约 60 节 × 2 小时、1–1.5 年，面向学完 Scratch 但基础较弱的小学生；筛选机制：能力强的提前进入 Python/C++，能力弱的继续学。课件以作品为导向（Scratch 风格）、由易到难。教学原则：教概念（变量/循环/事件/坐标）而非引擎 API，以保证迁移性。产品定位是"游戏创作入门"而非"Python 教学工具"（管理家长预期）。[ses_ed1279af4ffe]
- **课件六阶段结构（大纲已写入桌面）**: 伙伴小镇 L1-10（单角色控制/while True/if/键鼠/随机）→ 水果接接乐 L11-22（变量计分/碰撞/生成销毁/函数/游戏状态）→ 跳跳大冒险 L23-36（地图编辑器/重力跳跃/摄像机/动画/关卡）→ 星际保卫战 L37-48（组/批量碰撞/广播/多文件/状态机/波次）→ 毕业创作 L49-60（选题规划/制作周/内测/展示）。阶段末 L10/L22/L36/L48 设闯关挑战标记 A 层学员；分流点设在阶段末（保证完整作品体验）。课件文件：`/Users/amixc/Desktop/BingoPython游戏创作课-60课时课程大纲.md`。[ses_ed1279af4ffe]
- **开篇教学法（Run→Modify→Build）**: 文本代码不像积木"拼不上"，弱孩子会卡在读错误信息。开篇策略：先运行预置项目（成就感）→ 改参数（理解代码控制行为）→ 从零搭建（内化）。L1 铁律："第一节课没有人打字超过 10 行代码"。比 Scratch 的"从零拼积木"对文本语言更友好。[ses_ed1279af4ffe]
- **课件文档已完成（2026-10-12）**: `/Users/amixc/Desktop/BingoPython游戏创作课-60课时课程大纲.md` 现已完整——课程框架 + L1-60 全部 60 课教案 + 评估体系（四类工具/作品评分四维度/A层分流节点 L10/L22/L36/L48/L60/C层支持五措施）+ 教师资源准备清单（素材缺口：引擎仅 3 音效，阶段三四需自备爆炸/跳跃/受伤/过关；背景图按主题各 2-3 张）+ 附录 A-E（Scratch→Python 对照表/常见错误速查/课时弹性调整/Python/C++ 衔接说明/设计理念六条"为什么"）+ 结语。评估原则：作品导向、不考试不排名、闯关为限时解谜挑战。[ses_ed1279af4ffe]
- **课件扩充方向（用户 2026-10-12 确认）**: 用户认可大纲方向——L1-40 主要学脚本，L40 以后做经典命题游戏。核心痛点：课件数量必须足够多（中期学生 20 分钟写完小课件撑不满 2 小时；数量够才有筛选/删减余量）。整合来源：我的六阶段大纲 + 用户自己的课件草稿（`/Users/amixc/MyWorkSpace/NoteBook/Inbox/Python课件/课程体系.md`）+ Scratch 经典命题。扩充版课件清单交付位置：`/Users/amixc/MyWorkSpace/NoteBook/Inbox/Python课件/`（表格形式、先不写详细）。[ses_ed1279af4ffe]
- **90课表格版整合交付（2026-10-12 完成）**: `/Users/amixc/MyWorkSpace/NoteBook/Inbox/Python课件/课件总库-90课表格版.md` 已写入。结构：90 课池 / 建议授课 60-70；六阶段：初见代码 L1-12 / 有规则的世界 L13-26 / 代码的复利 L27-40 / 经典命题游戏工坊 L41-72（16 命题×2 课选做制：A骨架版+B完整版）/ 毕业创作 L73-84 / 毕业与远航 L85-90。属性标记 ★核心/○弹性/◆选做。整合取舍：保留用户 print-first+咒语卡24张+代码侦探+掀开引擎盖子+迷你游戏库存；保留我的 Run→Modify→Build+分层+评估；新增 Scratch 经典命题（吃豆人/坦克/节奏/投篮/弹弓/扫雷/五子棋/电子宠物/塔防/冰火/俄罗斯方块）。16 命题：Flappy进阶/无限跑者/吃豆人/坦克大战/弹幕射击/打砖块大作战/节奏大师/投篮高手/弹弓怒鸟/扫雷探险/五子棋AI/电子宠物/塔防保卫战/冰火双人/Boss Rush/俄罗斯方块。附录含弹性策略（快班加餐/慢班减负/时长不足预案）+Scratch 对应表+咒语卡清单+评估分流。[ses_ed1279af4ffe]
- **用户课件教学理念（《课程体系.md》草稿核心，2026-10-12 读取）**: 三铁律——每课有能玩的作品 / 语法 Just-in-Time / 每课自由改造时间。术语降维：print=咒语、变量=贴了标签的格子、函数=自制咒语、列表=购物袋、报错=引擎在向你求救、调试=当侦探。咒语卡体系 24 张分四阶段。120 分钟节奏：成品演示→热身→咒语卡→跟做→分层自由改造（必做/进阶/王者）→分享→保存仪式。阶段六独有"掀开引擎的盖子"（展示 move() 背后翻译 + 纯 Python 裸奔体验）。教师配套：半成品工程包+课堂模板一键还原（用户列为最高优先级引擎需求）+咒语卡打印+分层挑战卡。评估：第 20/40 课加速评估三维观察制，成长档案"发给家长的不是成绩单，是孩子的创造史"。[ses_ed1279af4ffe]

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

### Tauri 核心

- **Tauri v2 capabilities mandatory for window ops**: `capabilities/default.json` must declare `core:window:allow-{close,minimize,toggle-maximize,start-dragging}`. #1 trap for custom title bars. [ses_0fca6436bffe]
- **Tauri `beforeunload` 对原生关闭按钮无效**: 必须用 `getCurrentWebviewWindow().onCloseRequested()` 拦截窗口关闭。[ses_04894c7f7ffe]
- **Tauri `window.confirm()` 返回 Promise**: 在 Tauri v2 webview 中 `window.confirm()` 返回 Promise 对象而非 boolean，`if(obj)` 永远 true。必须用 `@tauri-apps/plugin-dialog` 的 `ask()`。`onCloseRequested` + `close()` 需防重复触发: `close()` 会再次触发 `onCloseRequested`，需用 flag 防止无限循环。[ses_04894c7f7ffe]
- **Tauri capabilities 需声明 `close` 和 `destroy`**: `appWindow.close()` 需要 `core:window:allow-close`，`appWindow.destroy()` 需要 `core:window:allow-destroy`。`emit_to("main", ...)` over `emit()`: From background threads, `app.emit()` unreliable. Use `app.emit_to("main", event, payload)` + `"core:event:default"` capability. [ses_0fca6436bffe, ses_0f3269daffe]
- **Tauri 窗口关闭调试**: 关闭后 console 丢失，需用文件写日志（`invoke('write_file', ...)` 写到 `/tmp/`）排查。productName 影响 About 菜单: `tauri.conf.json` 的 `productName` 和 `Cargo.toml` 的二进制文件名都会影响 macOS About 菜单项。[ses_04894c7f7ffe]
- **macOS 开发模式图标可能未加载**: productName 和图标变更需要清除构建缓存（`rm -rf src-tauri/target`）才能生效。Windows 图标圆角由系统控制: Windows 11 自动给图标加圆角遮罩，Windows 10 显示正方形。开发者无需在图标中画圆角。[ses_04894c7f7ffe]

### Tauri/Vue/Monaco/Windows 杂项

- **Vue watch array spread**: `watch(() => [...array])` ensures firing on in-place mutations. Pinia reactive replacement: `obj.name = newName` may not trigger watchers. Use `{ ...obj, name: newName }`。[ses_0fca6436bffe]
- **hasUnsavedTabs 条件**: 原条件 `t.modified && t.path` 跳过新文件，应改为只检查 `t.modified`。Monaco comment italic 光标重叠: 斜体字视觉宽度偏移但光标按正体计算。移除 `fontStyle: 'italic'` 修复。[ses_04894c7f7ffe]
- **Monaco suggest widget 宽度不随字体缩放**: 需非 scoped CSS 设 `min-width: 360px` + `overflow: visible` on `.column-label`。Monaco triggerCharacters 空格陷阱: 空格触发导致每次按空格弹补全。移除后不影响 `.` 触发和 quickSuggestions 自动弹出。不要设 `quickSuggestions: false`。[ses_04894c7f7ffe]
- **Monaco web worker 必须配置**: 未设置 `MonacoEnvironment.getWorkerUrl` 或 `getWorker` 时，web worker fallback 到主线程，可能导致 UI 卡顿。已移除 AMD 方案（需预打包文件在 publicDir），直接使用 ESM import + `?worker` 配置 web worker。更简洁可靠。`xattr -cr` may fail under SIP: Use `sudo xattr -cr` or "Open Anyway" in System Settings. [ses_0438c194affe, ses_08c1fa6b0ffe]
- **Windows `hidden_command()`**: `lib.rs` wraps `CREATE_NO_WINDOW` (0x08000000). All `Command::new()` must use it。GitHub Actions matrix: Edit `os` array in `.github/workflows/release.yml`. `workflow_dispatch` for manual. [ses_08c1fa6b0ffe]
- **Windows Python encoding**: `PYTHONIOENCODING=utf-8` required — Windows uses GBK/CP936。Windows `py` launcher path trap: `where py` returns launcher, not Python. Use `py -3 -c "import sys; print(sys.executable)"`。`tasklist` locale-dependent: Check for PID digits, not English text. [ses_08c1fa6b0ffe]
- **Windows `taskkill /F` EOFError — 已修复（v0.5.7, 2026-09-19）**: `taskkill /F /T` 强关 stdin 管道使 `input()` 抛 EOFError（macOS SIGTERM 无此问题）。最终方案：`run_script_file` 用 wrapper 脚本覆盖 `builtins.input` → `_safe_input` 直接 `stdin.readline()`，EOF/空行/已关闭 → 设 `_stdin_closed` + `raise SystemExit` 终止脚本。用户确认可正常输入。前两次失败：(1) `except EOFError` 在 `_custom_input`（code mode 不用它）；(2) queue-based override（`send_stdin` 写 pipe 不进 queue，会挂起）。坑：EOF 时返回 `""` 会让 `while True: input()` 死循环疯狂打印，必须 SystemExit；wrapper 内 `del` 局部变量会破坏闭包。[ses_f4d61514effe]
- **Code mode vs game mode input 分流**: game mode `start_game()` 经 `exec_globals` 注入 `_custom_input`（bingo_engine.py:2518）；code mode `run_script_file()` 直接跑脚本，`input()` 是 Python 内置。input/EOF 类修复必须针对 code mode wrapper。[ses_f4d61514effe]
- **Tauri 资源打包**: `resources` extracts flat to `resource_dir/portable-python/`。`resolve_engine_env` searches accordingly。`tauri.conf.json` 的 `resources: ["../engine/assets/**/*"]` 会打包所有资源到 `$RESOURCE/_up_/engine/assets/`。`engine/assets/` 是唯一资源目录：sprites/packages/ (14个.bgs), maps/packages/ (.bgm), maps/images/, maps/tiles/, maps/tilesets/, sounds/, ui/。`Child::wait()` over polling: Cross-platform blocking wait, no tasklist needed。resolve_engine_env must include venv Python: Dev needs venv for black. [ses_08c1fa6b0ffe]
- **`> Selected Element` 非代码输出**: 是浏览器扩展（如 Vue DevTools）的输出，无法在代码中移除。[ses_0438c194affe]

### 角色编辑器

- **Sprite config.json 磁盘格式**: 使用 `"segments"` 数组（不是 `"animations"`），每项 `{name, start, end, fps?, loop?}`。TS reader 兼容 `segments` 和 `animations` 两个 key，但写入只用 `segments`。[ses_f4cfba0c5ffe]
- **Sprite path 指向解压目录**: `resource.path` 是解压后的目录路径（如 `~/Projects/default/assets/sprites/皮卡丘`），不是 .bgs 文件。config.json 在 `{path}/config.json`。[ses_f4cfba0c5ffe]
- **ObjectURL 内存泄漏**: useSpriteData.ts 创建 ObjectURL 但从未释放。切换 sprite 时必须 `URL.revokeObjectURL()` 旧 URL。[ses_f4cfba0c5ffe]
- **Auto-save debounce pattern**: 300ms 防抖避免快速编辑时频繁写入。用 `setTimeout` + `clearTimeout`。Legacy PySide6 每次变更直接 `model.save()`。[ses_f4cfba0c5ffe]

### 资源加载

- **`fetch()` 无法读取本地文件系统路径**: Tauri webview 中 `fetch(url)` 只能访问 HTTP URL。sprite resource path 是本地路径（如 `/Users/.../assets/sprites/喷火龙`），必须通过 Tauri `invoke()` 读取。只有 `engine/assets/` 通过 Vite `publicDir` 提供 HTTP 服务。[ses_f4cfba0c5ffe]
- **Sprite 库导入流程**: SpriteLibPage → `invoke('extract_bgs_to_project')` 解压 .bgs 到 `{projectRoot}/assets/sprites/{name}/` → resource store item 的 `path` 指向解压目录。[ses_f4cfba0c5ffe]
- **引擎 Sprite 查找只认解压目录**: `Sprite('名')` 仅在项目 CWD 的 `assets/sprites/<名>/`（config.json+帧PNG）查找；磁盘上没有解压目录 ⇒ `[警告] 角色 '名' 不存在` + `_is_deleted` + `stop()`（bingo_engine.py:168-194）。引擎不读 .bgs zip 也不读 blob URL。[ses_ecb4859d7ffe]
- **控制台 print 输出链路两个坑（2026-10-13 修复）**: ① 游戏模式 stdout 处理（useEngine.ts）把 `read_line` 数据 `split('\n')` 丢弃末尾空串后 `join('\n')`——结尾换行被吃掉，多条 print 挤同一行；必须按 `data.endsWith('\n')` 补回，且中段空行（print()）要保留。② xterm 背后始终跑着一个 zsh；控制台面板自动弹出 → fit()/resize → SIGWINCH → zsh 重画提示符（macOS zsh 默认 `%`）泄漏进控制台。修复：`run()` 启动时统一 `terminalMode='python'`（游戏模式原先漏设），TerminalPanel 的 shell 回调在 python 模式下一律丢弃（原先仅代码模式丢弃）。附带收益：游戏运行中终端 Ctrl+C 能正确触发引擎停止。[ses_ecb4859d7ffe]
- **UploadDrawer 本地上传 .bgs 必须走同一解压流程（根因确认 2026-10-13）**: 抽屉 import 分支曾只 JSZip 读 config.json 名字 + `URL.createObjectURL(zip)` 存 blob URL、不写盘 → 卡片缩略图空白（blob URL 是 zip 非图片）+ 引擎报角色不存在。修复必须复用 `extract_bgs_to_project`，path 指向解压目录——与精灵库导入路径统一。[ses_ecb4859d7ffe]
- **双路径读取**: Sprite 可来自两个来源 — HTTP 服务的 engine assets（via `publicDir`）和本地解压目录（via project dir）。`readBgsFromUrl` 必须同时处理两种情况。[ses_f4cfba0c5ffe]
- **Map 库导入流程**: MapLibraryPage → `invoke('extract_bgm_to_project')` 解压 .bgm 到 `{projectRoot}/assets/maps/{name}/` → resource store item 的 `path` 指向解压目录。[ses_f4cfba0c5ffe]
- **.bgm 文件结构**: zip 包含 `map.json`（tilesets with relative image paths like `images/tileset.png`）、`thumbnail.png`、`images/tileset.png`。[ses_f4cfba0c5ffe]
- **`.bgm` map.json 相对路径 bug**: `.bgm` zip 中 `map.json` 的 tileset `image` 和 layer `resources[].path` 使用相对路径（如 `images/tileset.png`）。`deserializeMap` 不解析这些路径。`MapCanvas.vue` 的 `resolveImagePath` 只处理 `/maps/`、`assets/`、绝对路径三种前缀，裸相对路径走 `convertFileSrc()` 生成无效 URL。修复：在 `loadMapFromProject` 中 `deserializeMap` 后将相对路径解析为绝对路径。`onImportMap` 不受影响（走 `saveMapToProject` 重新序列化）。[ses_f4cfba0c5ffe]
- **GameCanvas 瓦片渲染数据流**: 引擎 stdout JSON → useEngine `CREATE_BATCH` → renderStore.createBatch()（填充 tiles/tileSets ref）→ gameLoop ticker → async syncTiles() → await getTileFrame(tileSetIndex, tileId) → await getTexture(imagePath) → invoke('read_image_as_data_url') → PIXI.Sprite。tileset image_path 含中文字符时 convertFileSrc 失败，必须用 invoke。syncTiles 是 async 函数被同步 ticker 调用，Promise 未 await，靠 tilesSyncing 锁防并发。[ses_f4cfba0c5ffe]
- **Tauri asset protocol URL 中文路径编码失败**: `convertFileSrc()` 生成的 `https://asset.localhost/...` URL 在路径含中文字符时图片加载失败（返回空/pink placeholder）。必须用 `invoke('read_image_as_data_url')` 直接读取本地图片。影响：缩略图加载、地图编辑器瓦片集加载、GameCanvas 运行时渲染。[ses_f4cfba0c5ffe]
- **`path_exists_cmd` 命令名不匹配 (已修复)**: Rust 注册为 `path_exists_cmd`，前端全部调用 `path_exists`（10+ 处），导致 `"Command path_exists not found"` 错误。已统一为 `path_exists`，内部辅助函数用 `path_exists_impl`。[ses_f4cfba0c5ffe]
- **Rust zip crate 0.6.6 解压 .bgm 数据丢失（根因确认+修复）**: `extract_bgm_to_project` 使用 `zip::ZipArchive` 解压 `.bgm` 时，`map.json`（原始 12147 字节）被截断为 227 字节，tilesets 和 tilelayer 全部丢失。Python `zipfile` 解压正常。**zip crate 0.6.6 的 bug**，不升级版本。**修复方案**：在 `loadMapFromProject` 中检测 `tilesets.length === 0` 时，用 `invoke('read_binary')` 读取 .bgm 二进制 → JSZip 解析 → 提取 map.json → 用 `write_file` 覆盖损坏文件。新增 `tryReadMapFromBgm` 和 `resolveRelativePaths` 公共函数。[ses_f4cfba0c5ffe]
- **地图缩略图刷新时机不完整**: `loadAllMapThumbnails` 只在 `resourceTab` watcher、`activeEditorMode` watcher、`onMounted` 时触发。`onMapLibImported` 新增地图后可能未触发 watcher 刷新缩略图。修复：新增 `resourceStore.maps.length` watcher。[ses_f4cfba0c5ffe]

### 运行时渲染

- **GameCanvas 组件渲染条件链**: `editor-page-game` div 需要 `isGameMode=true && activeEditorMode !== 'sprite' && activeEditorMode !== 'map'`。GameCanvas 在此 div 内。从内置库导入资源后 activeEditorMode 会变，`toggleRun()` 已改为运行前自动切回 'code'。GameCanvas template ref 变量名是 `containerRef`（非 `canvasRef`，混淆曾致 onMounted 崩溃）。[ses_f4cfba0c5ffe]
- **CREATE_BATCH JSON 截断 — 根因确认并修复（2026-09-22）**: 根因是 `engine.rs` stdout/stderr 用固定 4096 字节缓冲区 `read()`，大型 JSON（数百瓦片）被截成多个 chunk，前端收不到完整行（日志证据：`len=4096`）。**不是** Tauri 事件 payload 限制。修复：`BufReader` + `read_line()`（run_script 和 run_script_file 均已改）。截至 2026-10-10：Rust 编译通过但**未经用户实测、修复未提交**（工作树 M 状态）；大量 `[Engine]`/`[GameCanvas]` 诊断日志仍留在 useEngine.ts / GameCanvas.vue 待清理。[ses_f4cfba0c5ffe]
- **调试方法论**: 用户明确要求"不要猜测性修复，系统性追踪完整链路，在每个关键节点加日志"。[ses_f4cfba0c5ffe]
- **MapCanvas 渲染时序竞争**: `initPixi` 异步（`await import('pixi.js')` + `app.init()`），`loadMap` 的 revision++ 可能在 `app` 就绪前触发 `renderAllLayers()`（null 时直接 return，之后不再渲染）。`app` 非响应式，watch 无效。修复：`scheduleRender()` 内 `while (!app)` 轮询等待（MapCanvas.vue:1406）。[ses_f4cfba0c5ffe]
- **GameCanvas 精灵渲染细节**: anchor {0.5,0.5}，镜像靠 `scale.x` 负值；x/y 用 `Math.round` 取整（亚像素差）；CREATE 指令不带 hitbox（UPDATE 才带）；引擎发送的 vox/voy 前端全链路未消费。`getTexture()` 手动 `new Image()` + `BufferImageSource` 加载（绕过 PixiJS Assets 缓存），**无 alpha trim**——纹理尺寸=原图尺寸，anchor 0.5 即原图中心，与引擎命中盒 img_w/2 镜像基准一致。[ses_edb115532ffe]
- **scale×scaleX 双乘副作用（独立渲染 bug）**: 引擎 UPDATE 同时发 `scale=base_scale` 和 `scale_x=base_scale*flip`，前端 `displayObj.scale.x = spriteData.scale * spriteData.scaleX` = base_scale²×flip。scale=100% 时无影响；scale≠100% 时视觉尺寸被平方放大（左右对称）。独立于碰撞 bug，可择期修复。[ses_edb115532ffe]

### 碰撞系统

- **碰撞计算 100% 在 Python 引擎**: `engine/bingo_engine.py` 是碰撞唯一实现处（`_setup_hitbox()`、`_get_hitbox_rect()`、`_resolve_collision(axis)`）；Rust（src-tauri）无碰撞代码；前端（useEngine.ts → render.ts hitboxes Map → GameCanvas.vue）仅传输 hitbox 数组并可视化调试，不参与碰撞计算。修碰撞 bug 只需改 bingo_engine.py。[ses_edb115532ffe]
- **碰撞解算为轴分离式**: 各移动入口先 `_resolve_collision("x")` 再 `_resolve_collision("y")`。hitbox 格式 `[left, top, right, bottom]`（`hitbox[3]`=bottom 用于 `_prev_bottom_y` 地面检测）。支持三种碰撞体：瓦片矩形、自定义多边形（`collision_shape.points`）、地图边界。[ses_edb115532ffe]
- **命中盒不处理真实旋转（仅翻转）**: `_get_hitbox_rect()` 只按 `_current_scale_x`(±1) 水平镜像，不读 `self._angle`。默认旋转样式 `"all"` 下 angle=180 是渲染器真实旋转，命中盒不随之镜像 → 内容 bbox 不对称的精灵朝左时视觉可穿墙（左穿右不穿症状）。`set_rotation_mode('left_right')` 路径（angle→flip）命中盒与渲染器一致。[ses_edb115532ffe]
- **主循环物理排序**: 固定步长 1/60s（`run()` :2297-2478）。每物理步：用户 `loop()`（add_x 等在此解一次 X）→ `_handle_physics_collision()` :2056-2098 对所有精灵加重力后**先 Y 后 X** 各解一次 → **X 碰撞每帧双次解算，中间隔 Y 位移**。重力：上升 0.5（jump_cut 2.8）、下落 1.1、vy 钳 ≤10。frame_count 每 ~0.5s 重置（`duration>=0.5` :2451）。[ses_edb115532ffe]

### 其他

- **pnpm PATH gotcha**: `npm install -g pnpm` does NOT add to PATH. Use full path or `npx`. `npm bin -g` removed in npm v11 — use `npm prefix -g`。Engine API design for kids: No import needed, auto-concat args, one-line configs, no blocking in game loops。`__all__` requirement: New functions/classes in `bingo_engine.py` MUST be added to `__all__`。Tauri dev mode: `externalBin`/`resources` can be emptied for dev — `find_system_python()` resolves at runtime。macOS rounded corners: CSS `border-radius` can't do window-level. Use `decorations: true` + `titleBarStyle: "Transparent"` + `hiddenTitle: true`. Windows ignores these。Qt QLayout stretches widgets: When translating Qt to CSS flexbox, use `align-self: stretch` + `padding` on children. Don't assume natural size。Console panel always-render: keep rendered, use internal `collapsed` state. Header bar (26px) stays visible. No `v-show`/`v-if` on wrapper。Sprite data model: `{name, frames[], segments[{name, start, end, fps, loop}]}`. Frames are PNGs in same dir. Three-panel — costume list (100px), canvas, preview (264px)。PNG must be RGBA for Tauri icons: `generate_context!()` panics otherwise. Use `Image.convert('RGBA')`。`.editor-page-full`: Use `flex: 1; min-width: 0; min-height: 0;` in flex parents. Missing `min-width: 0` causes overflow when sibling (side panel) grows. [ses_0fca6436bffe, ses_0f376fc72ffe, ses_04894c7f7ffe, MyIDE MEMORY]

### 引擎教学 API（课件设计参考，2026-10-12 调研确认）

- **学生代码写法**: 推荐 `while True:`（引擎自动转 generator）；`def loop()+run()` 为旧写法仍兼容；多文件项目自动发现合并。`wait(seconds)` 语义特殊——每 N 秒返回一次 True 的节流器（非阻塞 sleep），勿当"等待 N 秒"教。
- **键盘映射（GameCanvas.vue:612-622）**: 方向键 ArrowUp/Down/Left/Right → `"up"/"down"/"left"/"right"`；其余键 → `key.toLowerCase()`。课件可直接教 `key_down("up")`、`key_down("space")`、`key_down("a")`。
- **move() vs add_x/add_y**: `move(d)` 沿当前 angle 方向移动（angle 默认 0=向右）；up/down 用 move 会因 angle 不变而全部水平移动，必须用 `add_x`/`add_y`。课件第2课只教左右 move，第3课引入 add_x/add_y。
- **输入/计时**: `key_down`/`key_pressed`（单帧）、`mouse_down`/`mouse_pressed`/`mouse.x/y`、`Timer(seconds, loop, autostart)`。物理内置重力（上升0.5/下落1.1/vy≤10）；舞台 640×480。
- **内置资源现状**: 14 个 .bgs 角色包；音效仅 3 个（Chill/Coin/Connect）；地图仅 1 个包 `地图1.bgm`；瓦片集 coin/fruit/tileset.png、瓦片 brick/grass.png。课件涉及声音/多地图/多场景的课程需提前扩充资源或控制需求。
- **循环 yield 模型（2026-10-13 修复对齐 Scratch，已验证）**: `start_game` 主循环固定步长 1/60s，每物理步对每个 generator 只调一次 `next(gen)`（bingo_engine.py:2576-2587）。`code_transform._insert_loop_yields` 递归插入 yield：for 每轮结束插（Scratch "重复执行 N 次" 语义，移动逐帧可见）；while（含 while True 与条件 while）体首插（原有时序 + 防 "while not 按键: continue" 单帧死循环）；**不进入** FunctionDef/ClassDef/Lambda（函数体内插 yield 会变 generator 导致调用不执行，旧式 `def loop()+run()` 兼容依赖此规则）。**无 while True 但顶层含 for/while 的脚本也整体包 generator**（`_has_top_level_loop`，script_runner 单文件/多文件两处调用点同判），否则启动循环（如 `for i in range(10): f.x += 5`）在 exec 期同步跑完瞬移——用户实测踩过。副作用：generator 内模块级变量变函数局部——"带顶层循环的文件里定义的函数"跨文件共享会 NameError（纯 defs 文件不转换、保持模块级，主教学模式不受影响）；启动期批量 for 摊到多帧（10 次≈0.17s）。**验证**：`python3 engine/code_transform.py` 自测通过；逐帧模拟确认 for 每帧 +5（fish 测试 10 帧到位）、while True 路径不变、helpers 纯定义文件保持模块级。[ses_ecb4859d7ffe]
- **Transformed-generator 测试方法**: 被 `transform_while_true` 包进 `__game__` 函数的原模块级变量对 `exec` 的 globals 不可见（函数局部作用域），断言状态需通过 `import builtins` 注入的外部观察器（如 `builtins._log.append(...)`）记录，或用类级 observer（如 FakeSprite.instances）。逐帧验证 = 手动循环 `next(gen)`，统计每步新增观察器条目数，勿读取中途变量快照（可能尚未赋值，造成假阴性）。[ses_ecb4859d7ffe]
- **引擎 vs Scratch 速度对比（2026-10-13 用户询问，已答复定调）**: 引擎逻辑帧率 60Hz（_PHYSICS_DT=1/60，每物理步 next(gen) 一次），Scratch 30 FPS。两引擎循环都是"每帧一轮"故动画同样平滑不瞬移，但同样数值（如 move(10)）在我们引擎中速度是 Scratch 的 2 倍（600 vs 300 像素/秒）。舞台 640×480 vs Scratch 480×360 部分缓和——横穿舞台净快约 50%（1.07s vs 1.6s）。对齐 Scratch 手感：课件数值减半（move(10)→move(5)），**不在引擎层加速度系数或改帧率**——课件按我们引擎设计。for 与 while True 速度完全相同（均每帧恰一轮，60 轮/秒）。`f.x += N` 经 set_x→_update_transform 每帧发 UPDATE（带值去重缓存），逐帧 yield 即可见移动（用户 fish 测试实测确认）。[ses_ecb4859d7ffe]

- See MEMORY-tauri-release.md (6 entries) — Tauri updater 签名/endpoint/latest.json 生成 + CI release 工作流（稳定历史知识，2026-10-13 裁剪）

### Discovered
(none)

### Dead ends
(none)
