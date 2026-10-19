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
- **每次打包发版必须更新 CHANGELOG.md（发版日志规则）** — 长期约定（2026-10-15 立；changelog 位置后从 README 章节迁移到根目录独立 `CHANGELOG.md`，AGENTS.md ## Rules 已同步为 CHANGELOG.md）。流程：打 tag 发版前在 `CHANGELOG.md`「更新日志」添加版本条目（最新在前），按「新增/修复/优化/资源」分类；未发版 master 改动暂列「未发布」小节，发版时移入正式版本号+日期；同步刷新 README「功能特性」标题版本号与「更新日志」节的「当前最新版本」一句话摘要。[ses_ec075fac1ffe, 落地确认 ses_ebd75331bffe（v0.6.1）]
- **交互控件必须防疯狂点击/连点竞态** — 目标用户是小学生，按钮会被乱点。运行/停止/模式切换等状态控件实现或改动后，必须做并发审查：防抖、幂等、异步取消、孤儿进程防护；连点不得卡死、串状态或误启动。（2026-10-16 用户明确提出）[ses_ebbf7d71bffe]
- **不要随便帮我 commit** — 未经用户明确确认不要自行 commit；等用户说"可以了 commit"或类似指示后再提交。（2026-10-16 用户明确提出）[ses_ebbf7d71bffe]
- **精灵库分类必须显式配置，不能自动扫描目录** — 用户明确要求底层逻辑："我要你设置什么标签，你就在导航栏添加什么标签，然后根据我分类需求，我会告诉你连接到哪个目录"。扫描+过滤方案被否决（将来新目录会被误添加）。[ses_ebbf7d71bffe]
- **角色翻转/旋转穿帮在引擎/前端渲染层解决，不动原素材** — 用户明确："应该不是靠解决原素材来解决吧"。[ses_ebbf7d71bffe]

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
- **专注模式（教师专用复制粘贴开关，2026-10-16 已实现，用户验收"可以了"，随 v0.6.1 发布）**: 防小学生复制粘贴偷懒——设置→引擎设置子菜单「专注模式」+ 右侧小 toggle（名字与形态均用户定：初版「专注模式-开/关」文字被否，改 toggle 模式）。语义：**toggle 开（accent 绿）= 复制粘贴禁用**；localStorage `bingo-ide-focus-mode`（'1'/'0'），fresh install（key null）默认开。弃 Ctrl+Alt+C 快捷键方案（误触后无状态提示）。三层拦截（均在 CodeEditor.vue，游戏/代码模式共用）：Monaco onKeyDown preventDefault+stop 拦 Cmd/Ctrl+C/X/V；editor DOM 上 copy/cut/paste/drop preventDefault（drop 防外部拖文本）；doCut/doCopy/doPaste 早退 + 右键菜单三项 `editor-ctx-disabled`（仅 opacity 0.35，**不改鼠标样式**——用户明确要求）。撤销/重做/注释/运行/格式化保留。子菜单 128→152px（toggle 间距）。开关仅老师知道。[ses_ebd75331bffe]

- **绘制器编辑功能 = 对齐 Scratch 双模式（2026-10-18 用户 Question 拍板）**: 位图模式 = 选区套件（矩形框选、拖动选区像素、复制/粘贴/删除、镜像翻转——无选区时翻转整帧）；矢量模式（paper 对象，原 Stage 2 主体提前）= 对象套件（框选多对象、组合/拆散、图层上下移动、复制粘贴、删除、镜像——paper 原生 Group/sendToBack/scale(-1,1)/hitTest 全内建，不重造）。否决「PS 位图图层模式」（自研图层组面板工程量最大，且与未来矢量形成两套并行概念）与「只做位图选区」（不满足组合/图层点名需求）。**操作类按钮放顶部工具栏**（工业软件 options bar 风格，用户定"一部分也可以放在上面的工具栏"），左栏保留绘制工具；组合/图层按钮在位图模式禁用占位 title「矢量模式下可用」，矢量批点亮。分两批交付：先位图选区，后矢量对象。[ses_ebce1d478ffe]

## Discovered durable knowledge (terminal/console)

- **终端双通道**: 游戏模式 `engine.rs` 子进程（piped），代码模式 `shell.rs` PTY。完全独立 I/O。[ses_09c5077a4ffe]
- **PTY 回映不可抑制**（2次打包确认）: 内核级机制，`stty -echo` 有延迟且与输入混淆。[ses_09c5077a4ffe]
- **`input()` 提示无换行使 `read_line()` 阻塞**: 必须用 `Read::read()` 替代。[ses_09c5077a4ffe, ses_08c1fa6b0ffe]
- **`send_stdin` 追加 `\n` 不适合代码模式**: 需 `send_stdin_data`，前端 `\r` → `\n`。[ses_09c5077a4ffe]
- **输入路由用 `terminalMode`**: `isRunning` 可被提前置 false。用独立 `terminalMode`（`'shell'`/`'python'`）。[ses_09c5077a4ffe]
- **代码模式跳过 shell `runEndTimer`**: 否则 1 秒后误判脚本结束。[ses_09c5077a4ffe]
- **Python `-u` 不解缓冲文本 I/O**: 管道模式必须 `PYTHONUNBUFFERED=1`。[ses_08c1fa6b0ffe]
- **前端 RAF 缓冲延迟**: `handleCodeStdout` 已改为直接写入 xterm.js。[ses_08c1fa6b0ffe]
- **代码模式 input() `__BINGO_WAITING_INPUT__` 标记协议（2026-10-16 修复）**: `_safe_input`（engine.rs wrapper）写 `prompt + '__BINGO_WAITING_INPUT__\n'`（标记充当行终止符让 Rust `read_line` 能推送）；前端 `handleCodeStdout`（terminal.ts）检测标记 → 剥掉标记和尾部 `\r?\n` → 只写 prompt 到 xterm（光标停同一行）→ 设 `waitingForInput = true`；`doWrite` 也需兜底剥标记（防 `pendingWrite` 缓冲泄漏）；用户 Enter 后 `consumeInput()` 重置。同时代码模式 stdout 需设 `consoleVisible = true` 弹出控制台（游戏模式有、代码模式原来漏了）。[ses_ebbf7d71bffe]
- **`createTerminal` 无条件重置 `terminalMode` 导致首次运行 shell `%` 泄漏（2026-10-16 修复）**: `TerminalPanel.vue` `createTerminal()` 原无条件设 `terminalStore.terminalMode = 'shell'`，覆盖 `run()` 设的 `'python'`。首次运行终端新建触发此路径，zsh 输出 `%` 泄漏；第二次运行终端已存在直接 return 不重置。修复：`if (!editorStore.isRunning)` 条件。[ses_ebbf7d71bffe]
- **模式切换 TerminalPanel 生命周期三连坑（2026-10-16 修复）**: (1) `onBeforeUnmount` 只 dispose 不调 `terminalStore.destroy()`，`terminalInstance` 指向已销毁终端；(2) 新组件挂载时 `consoleVisible` 已 true，watch 不触发，`createTerminal()` 不执行；(3) `isRunning` 是游戏/代码共享状态，切换模式不清理会串台。修复：`onBeforeUnmount` 加 `destroy()`；`onMounted` 检查 `props.visible` 主动创建；`watch(isGameMode)` 切换时 `engine.stop()`。[ses_ebbf7d71bffe]
- **游戏模式 `start_game` 主循环永不退出（2026-10-16 修复）**: `while True` 无退出条件，generator 全部结束后仍空转，Python 进程永不退出 → `engine:finished` 不触发 → 运行按钮不复位。修复：generator 全结束且无 say 计时器/移动精灵/播放中动画/碰撞回调时主循环 `return`。[ses_ebbf7d71bffe]
- **SIGTERM 无法中断 macOS 上阻塞在 `readline()` 的 Python（2026-10-16 修复，用户验证通过）**: `stop_script_process` 先发 SIGTERM 后 drop stdin，但 Python 主线程阻塞在 `readline()` C 调用时信号处理延迟。正确顺序：先 `drop(proc.stdin.take())` 关 stdin 管道 → `readline()` 返回空串 → `_safe_input` 主动 `raise SystemExit` → 再 SIGTERM 兜底。已提交 86c7eed。[ses_ebbf7d71bffe]
- **运行/停止按钮连点竞态已修复（2026-10-16，commit 86c7eed + MainLayout TOGGLE_COOLDOWN_MS 随 2812c92 入库）**: `stop()` 同步置 `isRunning=false` 且 fire-and-forget，`_toggling` 立即释放——连点停止第二次点击落入 run 分支；`stop_script` 与 `run_script` Rust mutex 竞争时 stop_script 可能杀掉新进程。修复：`toggleRun` 加 `TOGGLE_COOLDOWN_MS = 400` + `_lastToggleTime` 冷却；运行中点击只 stop 不重启（return）。用户确认"可以了"。单按钮模式可行，不拆分运行/停止按钮。[ses_ebbf7d71bffe]
- **turtle 关窗卡死根因（2026-10-16 修复，commit a16aed5，用户验证通过）**: `engine.rs` wrapper 的 turtle 收尾代码（WM_DELETE_WINDOW 注册 + keepalive + mainloop）位于用户脚本 `{}` 之后。用户代码 `turtle.done()`/`mainloop()` 阻塞 → 收尾代码永不执行 → `WM_DELETE_WINDOW` 从未注册 → 点 X 走 Tk 默认销毁窗口但 Python 进程不退出 → 窗口卡死。正确做法：monkey-patch `builtins.__import__` 拦截 `import turtle`，替换 `turtle.mainloop`/`turtle.done` 为先注册 `WM_DELETE_WINDOW` 再调用原函数的包装器。终止用 `os._exit(0)`（Tk 回调中 `sys.exit()` 可能被吞）。已提交 a16aed5，用户确认"turtle目前运行都没问题"。[ses_ebbf7d71bffe]
- **精灵库分类显式配置（2026-10-16, commit a74eefa）**: `src/stores/spriteLib.ts` 导出 `SPRITE_CATEGORIES: Array<{dir, label}>` 替代自动目录扫描；`CATEGORY_LABELS` 已删除。`SpriteLibPage.vue` 的 `categoryLabel()` 从 `SPRITE_CATEGORIES.find(c => c.dir === cat)?.label` 取标签。新增分类只需在数组加一行 `{dir, label}` 并创建 `engine/assets/sprites/<dir>/{packages,images}/` 目录。`list_dir` Rust 实现两平台都正确返回 `/` 后缀目录名——Windows packages 多标签根因是 Tauri 资源拷贝在 Windows 产生多余顶层 `sprites/packages` 目录。[ses_ebbf7d71bffe]
- **碰撞框旋转感知（2026-10-16, commit 7838f40）**: `bingo_engine.py` `_get_hitbox_rect()` 原只处理 flip_x 水平镜像不处理旋转，角色旋转 180° 时碰撞框不跟随导致穿帮。修复：bbox 四角逐角点做 镜像→旋转→缩放→平移 后取 AABB；`rotation_style == "left_right"/"none"` 时 `effective_angle = 0`（镜像由 flip_x 处理）；帧级缓存增加 `_cached_rect_angle` 比对。同函数覆盖碰撞框显示和 `is_touch` 检测。[ses_ebbf7d71bffe]
- **角色翻转围绕内容重心渲染（2026-10-16 修复，用户验证"上下反转也可以了"）**: fish_2 等序列帧素材非透明内容偏下方（保证动画站在地面）；PixiJS `anchor={0.5,0.5}` 是图片几何中心，翻转围绕整图中心导致视觉跳位。最终方案：**anchor 保持 {0.5,0.5}（引擎 _x/_y 语义不变），pivot 设为 {x:vox, y:voy}**（内容重心偏移像素）。前端链路：SpriteData 加 vox/voy → createSprite 初始化 → useEngine CREATE/UPDATE 传参 → GameCanvas 设 displayObj.pivot.x/y + 脏检查 propsKey 含 pivotX/pivotY。备选 anchor.x = 0.5 + vox/texW 方案被弃（需纹理尺寸、改 _x/_y 语义）。[ses_ebbf7d71bffe]
- **PixiJS pivot 变换公式（2026-10-16，碰撞框修复关键）**: `world = position + R * S * (local - pivot)`。pivot 在 (local - pivot) 中减**一次**，绝不在最终平移时加回。引擎 `_get_hitbox_rect` 必须与此一致：bbox 四角先减 vox/voy（相对内容重心）→ flip → rotate → scale → `world = center + (rx,ry)*s`（**不加 vox/voy 回偏移**）。首次碰撞框修复尝试因 corners 减 vox/voy 后平移又加回（双计）而失败（用户确认"修复失败"）。[ses_ebbf7d71bffe]
- **v0.6.2 发版完成（2026-10-16, commit 6a0fe7f, tag v0.6.2 已推送）**: 包含 input() 修复、运行按钮复位、turtle 关窗、碰撞旋转穿帮、Windows 精灵库分类、IMK 噪音过滤。[ses_ebbf7d71bffe]

## compose-preferences

- execution-style: subagent

## Discovered durable knowledge
_Cross-task facts that survive across sessions._

### Tauri/Vue/Monaco/Windows 杂项

- **内置素材风格 = 插画为主，非像素画（2026-10-16 Pillow 实测）**: characters/images 24 张（boat 128×128、cannon 500×500、car 236×167，>256px 占 15）、items/images 21 张全 108×108、maps/images 43 张全 640×480（与逻辑分辨率 1:1，渲染模式几乎无差别）；真像素画仅 maps/tiles（grass 16×16、brick 32×32）与 tilesets 共 2-3 张。锐利边缘比/半透明比测量确认角色与道具是卡通插画。推论：PixiJS 渲染模式默认 **smooth 更合适**（道具/角色常缩小显示，nearest 对插画 stair-stepping）；pixelated 供像素画项目手动切换。若未来内置库扩充像素画素材包，重新评估默认值。用户已拍板 master 默认保持 smooth（2026-10-16 撤回临时 pixelated 改动，未入库）。[ses_ebd75331bffe]
- **image-rendering: pixelated 在 WKWebView 需绕开合成图层路径（2026-10-18 绘制页实测）**: 恒等 `transform: scale(1)` 与 `will-change: transform` 会把元素提升为合成图层，WebKit 可能用平滑缩放覆盖 pixelated（观感=设了像素渲染"貌似还是 smooth"）。对策三件套：100% 缩放时不写 transform、去 will-change、CSS 类多重声明渐进回退（`-moz-crisp-edges; crisp-edges; pixelated`）。位图编辑画布用 1:1 逻辑分辨率（canvas 属性=逻辑尺寸）+ pixelated 即 Scratch 同款像素网格（绘制页曾试 HiDPI backing×dpr 后回退——输出尺寸会随机器变化且像素网格变设备级）。[ses_ebce1d478ffe]

- See MEMORY-tauri-windows-misc.md (8 entries) — .bc 共享工作目录 unpack 语义 / 内置资源提交钩子（含 2812c92 二次实例）/ 发版流程 / Windows hidden_command·编码·taskkill / input 分流 / Tauri 资源打包 / Selected Element（稳定历史知识，2026-10-18 裁剪）

### 角色编辑器

- See MEMORY-sprite-editor-core.md (4 entries) — config.json segments 磁盘格式 / resource.path 指向解压目录 / ObjectURL 释放 / 300ms auto-save 防抖（稳定历史知识，2026-10-18 裁剪）

- See MEMORY-assets-loading.md (20 entries) — 资源加载：sprite/map 库导入解压、`_up_` 过期副本、中文路径图片读取、.bgm zip bug、缩略图刷新；另含 say 气泡三坑与控制台 print 输出链路修复（稳定历史知识，2026-10-15 裁剪）


### 代码模式 Python 打包与 turtle（2026-10-15，已随 v0.5.17~v0.5.19 发布）

- See MEMORY-turtle-packaging.md (6 entries) — 打包必须含 tkinter / pygame-ce / 代码模式执行链 / turtle 保活与 X 关闭三坑 / postlude 测试陷阱 / v0.5.17~v0.5.19 发布状态（稳定历史知识，2026-10-15 裁剪）

### 其他

- **pnpm workspace `-w` flag**: 项目根 `pnpm-workspace.yaml` 含 `packages: ["."]`，任何 `pnpm add <dep>` 必须带 `-w`（否则 ERR_PNPM_ADDING_TO_ROOT）。[ses_ebce1d478ffe]
- **useFileDialog `multiple` 只返回第一个文件**: `openFile(accept, true)` 的 onChange 取 `input.files?.[0]`——多选需自建 input；纯图片场景 File 本身就是 Blob，无需 FileReader 读字节。[ses_ebce1d478ffe]
- See MEMORY-legacy-dev-tips.md (9 entries) — pnpm PATH / 引擎 API 设计与 __all__ / Tauri dev mode / macOS 圆角窗口 / Qt→CSS / 控制台常驻 / 精灵数据模型 / Tauri 图标 RGBA / .editor-page-full flex（历史稳定提示，2026-10-18 裁剪）

### 引擎教学 API（课件设计参考）

- See MEMORY-teaching-api.md (8 entries) — 学生代码写法 / 键盘映射 / move vs add_x / 输入计时 / 内置资源现状 / 循环 yield 模型 / generator 测试方法 / 引擎 vs Scratch 速度对比（稳定历史知识，2026-10-16 裁剪）

- See MEMORY-tauri-release.md (6 entries) — Tauri updater 签名/endpoint/latest.json 生成 + CI release 工作流（稳定历史知识，2026-10-13 裁剪）
- See MEMORY-tauri-core.md (6 entries) — Tauri v2 capabilities/窗口关闭/confirm Promise/emit_to/图标缓存（稳定历史知识，2026-10-15 裁剪）
- See MEMORY-collision.md (4 entries) — 碰撞系统架构：计算全在 Python 引擎 / 轴分离解算 / 命中盒仅翻转不旋转 / 主循环物理排序（稳定参考，2026-10-13 裁剪）

- See MEMORY-execution-chain.md (12 entries) — 代码模式执行链/prelude/resolve_engine_env/venv 实测 + turtle import 与窗口调查历史（2026-10-15，部分保活/X 按钮结论已在主文件更正）
- See MEMORY-graphics-maps.md (17 entries) — 坐标系约定 / Pillow·SVG 中文字体 / 地图图片加载与上传路径 / PixiJS 超采样与 SVG 光栅化 / 内置背景库规范化 / 边界 API 修复 / 缩放手柄吸附（稳定历史知识，2026-10-16 裁剪）
- See MEMORY-resource-naming.md (5 entries) — 资源创建/重命名入口全景图 / nextSequentialName / .bgm 内嵌路径陷阱 / vue-tsc 基线 / migrateSpriteDir 闭环（稳定历史知识，2026-10-18 裁剪）
- See MEMORY-paint-editor.md (6 entries) — 绘制角色编辑器：Stage 0/1 已交付并经三轮实测迭代收敛，T5 修复已提交（ea581a0）；尺寸规格（640×480/手动2048/一键裁切）已验收；多帧绘制+统一 .bsf 保存管线已落码；造型列表「添加序列帧」抽屉三来源（绘制/内置/本地）已实现并经用户测试；交互重设计（绘制页载入全部帧的整角色编辑模型、双击帧进绘制页、抽屉大圆按钮居中）已验收并提交（dbad54a）；**位图选区变换框全套已提交（2026-10-19, be5b3bf）**——锚定缩放/Shift 等比/穿越翻转/复制粘贴删除镜像/顶栏操作组，SVG overlay 硬约束根治烙印/锯齿，配色 indigo（SEL/SEL_DEEP 常量用户自改）；**下一步：矢量对象批（Stage 2 主体提前，paper 组合/图层/多选）**；独立页宿主架构（用户批准）、Paper.js 选型、位图引擎细节（2026-10-19 更新）
- See MEMORY-editor-quirks.md (5 entries) — Monaco/Vue 编辑器渲染与行为杂项：watch 触发、hasUnsavedTabs、suggest 布局、web worker、Monarch 高亮（稳定历史知识，2026-10-18 裁剪）

### 角色资源格式（.bgs → .bsf）

- See MEMORY-bsf-format.md (23 entries) — .bsf v2 格式规范与迁移决策 / BSF 集成实现史（commit 2812c92）/ crates.io 卡死与引擎方法级单测法 / 消费链路与 UPDATE_BATCH·GameCanvas 双实例·加载覆盖层·批量读图修复 / 动画速度链路与 FPS UI / .bgs 去留策略 / 绘制器打包契约·画板规格·追加回写双管线·位图选区 SVG overlay 架构（2026-10-18 裁剪）

- See MEMORY-runtime-rendering.md (6 entries) — GameCanvas 渲染条件链/精灵渲染细节、CREATE_BATCH 4096 截断修复、MapCanvas 时序竞争、scale×scaleX 双乘语义、调试方法论（稳定历史知识，2026-10-18 裁剪）

### Discovered
(none)

### Dead ends
(none)
