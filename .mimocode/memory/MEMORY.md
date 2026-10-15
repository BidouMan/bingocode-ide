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
- **每次打包发版必须更新 README.md 更新日志** — 用户 2026-10-15 长期约定：changelog 写在 README「更新日志」章节（非独立 CHANGELOG.md）。格式：`### vX.Y.Z（YYYY-MM-DD）` 分「新增/修复/优化/资源」四类，最新在前；master 未发布内容暂列 `### 未发布（master，待下次发版）`，发版时移入正式版本号。README「功能特性」节随版本同步更新。[ses_ec075fac1ffe]

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
- **世界边界钳制仅重力地图生效（2026-10-15, commit eb99fa3）**: `_resolve_collision` 的 world_bounds "隐形墙"钳制改为 `gravity=True` 才执行。理由：钳制会架空全部边界 API（edge_bounce/is_touch_edge/is_out_side/auto_destroy 子弹销毁）——无重力地图（俯视/太空）自由移动，边界语义交给用户代码；重力地图（平台）边界仍是墙。瓦片/图像碰撞两种模式都保留。[ses_ec075fac1ffe]
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

- See MEMORY-assets-loading.md (20 entries) — 资源加载：sprite/map 库导入解压、`_up_` 过期副本、中文路径图片读取、.bgm zip bug、缩略图刷新；另含 say 气泡三坑与控制台 print 输出链路修复（稳定历史知识，2026-10-15 裁剪）

### 运行时渲染

- **GameCanvas 组件渲染条件链**: `editor-page-game` div 需要 `isGameMode=true && activeEditorMode !== 'sprite' && activeEditorMode !== 'map'`。GameCanvas 在此 div 内。从内置库导入资源后 activeEditorMode 会变，`toggleRun()` 已改为运行前自动切回 'code'。GameCanvas template ref 变量名是 `containerRef`（非 `canvasRef`，混淆曾致 onMounted 崩溃）。[ses_f4cfba0c5ffe]
- **CREATE_BATCH JSON 截断 — 根因确认并修复（2026-09-22）**: 根因是 `engine.rs` stdout/stderr 用固定 4096 字节缓冲区 `read()`，大型 JSON（数百瓦片）被截成多个 chunk，前端收不到完整行（日志证据：`len=4096`）。**不是** Tauri 事件 payload 限制。修复：`BufReader` + `read_line()`（run_script 和 run_script_file 均已改）。截至 2026-10-10：Rust 编译通过但**未经用户实测、修复未提交**（工作树 M 状态）；大量 `[Engine]`/`[GameCanvas]` 诊断日志仍留在 useEngine.ts / GameCanvas.vue 待清理。[ses_f4cfba0c5ffe]
- **调试方法论**: 用户明确要求"不要猜测性修复，系统性追踪完整链路，在每个关键节点加日志"。[ses_f4cfba0c5ffe]
- **MapCanvas 渲染时序竞争**: `initPixi` 异步（`await import('pixi.js')` + `app.init()`），`loadMap` 的 revision++ 可能在 `app` 就绪前触发 `renderAllLayers()`（null 时直接 return，之后不再渲染）。`app` 非响应式，watch 无效。修复：`scheduleRender()` 内 `while (!app)` 轮询等待（MapCanvas.vue:1406）。[ses_f4cfba0c5ffe]
- **GameCanvas 精灵渲染细节**: anchor {0.5,0.5}，镜像靠 `scale.x` 负值；x/y 用 `Math.round` 取整（亚像素差）；CREATE 指令不带 hitbox（UPDATE 才带）；引擎发送的 vox/voy 前端全链路未消费。`getTexture()` 手动 `new Image()` + `BufferImageSource` 加载（绕过 PixiJS Assets 缓存），**无 alpha trim**——纹理尺寸=原图尺寸，anchor 0.5 即原图中心，与引擎命中盒 img_w/2 镜像基准一致。[ses_edb115532ffe]
- **scale×scaleX 双乘副作用 — 已修复（2026-10-15, commit e974e43）**: 原 bug：引擎 UPDATE 同时发 `scale=base_scale` 和 `scale_x=base_scale*flip`，前端 `displayObj.scale.x = scale * scaleX` = base²×flip，scale≠100% 时尺寸被平方。修复后语义：**`scaleX/scaleY`（引擎 `scale_x/scale_y`）是权威最终缩放，前端直接使用，绝不能再乘 scale**（会平方）。GameCanvas syncSprites/syncTiles 均已改为 `displayObj.scale.x = scaleX ?? scale`。顺带修复了地图图像图层同类问题。[ses_ec075fac1ffe]

### 代码模式 Python 打包与 turtle（2026-10-15，已随 v0.5.17~v0.5.19 发布）

- See MEMORY-turtle-packaging.md (6 entries) — 打包必须含 tkinter / pygame-ce / 代码模式执行链 / turtle 保活与 X 关闭三坑 / postlude 测试陷阱 / v0.5.17~v0.5.19 发布状态（稳定历史知识，2026-10-15 裁剪）

### 坐标系与图像生成（2026-10-15）

- **游戏舞台坐标系约定（画图/课件/前端渲染共用）**: 原点 (0,0) 在**舞台左上角**，X 向右 0→640，Y **向下** 0→480（屏幕坐标系，非数学坐标系 Y 向上）。默认精灵出生点 (320,240)=舞台中心；相机中心 `_CAMERA_X=320,_CAMERA_Y=240`。依据：`bingo_engine.py:138-139`（`_x=320,_y=240`）、`world_bounds {left:0,top:0,right:640,bottom:480}`（:497/706/2418 等）、越界检测 `rect[3]<0`=上边缘越过顶边（:897-898）。给学生讲坐标或生成坐标教学图时必须按此约定，勿画成 Y 向上。
- **本机 Pillow 画中文图的字体坑**: `/System/Library/Fonts/PingFang.ttc` **在本机不存在**——脚本若首选它会回退到 `load_default()`（无 CJK 字形），中文全变方框 □。本机实测可用中文字体：`Hiragino Sans GB.ttc`（推荐）、`STHeiti Light.ttc`、`Arial Unicode.ttf`（`/System/Library/Fonts/Supplemental/` 与 `/Library/Fonts/` 两处都有）。Windows 侧用 `C:/Windows/Fonts/msyh.ttc`。生成含中文的图前先 `os.path.exists` + `font.getbbox("舞台坐标")` 实测字形，勿假设系统字体存在。
- **地图编辑器图片加载双通道（2026-10-15 查清并修复）**: ①用户导入：`pick_image_file` → `copyResourceToMapDir` 进项目 `assets/` → 曾用 `convertFileSrc`（中文路径会失败，现全部改走 `read_image_as_data_url`）；②内置 `/maps/` 资源：`read_image_as_data_url` data URL → `new Image()` → PixiJS。带显式 `width`/`height` 的 SVG 经 `new Image()` 可直接作 PixiJS 8 纹理源，无需插件。`engine/assets/maps/images/` 下的 .svg（Blue Sky/Jurassic/Basketball 1）是**死资产**——`地图1.bgm` map.json 只引用 tileset.png，从未被消费，勿当支持先例。[ses_ec075fac1ffe]
- **中文路径 convertFileSrc 加载失败的完整修复面（2026-10-15）**: 不仅缩略图/瓦片集，地图编辑器全部 4 处项目内图片加载点都改走 `read_image_as_data_url`（失败回退 convertFileSrc）：`MainLayout.measureImageSize`、`ResourceListPanel.getResourceUrl`、`MapCanvas.resolveImagePath`、`CollisionEditor.resolveImagePath`。[ses_ec075fac1ffe]
- **地图图片上传有三条独立路径（2026-10-15 查清，勿混淆）**: ①地图编辑器图像图层：`pick_image_file`（Rust 对话框，已加 svg 过滤器）→ `copyResourceToMapDir` 进项目 `assets/` → `read_image_as_data_url`；②内置 `/maps/` 资源：`read_image_as_data_url` data URL；③资源面板 UploadDrawer 地图 tab：浏览器 file input → `arrayBuffer` → `emit('importMapImage')` → `MainLayout.onImportMapImage:949` → `createImageMapProject(fileName,{bytes})`——把图片变成一张**新地图**（地图名=文件名，40×30×16px=640×480 贴舞台）。路径③全程在前端处理字节，不经 Rust 文件对话框。**已修复**：UploadDrawer 地图 tab 的 `isImageFile` 白名单加了 `.svg`（此前 SVG 掉进 else 分支以 blob URL 塞进地图列表 → 空地图）；精灵 tab 不放开（Python 引擎 PIL 只处理位图）。[ses_ec075fac1ffe]
- **PixiJS 超采样：resolution API 整条路已放弃（2026-10-15 两次踩坑定案）**: ①`Texture.from()` 后设 `source.resolution=2` 不回算逻辑宽高（纹理按 1280 显示超框）；②`new PIXI.TextureSource({resolution})` 构造传入也失败——运行时异常被 try/catch 吞掉，**画布全空**（缩略图正常因走 `<img>`）。**最终方案**：`Texture.from(2x canvas)` + 精灵显式缩放补偿 `sprite.scale = logicalW/texture.width`（2x 纹理压回逻辑尺寸，超采样清晰度保留）；瓦片靠 renderTile 的 `sprite.width=tileSize` 自动补偿；GameCanvas 游戏运行时整体回退 1x。[ses_ec075fac1ffe]
- **引擎渲染路径读 map.json 图像缩放必须 camelCase 优先（2026-10-15 修复）**: 编辑器保存 `scaleX/scaleY`（camelCase），引擎渲染路径此前只读 snake_case `scale_x` 靠 fallback 碰巧正确；碰撞路径本就两种都读。定案：`image.get("scaleX", image.get("scale_x", scale))`——渲染/碰撞读取逻辑必须一致。[ses_ec075fac1ffe]
- **SVG 超采样光栅化架构（2026-10-15 定案，借鉴 scratch-render，commit 07738fc）**: `src/utils/svgRasterize.ts` 提供 `SVG_RASTER_SCALE=2` + `isSvgSource()` + `rasterizeSvgImage()`（img → 2x canvas）。**接入点仅 MapCanvas 两处**：`getTileTexture` + `renderImageLayer`——SVG 先光栅化 2x canvas 再 `Texture.from`，配 `sprite.scale = 逻辑尺寸/纹理像素尺寸` 显式补偿（不用 resolution API，见上条）。**GameCanvas 游戏运行时回退 1x**（舞台 1:1 显示，避免帧切割坐标受扰，超采样收益有限）。PNG 永远不走超采样路径原样上传。Scratch 原理：SVGRasterizer 运行时 2x 栅格化 SVG → WebGL 纹理；碰撞用 Silhouette。[ses_ec075fac1ffe]
- **SVG 生成中文图无 Pillow 字体坑**: SVG `<text>` 用系统字体栈（`PingFang SC, Hiragino Sans GB, Microsoft YaHei, sans-serif`），WKWebView/WebView2 直接渲染，绕开 Pillow 字体发现（本机 PingFang.ttc 不存在的坑不适用于 SVG）。本机栅格化验证：`qlmanage -t -s 960 -o <dir> file.svg`。[ses_ec075fac1ffe]
- **内置地图背景库已全量规范化并提交（2026-10-15, commit 9e76ece）**: `engine/assets/maps/images/` 47 文件全部 640×480 + 小写连字符简短命名（如 soccer.png、wall.png、night-city.png、basketball.svg）。20 张 960×720 PNG 已 Lanczos 缩放；3 个非标准 SVG viewport 已归一（根标签 `width="640" height="480" preserveAspectRatio="xMidYMid slice"`——4:3 源零裁切，非 4:3 微裁切填满）。旧文件名无代码引用，资源库页面目录自动扫描。[ses_ec075fac1ffe]
- **SVG 拖拽缩放瞬间放大 bug（2026-10-15, commit 4835dc8）**: SVG 超采样后纹理 2x（1280×960 vs 逻辑 640×480），`renderImageLayer` 创建精灵时有 `sprite.scale = 逻辑尺寸/纹理尺寸` 补偿，但拖拽路径 `updateSelectedImageSprite` 直接 `scale.set(scaleX, scaleY)` 忽略补偿 → 拖拽中每帧精灵按 2x 显示（瞬间大一倍），松手触发整图重渲染又恢复。修复：updateSelectedImageSprite 改用 `(逻辑W×scaleX)÷texture.width` 同款换算。**教训：同一精灵有多条属性更新路径（创建/拖拽/动画）时，缩放补偿逻辑必须在所有路径同步，否则只在非重渲染路径暴露。**[ses_ec075fac1ffe]
- **边界 API 全套修复已提交（2026-10-15, commit eb99fa3）**: ①`edge_bounce`/`is_touch_edge` 检测改"贴边（EPS=0.5 容差）+ 朝该边运动（cos/sin 方向判断，is_touch_edge 为纯查询不需要方向）"——原溢出检测在钳制下恒 false；②`is_out_side` 逻辑本身对，靠解除钳制恢复（子弹出界销毁 auto_destroy :2394/:2613 依赖它）；③**世界边界钳制改为仅 gravity=True 地图生效**（见 Architecture decisions）。无重力地图自由移动，重力地图边界仍是墙；瓦片/图像碰撞不受影响。用户 IDE 实测确认。**注意**：此 commit 被 "[内置资源钩子]" 同时扫入 ~100 个素材 hyphen→underscore 改名（非会话 agent 所做）。[ses_ec075fac1ffe]
- **bingo_engine 直接复现不可 importlib.reload**: 模块 import 时重定向 stdout，reload 重复执行破坏 fd → `OSError: Bad file descriptor`。每个测试场景必须全新 python 进程。[ses_ec075fac1ffe]
- **macOS APFS 大小写不敏感文件系统的批量改名坑**: `os.path.exists("boardwalk.png")` 在只有 `Boardwalk.png` 时返回 True——纯大小写改名会被"目标已存在"误判跳过，`os.rename` 同理无效。必须两步：`rename(old, tmp)` + `rename(tmp, new)`。[ses_ec075fac1ffe]
- **地图编辑器缩放手柄已接网格吸附（2026-10-15, commit c3c5c5b）**: transform handle pointermove 中受控边 mx/my 按 `mapStore.mapData.tileSize` 吸附到最近网格线，与图像拖动吸附共用 `snapToGrid` 开关。四角保持等比约束：先吸附鼠标坐标再按比例调整；未拖动的边保持初始位置。[ses_ec075fac1ffe]
- **导入地图编辑器与舞台对齐的图，原点必须与图片左上角像素级对齐（用户 2026-10-15 硬要求，已按此交付）**: 图片要与 640×480 舞台渲染精确对齐，坐标原点标记须落在图片像素 (0,0)；为线宽留白做的内缩偏移（如 axis_off=18）会造成"原点空隙"。定稿实现：轴线用贴边实心 rect（顶 y=0 h=2、左 x=0 w=2），原点 `circle cx="0" cy="0"` 呈四分之一圆。SVG 带 `width="640" height="480"` 自然尺寸，导入后即与舞台 1:1。[ses_ec075fac1ffe]

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
- See MEMORY-tauri-core.md (6 entries) — Tauri v2 capabilities/窗口关闭/confirm Promise/emit_to/图标缓存（稳定历史知识，2026-10-15 裁剪）
- See MEMORY-collision.md (4 entries) — 碰撞系统架构：计算全在 Python 引擎 / 轴分离解算 / 命中盒仅翻转不旋转 / 主循环物理排序（稳定参考，2026-10-13 裁剪）

- See MEMORY-execution-chain.md (12 entries) — 代码模式执行链/prelude/resolve_engine_env/venv 实测 + turtle import 与窗口调查历史（2026-10-15，部分保活/X 按钮结论已在主文件更正）

### Discovered
(none)

### Dead ends
(none)
