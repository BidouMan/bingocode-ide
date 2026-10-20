Topic: BingoCodeIDE 项目记忆 — Tauri v2 + Vue 3 + PixiJS 游戏IDE，Python引擎子进程，服务60节Python游戏启蒙课

# Project memory
_Durable project-level knowledge. Persists across all sessions in this project. Edit only content under italic instructions._

## Project context
_BingoCodeIDE_ — Tauri v2 + Vue 3 + PixiJS desktop IDE for game development with a Python engine (`bingo_engine.py`). Refactored from a PySide6 version (see sibling project MyIDE for legacy knowledge). Two modes: game mode (visual editors + code + preview) and IDE mode (Python editing + run/stop). Engine runs in subprocess, communicates via JSON over stdout/stdin.

## Rules
_Hard constraints from user that every session must respect._

- UI 规格以 AGENTS.md 末尾 QSS color reference + 现有 Vue 组件为准；原 PySide6 参考（legacy/）已于 2026-10-20 归档删除，如需查阅从 `~/BingoCodeIDE-legacy-pyside6-archive-20261020.tar.gz` 解压临时目录读，不恢复回仓库
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
- **前端图标唯一存放位置 = `src/assets/icons/`，不留双副本（2026-10-20 用户明确"务必把文件夹统一 不要在目录里弄得乱七八糟的"）** — 前端组件一律 `import iconX from '../../assets/icons/xxx.svg'`。曾踩坑：图标双副本（legacy/src 各一份），用户改 legacy 里粘贴.svg、前端加载的 src 旧副本纹丝不动（"替换了图标重启还是旧的"）。**根治（同日）：`legacy/`（老 PySide6 工程，.gitignore 整目录忽略、前端零引用）已安全移除**——全量归档到项目外 `~/BingoCodeIDE-legacy-pyside6-archive-20261020.tar.gz`（14M，排除 .venv）后删除；AGENTS.md 已同步更新（旧「Reference Original First」节改为归档说明 + 新增「素材目录约定」节）。现无双副本可能，改图标只改 src 一处。[ses_ffe5ea6b2a993ffeHddz87eJYy]

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

- **矢量填充=Scratch fill-tool 同款（2026-10-20 落码并提交 `1cacfe3`，用户实测通过"功能实现了"）**: 矢量油漆桶为 **recolor 模型**——点击形状换填充/描边色；**无区域洪水填充，点空区域=无操作是 Scratch 矢量语义**（位图模式才有 flood fill；用户报"无效"后按 scratch-paint `src/helper/tools/fill-tool.js` 规格重写并经用户验收）。架构（usePaperScope.ts）：`fillTargetAt` = stock hitTest（match 只认 Path/CompoundPath/PointText，位图代理穿透）+ **迭代显式栈 DFS 盲区扫描**（stock 三盲区：无填充闭合/近闭合路径内部、复合路径的洞、复合描边）按同一序表裁决 z 层（盲区 idx<rawIdx 胜、同项偏 raw）；复合作命中单元不下钻。**悬停即预览、按下压栈、松手提交**（Scratch updateFillPreview/onMouseUp 模型）；`snapshotForGesture` 头部 restore=快照/undo/redo/帧导出统一收口（另补 copySelection/watch 工具与模式/onPointerLeave/importFrame/clearAllForBake）；**fillPushed 延迟压栈**实现"按下空白→拖到目标→松手提交"且一段手势单步撤销；同色点按/拖离→popHistory 防空步；洞覆盖片=clone+clockwise+expandBy(0.1)+insertAbove+**prepend 父 getGlobalMatrix()**（必须——我们 item.transform 保留矩阵，Scratch 无此情况勿照抄省略）；同色无描边提交时 reduce 洞消融进父。[ses_ebce1d478ffe]

- **Vue store watch 三陷阱（2026-10-20 揘边 UI 迭代取证，跨任务耐久）**: ①**同 tick 值往返不触发**——`setSelection` 同步块内 count 1→0→1，watch 新旧值相同（都是 1）直接不触发 → 依赖"选中变化"的同步必须挂在必经函数（如 syncVectorSelBox）内联调用，不能靠 watch 计数器；②**同值写入不触发**——`store.x = true` 当已是 true 时 watch 不触发 → 勾选/开关类信号需配 tick 计数器（`xxxTick++`）做边沿强制，watch getter 写成数组 `[value, tick]`；③**多 watcher 同 flush 按注册序执行**，A watcher 内改 store 会把受影响 watcher 追加到本 flush 尾部 → 抑制窗口不能立即解锁，须 `nextTick(() => lock=false)`（nextTick 回调在 flush 之后）。[ses_ebce1d478ffe]

- **绘制编辑器文字工具（2026-10-20 用户拍板+全链路落码，两轮 bug 修复后待 dev 验收）**: 用户三问确认——完整 HarmonyOS Sans SC 8.2MB 直接打包（`engine/assets/fonts/`，publicDir `/fonts/` 服务）、矢量+位图都做、默认字号 40 无字号 UI（靠缩放手柄）。规格对齐 scratch-paint `src/helper/tools/text-tool.js`（TEXT_EDIT/SELECT 双态、fontSize 40、leading 46.15、空文字删除、双击 250ms 重编辑）。矢量=paper.PointText + store.textEdit overlay；结束编辑自动 setSelection+setTool('select') 复用变换框；位图=textarea 绝对定位+commit 时 ctx.fillText 逐行栅格化（一次性）。加载入口 `paintFont.ts` ensurePaintFont。**已改**：paint.ts textEdit state（含 width/height 动态尺寸）、usePaperScope 文字工具全段+expose、useBitmapCanvas commitBitmapText+measureBitmapText+expose、tintTargets 纳 PointText、PaintArtboard textarea 模板/CSS/textEditStyle/onStageKeydown Esc/onMounted 预加载/导出撤销清空增删帧前 commitTextEdit。**textarea 定位**：left/top=PointText 内容左上角项目坐标 + CSS matrix 仅线性部分 (a,b,c,d,0,0)（不乘 view.matrix）。**动态边框**：矢量 internalBounds / 位图 measureText 驱动 width/height；空文字仅光标位。**IME**：compositionstart/end 门控、组词中不上屏、textarea 非受控（挂载写一次初值）。**焦点**：编辑态 stage 不 focusStage、text 工具不 setPointerCapture、nextTick+rAF 聚焦；`.paint-stage:focus outline:none` 去深蓝焦点环。**光标色** caret-color #2a2d33 固定不吃字体色。**收口禁用 stage mousedown**（pointerdown 新建会话会被冒泡 mousedown 误杀）；撤销 push 在 beginTextTool 创建/重编辑**前**（栈顶=改动前）；endTextEdit(switchToSelect) 分手势结束（true）与 forceEnd（false，不覆盖用户工具）。paint-editor 相关 vue-tsc 已清零；**dev 验收未完成**（用户已能输入，两轮 bug 修复待回报）。[ses_ffe5ea7fb3831ffe3TChf2A9H3]

## Discovered durable knowledge (terminal/console)

- **legacy/ 目录已安全移除并归档（2026-10-20）** — `legacy/`（老 PySide6 工程：main.py/ui/*.py/requirements.txt，1.3G 中 1.2G 为可重建的 .venv）整目录在 .gitignore、git 零跟踪、前端零代码引用。用户授权"在安全的情况下移除"后执行：图标全量同步进 `src/assets/icons/`（误同步的 undo/redo 用 `git checkout --` 回退）→ 归档 `~/BingoCodeIDE-legacy-pyside6-archive-20261020.tar.gz`（14M，196 文件，排除 .venv/__pycache__/.DS_Store，tar -tzf 校验关键文件 ✓）→ `rm -rf legacy/` → AGENTS.md 更新（移除指向 legacy 的「Reference Original First」节，改为归档说明 + 素材目录约定）。**归档包是 PySide6 原版参考的唯一副本，勿删**；需要查阅原始布局/交互时从归档解压临时目录阅读，不恢复回仓库。原 .gitignore `legacy/` 条目可保留（无害）。[ses_ffe5ea6b2a993ffeHddz87eJYy]
- **矢量模式图标已全量替换并提交（2026-10-20，commit 727c009）** — PaintToolbar（select→选择箭头/eraser→清空/fill→填充_fill/text→文字_text/line→直线工具/rect→矩形_rectangle/ellipse→圆形_round/eyedropper→取色器/clear→清空画布；brush、reshape 未动）、PaintTopBar（crop→裁切画板/paste→粘贴/flipH→水平翻转/flipV→垂直翻转/group→组合/ungroup→取消组合/curve→曲线/straight→折线）、PaintColorPanel（吸管→取色器，fill+stroke 两按钮共用 import）。命名差异：用户清单"裁切换班.svg"=实际 `裁切画板.svg`、"左右翻转.svg"=实际 `水平翻转.svg`。该 commit 同时含塑形 toggle、vectorCanUngroup、顶栏三小细节、AGENTS.md legacy 归档口径。`npx vite build` ✓。[ses_ffe5ea6b2a993ffeHddz87eJYy]
- **塑形曲线/折线 = 互斥 toggle（2026-10-20 用户定，已验收并随 727c009 提交）** — PaintTopBar 塑形工具专属组：激活侧由 `store.reshapeHasPointed` 推导（选中锚点含手柄=曲线态激活；无手柄/未选=折线态默认激活）；`icon-btn-active` 样式复用 `--bg-active`；激活侧点击=引擎侧安全空操作（curveSelectedPoints/pointSelectedPoints 对已是目标形态的点跳过+popHistory，零撤销副作用），不做 disabled；未激活侧仅在有可转换锚点时可点（curveDisabled = !hasUncurved && !hasPointed）。tooltip 状态化：激活侧「曲线（当前）」/「折线（当前）」。[ses_ffe5ea6b2a993ffeHddz87eJYy]
- **位图模式微调 + v-tooltip 位置扩展（2026-10-20 用户逐条指示，已随 0ccf29f 提交）** — ①位图左栏顺序定稿 `select→brush→eraser→fill→text→line→rect→ellipse→eyedropper`（fill 橡皮下、text 填充下，用户两轮收敛）；②位图 select=框选语义配专用图标：`toolIcon(key)` 按模式切（bitmap→`选取工具.svg` 虚线框选、vector→`选择箭头.svg` 点选）；③位图顶栏隐藏矢量四按钮：组合/解组/上移/下移+首 divider 包 `<template v-if="isVector()">`（用户"不应该有"，非 disabled 占位），flip 经第二 divider 保留；④v-tooltip 指令扩展对象值 `v-tooltip="{ text, position: 'top'|'bottom'|'left'|'right' }"`（parseTooltipValue+positionTooltip 四向+视口钳制补 top<8；updated 钩子比较解析后 text 防对象 oldValue 误判；旧字符串用法不变），PaintToolbar 侧栏 tips 全部 `tipRight()`=right 且偏移用户定 **+4px**（8px 被嫌"远/靠右"）。[ses_ffe5ea6b2a993ffeHddz87eJYy]
- **顶栏 ungroup 激活条件=选中含 Group（2026-10-20 用户指正，已实现并随 727c009 提交）** — store 新增 `vectorCanUngroup`（paint.ts ref+reset+导出）；`syncVectorSelBox()` 函数开头（reshape/空选分支之前）内联计算 `!!scope && Array.from(selected).some(it => it instanceof scope!.Group)`；onBeforeUnmount 复位 false。ungroup 按钮 `:disabled="!isVector() || !store.vectorCanUngroup"`。所有选中变更路径都汇聚 syncVectorSelBox → 单点覆盖。组合按钮 count≥2 逻辑保留（用户确认正确）。**不可用 watch(vectorSelectedCount)**（同 tick 1→0→1 不触发陷阱，见 Vue watch 三陷阱）。[ses_ffe5ea6b2a993ffeHddz87eJYy]
- **拾色放大镜（Scratch 同款）已提交（2026-10-20, 0ccf29f，用户验收通过）** — 规格：PaintArtboard.vue 圆形镜片 92px 屏幕恒定、10 倍最近邻放大、**镜中心=光标位置（LENS_OFFSET 已删——首版偏右下 34px 被用户报"拾取的位置和准星位置不一样"，去 offset 所见即所得）**、双环+棋盘底+中心十字准心、dpr 物理像素；激活时 `buildPickComposite` 缓存位图⊕矢量合成图（pointermove 只 drawImage 小窗防矢量重渲染）；.picking 时 cursor:none 由准心接管。**v-if 死锁修复模式（首版 bug）**：镜片 canvas 由 `v-if="… && pickLensPos"` 控制、绘制函数开头又检查 ref null 提前 return → 永不挂载。修复：**先写驱动 v-if 的响应式状态再取 ref，ref 未就绪用 nextTick 补画**（拆出 paintPickLens 纯绘制函数）。**setTool 联动**：切到/离开 eyedropper 时联动 eyedropperActive（工具栏取色真正激活会话）。**取色会话语义（用户否决连续取色后定稿）**：**一次性取色**——`toolBeforePick` 记录进拾色前工具、`endEyedropper()` 统一收口（取色完成/Esc/面板取消/错误兜底），工具栏取色结束回退到取色前工具，面板吸管不动 activeTool。两引擎（usePaperScope L3040 / useBitmapCanvas L1249）pointerdown 放行冒泡、点击由 PaintArtboard onStagePointerDownForPick 从合成缓存 getImageData 消费。**CSS 同特异性顺序坑（顶栏批）**：`.icon-close{14px}` 写在 `.icon-sm{18px}` 之前被覆盖（同类名规则后定义者胜）——修复=移到其后或 `.icon-sm.icon-close` 提特异性。**保存按钮配色约束**：亮强调绿 rgb(91,251,132) 底配深色「不和谐」、配白色「更看不清」→ 定稿中深绿 #2b8a48 底+纯白前景+整按钮 `filter: brightness(1.15)`，hover #33a056。[ses_ffe5ea6b2a993ffeHddz87eJYy]
- **顶栏布局最终定稿 + 低分屏挤压分析（2026-10-20，commits 370080f + d95c3e9，master）** — 布局：左 mode-switch 顶头（topbar padding-left 4px）；zoom-align 组（撤销/重做/缩放）**绝对定位 right:200px**——放大按钮右缘压 PaintColorPanel 左分割线（用户验收"对齐了"）；topbar-actions **绝对定位 right:10px width:190px**（=200px 面板宽−10px 边距）内含关闭+保存 **flex:1 等宽**。**padding 左48/右200 整列对齐方案被用户否决**（"你把两边都空出来了 反而不好了"——顶栏内容要顶到屏幕边缘，只把右侧簇与面板列对齐）。保存按钮定稿 #2b8a48 底+纯白+整按钮 `filter: brightness(1.15)`（hover #33a056）；关闭=`关闭.svg` 13px（`.icon-close` 移到 `.icon-sm` 之后修同特异性顺序覆盖）；`mode-btn-active`=`--accent` 绿底+#16201a 粗体（用户定激活态变绿；小面积文字块吃亮绿底深字，与保存按钮压暗路线区分）；窄窗防竖排=文字按钮 `white-space:nowrap` + mode-switch `flex-shrink:0`（启动非全屏时矢量/位图/保存曾逐字竖排——flex 收缩 CJK 逐字换行）。**挤压风险分析（用户提问，分析已交付待拍板）**：tauri `minWidth:960`；矢量在流内容 ~720px + 右侧绝对簇 380px → 逻辑宽 **< ~1115px 操作组右端被 zoom-align/actions 覆盖**；位图 ~905px 阈值 960 可放下；**1366×768 @ 125% 缩放 = 1093px 正落重叠区**（学生本常见）。**推荐=优雅降级**（否决悬浮：遮画布+选中态按钮浮画布语义乱；否决滚动：学生可发现性差）：①尺寸输入开画后折叠成纯文本（禁用态占 ~150px 无意义）②< ~1150px 紧凑模式按频率隐藏 图层上下移→组合/解组。待用户选型后实施。[ses_ffe5ea6b2a993ffeHddz87eJYy]
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

- **paper.js 命中/填充 API 事实（0.12.18 源码+Node 实测，2026-10-20 矢量填充批）**: ①`project.hitTest` 的 **point=项目坐标**（Item._hitTest 只做 item 局部矩阵逆变换，view.matrix 仅参与 stroke/tolerance 缩放）→ clientToArtboard 直接喂；fill 命中要求 `style.hasFill()`（无填充闭合路径内部=MISS）；②**CompoundPath._hitTestChildren 对子级强制 fill:false** → 复合只在整体层回 fill 命中、子级 stroke 命中经验性 null → 复合描边/洞（XOR contains=false）/未填充内部全是 stock 盲区（fork @scratch/paper 的 `hitUnfilledPaths/hitUnstrokedPaths` stock 不存在，grep dist 零命中）；③`getNearestLocation`/`contains` 输入输出皆项目坐标且穿透父级变换链，`loc.distance`=查询点到最近点距离；④`CompoundPath.reduce` 单子→Path、≥2 子→自身（幂等）；⑤clone→insertAbove→`transform(parent.getGlobalMatrix())` = 世界系 prepend（**getGlobalMatrix d.ts 未收录**需窄断言）；⑥`Color.toCSS` d.ts 要求参数（用 `toCSS(false)` 比 rgba 串）；hitTest options d.ts 类型 `object`（match/segments 等随意传）；⑦开放近闭合路径 contains 隐式闭合（首尾距<8 可当闭合填）。**scratch-paint 源码抓取**：GitHub API `contents?ref=develop` 或 `cdn.jsdelivr.net/gh/scratchfoundation/scratch-paint@develop/...`（raw.githubusercontent 超时；fill 规格在 `src/helper/tools/fill-tool.js`，`src/tools` 是 404）。⑧TS 闭包坑：`let x=null` 闭包内赋值、闭包外读会收窄成 `never`（TS2339）→ 改显式栈迭代。⑨`project.hitTestAll` 返回序=自顶向下（hitTestChildren 遍历 children l-1→0、filter 依次 push 到 options.all）→ `hits[0]` 即最顶，无需 sortItemsByZIndex。⑩**stock d.ts 命名 ≠ @scratch/paper fork API**（2026-10-20 reshape 落码 vue-tsc 全量核实）：`Segment.previous/next/curve` 是**属性**（fork 的 getPrevious()/getNext()/getCurve() stock 无）；**加点=`Curve.divideAt(location)`→返回右段、新锚点=`nc.segment1`**（`PathItem.divideAt` stock 不存在）；`isCollinear`（双 l，d.ts 规范名，运行时有 isColinear 别名但 d.ts 不收）；`PathItem.segments` d.ts 未收录→cast `(item as paper.Path).segments`（运行时 CP 同可用）；`Item.removed` 不存在→用 `path.parent` 真值判 detach；hitTest options d.ts 类型 `object`→match 回调参数须显式标 `(hr: paper.HitResult)`；`segment.smooth()` ✓、`seg.path.localToGlobal/globalToLocal` ✓（项目坐标穿透父级变换链）；`Curve.getLocationAt`=弧长 offset、`getLocationAtTime`=参数时间；`segment.smooth()` 不给开放路径端点设单侧柄；handleIn/handleOut 赋值用零向量 (0,0) 替代 null（防后续 .length 崩）。⑪`PathItem.getPathData(matrix?)` 运行时方法 **d.ts 未收录**（需窄 cast `(item as unknown as {getPathData:(m:paper.Matrix)=>string})`），传 **`item.globalMatrix`（d.ts 有，readonly）** 得项目坐标 path data；复合路径子路径间用小写 `m`（SVG 合法）；本项目 applyMatrix=true 变换已烘进 segments、matrix 恒 identity → 无参与带 globalMatrix 同值（Node 实测），带参幂等安全——SVG overlay 轮廓线即用此法。[ses_ebce1d478ffe]

- **scratch-paint reshape/塑形规格（2026-10-20 取证完毕，全量通读）**: 工具三件套在 `src/helper/selection-tools/`——`reshape-tool.js`（4 子模式状态机 FILL/POINT/HANDLE/SELECTION_BOX，命中 4 级优先：选中段>手柄>选中曲线>fill/stroke，TOLERANCE=(5.25+1)/zoom，双击 250ms，方向键 nudge 1/zoom）、`point-tool.js`（段选中塌缩语义：已选再点无 shift=mouseup 塌成单选、拖动取消 pending；曲线点击 divideAt+无柄 smooth+立即拖；跨对象多段同拖；双击删点 removeSegment+邻柄按 HANDLE_RATIO×曲线长重设）、`handle-tool.js`（Alt 或两柄已不共线 `!isColinear`→独立移动，否则镜像联动 `handleIn=handleOut.multiply(-|handleIn|/|handleOut|)` 方向反转保持自身长度）；**曲线/折线按钮=`src/containers/mode-tools.jsx`（已通读全文）**：isCurved 判定=（无前邻或有 handleIn）&&（无后邻或有 handleOut）&&（双邻⇒两柄 isColinear）；handleCurvePoints 三分支（双邻无柄→handleIn=(prev.point−next.point).normalize()×(prev 曲长×HANDLE_RATIO)；端点/起点→法线×convexity（getCurvatureAtTime(.5)<0?-1:1）+指向邻点方向平均）+第二柄=第一柄×(−1)；straight（handlePointPoints）=选中带柄点清空两柄；**HANDLE_RATIO=0.3902628565**（math.js）。工具接线 `src/containers/reshape-mode.jsx`（纯接线）。**命中分级的 match 语义必须逐条对照原文、不能望文生义**：第1级（选中段）match 是**对象级** `hitResult.item.selected`，第2级（手柄）才是锚点级 `hitResult.segment.selected`——把第1级误写成锚点级（`reshapeSel.has(seg)`）会让未选中锚点的点击落到第3级曲线命中 → `divideAt` 加点 → 拖出新点而原点残留的"幻影锚点" bug（2026-10-20 实测）。抓取通道同 fill。[ses_ebce1d478ffe]

- See MEMORY-tauri-windows-misc.md (8 entries) — .bc 共享工作目录 unpack 语义 / 内置资源提交钩子（含 2812c92 二次实例）/ 发版流程 / Windows hidden_command·编码·taskkill / input 分流 / Tauri 资源打包 / Selected Element（稳定历史知识，2026-10-18 裁剪）

### 角色编辑器

- See MEMORY-sprite-editor-core.md (4 entries) — config.json segments 磁盘格式 / resource.path 指向解压目录 / ObjectURL 释放 / 300ms auto-save 防抖（稳定历史知识，2026-10-18 裁剪）

- See MEMORY-assets-loading.md (20 entries) — 资源加载：sprite/map 库导入解压、`_up_` 过期副本、中文路径图片读取、.bgm zip bug、缩略图刷新；另含 say 气泡三坑与控制台 print 输出链路修复（稳定历史知识，2026-10-15 裁剪）


### 代码模式 Python 打包与 turtle（2026-10-15，已随 v0.5.17~v0.5.19 发布）

- See MEMORY-turtle-packaging.md (6 entries) — 打包必须含 tkinter / pygame-ce / 代码模式执行链 / turtle 保活与 X 关闭三坑 / postlude 测试陷阱 / v0.5.17~v0.5.19 发布状态（稳定历史知识，2026-10-15 裁剪）

### 其他

- **项目内可用字体文件（2026-10-20 勘察，同日已复制进 publicDir）**: 源头 `legacy/assets/font/HarmonyOS_Sans_SC_Regular.ttf`（约 8.2MB 中文字体，PySide6 遗留）与 JetBrains Mono 两处。**已复制到 `engine/assets/fonts/HarmonyOS_Sans_SC_Regular.ttf`**（Vite publicDir，前端经 `/fonts/` 加载；加载封装 `src/components/paint-editor/utils/paintFont.ts` 的 `ensurePaintFont()`）。用户拍板完整 8.2MB 直接打包（不做子集化）。[ses_ffe5ea7fb3831ffe3TChf2A9H3]
- **中文输入法（IME）组词必须 composition 门控（2026-10-20 绘制器文字工具实测）**: 受控 `:value` 绑定 + 每个 `input` 事件同步引擎 = 拼音音节被逐字提交成最终文本（用户实测乱码 `nnini'hni'hani...`）。正确模式：`compositionstart` 置位 → 组词中 `input` 跳过引擎同步（中间态只活在 textarea）→ `compositionend` 一次提交最终值；textarea 用**非受控**（挂载时写一次初值，之后 DOM 由用户输入主导）。对任何「输入框驱动画布对象」的交互（文字工具、标注、重命名就地编辑）都适用。[ses_ffe5ea7fb3831ffe3TChf2A9H3]
- **textarea 刚挂载就失焦的两个常见源（2026-10-20）**: ①父/兄弟元素的 pointerdown 回调里调 `el.focus()`（本例 `.paint-stage` 的 focusStage，tabindex=0）抢走刚聚焦的 textarea；②canvas `setPointerCapture` 把后续指针/焦点事件钉在画布上。文字/标注类覆盖层：编辑态跳过 focusStage、对应工具不 capture；聚焦用 `nextTick + requestAnimationFrame` 双保险。另：`.paint-stage:focus/:focus-visible { outline: none }` 去掉 tabindex=0 带来的浏览器深蓝焦点环（用户取色 ≈ rgb(31,74,148)）。[ses_ffe5ea7fb3831ffe3TChf2A9H3]
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
- See MEMORY-paint-editor.md (6 entries) — 绘制角色编辑器：Stage 0/1 已交付并经三轮实测迭代收敛，T5 修复已提交（ea581a0）；尺寸规格（640×480/手动2048/一键裁切）已验收；多帧绘制+统一 .bsf 保存管线已落码；造型列表「添加序列帧」抽屉三来源（绘制/内置/本地）已实现并经用户测试；交互重设计（绘制页载入全部帧的整角色编辑模型、双击帧进绘制页、抽屉大圆按钮居中）已验收并提交（dbad54a）；**位图选区变换框全套已提交（2026-10-19, be5b3bf）**——锚定缩放/Shift 等比/穿越翻转/复制粘贴删除镜像/顶栏操作组，SVG overlay 硬约束根治烙印/锯齿，配色 indigo（SEL/SEL_DEEP 常量用户自改）；**矢量模式 Stage 2 已分批落地并提交（714a6bf/85a60f6/3e4f1d5/3ccdad7：选择变换框缩放旋转/位图代理 image/橡皮几何接触/画笔胶囊+Scratch 收笔）**；**矢量填充已提交并经用户实测（2026-10-20, 1cacfe3：悬停预览/盲区扫描/洞覆盖片）**；**塑形锚点编辑已提交（2026-10-20, 66e4e93：4级命中/手柄联动/曲线折线按钮/幻影锚点修复/圆锚点+轮廓线）**；**矩形/圆画完自动切选择工具已提交（311b72f）**；**选中图形调色板直改颜色已提交（d7303db：colorEditing 手势合并撤销）**；**描边勾选区已落码（☑ 描边→展开描边色块弹层+粗细滑条；strokeToggleTick 修同值勾选无效——未复验未提交）**；**矢量图标+塑形toggle+顶栏三细节+legacy归档口径已提交（2026-10-20, 727c009；图标唯一 src/assets/icons，legacy/ 已归档删除）**；**位图微调+tooltip+拾色放大镜已提交（2026-10-20, 0ccf29f：框选图标/工具顺序/矢量四按钮 v-if 隐藏/v-tooltip 右侧+4px/放大镜准心=光标/一次性取色 endEyedropper）**；**顶栏关闭/保存重设计已两笔提交（2026-10-20：370080f 布局重构——删左标题/左关闭 X、右侧关闭+保存 190px 等宽列 absolute right:10 对齐面板列、zoom-align absolute right:200 放大钮压分割线、保存=#2b8a48 底+白+brightness(1.15)、关闭.svg 13px CSS 顺序修复；d95c3e9 模式切换——激活态 --accent 绿底+#16201a、padding-left 4、窄窗 nowrap 防竖排）**；**当前=低分屏顶栏挤压降级方案待用户拍板（分析：minWidth 960、矢量 <~1115px 与右侧绝对簇重叠、1366×768@125%=1093 落区间；推荐尺寸输入开画折叠+紧凑隐藏低频按钮，否决悬浮/滚动）**；独立页宿主架构（用户批准）、Paper.js 选型、位图引擎细节（2026-10-20 更新）
- See MEMORY-editor-quirks.md (5 entries) — Monaco/Vue 编辑器渲染与行为杂项：watch 触发、hasUnsavedTabs、suggest 布局、web worker、Monarch 高亮（稳定历史知识，2026-10-18 裁剪）

### 角色资源格式（.bgs → .bsf）

- See MEMORY-bsf-format.md (23 entries) — .bsf v2 格式规范与迁移决策 / BSF 集成实现史（commit 2812c92）/ crates.io 卡死与引擎方法级单测法 / 消费链路与 UPDATE_BATCH·GameCanvas 双实例·加载覆盖层·批量读图修复 / 动画速度链路与 FPS UI / .bgs 去留策略 / 绘制器打包契约·画板规格·追加回写双管线·位图选区 SVG overlay 架构（2026-10-18 裁剪）

- See MEMORY-runtime-rendering.md (6 entries) — GameCanvas 渲染条件链/精灵渲染细节、CREATE_BATCH 4096 截断修复、MapCanvas 时序竞争、scale×scaleX 双乘语义、调试方法论（稳定历史知识，2026-10-18 裁剪）

### Discovered
(none)

### Dead ends
(none)
