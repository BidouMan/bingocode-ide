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
- **世界边界钳制仅重力地图生效（2026-10-15, commit eb99fa3）**: `_resolve_collision` 的 world_bounds "隐形墙"钳制改为 `gravity=True` 才执行。理由：钳制会架空全部边界 API（edge_bounce/is_touch_edge/is_out_side/auto_destroy 子弹销毁）——无重力地图（俯视/太空）自由移动，边界语义交给用户代码；重力地图（平台）边界仍是墙。瓦片/图像碰撞两种模式都保留。[ses_ec075fac1ffe]
- **专注模式（教师专用复制粘贴开关，2026-10-16 已实现，用户验收"可以了"，随 v0.6.1 发布）**: 防小学生复制粘贴偷懒——设置→引擎设置子菜单「专注模式」+ 右侧小 toggle（名字与形态均用户定：初版「专注模式-开/关」文字被否，改 toggle 模式）。语义：**toggle 开（accent 绿）= 复制粘贴禁用**；localStorage `bingo-ide-focus-mode`（'1'/'0'），fresh install（key null）默认开。弃 Ctrl+Alt+C 快捷键方案（误触后无状态提示）。三层拦截（均在 CodeEditor.vue，游戏/代码模式共用）：Monaco onKeyDown preventDefault+stop 拦 Cmd/Ctrl+C/X/V；editor DOM 上 copy/cut/paste/drop preventDefault（drop 防外部拖文本）；doCut/doCopy/doPaste 早退 + 右键菜单三项 `editor-ctx-disabled`（仅 opacity 0.35，**不改鼠标样式**——用户明确要求）。撤销/重做/注释/运行/格式化保留。子菜单 128→152px（toggle 间距）。开关仅老师知道。[ses_ebd75331bffe]

- **Vue store watch 三陷阱（2026-10-20 揘边 UI 迭代取证，跨任务耐久）**: ①**同 tick 值往返不触发**——`setSelection` 同步块内 count 1→0→1，watch 新旧值相同（都是 1）直接不触发 → 依赖"选中变化"的同步必须挂在必经函数（如 syncVectorSelBox）内联调用，不能靠 watch 计数器；②**同值写入不触发**——`store.x = true` 当已是 true 时 watch 不触发 → 勾选/开关类信号需配 tick 计数器（`xxxTick++`）做边沿强制，watch getter 写成数组 `[value, tick]`；③**多 watcher 同 flush 按注册序执行**，A watcher 内改 store 会把受影响 watcher 追加到本 flush 尾部 → 抑制窗口不能立即解锁，须 `nextTick(() => lock=false)`（nextTick 回调在 flush 之后）。[ses_ebce1d478ffe]

- **精灵锚点架构 = 素材级持久化（manifest.pivot），非全局硬编码（2026-10-20 讨论定调）**: .bsf 的 pivot 字段是逐素材属性，引擎/GameCanvas/碰撞统一读该值。方向（**用户已自行在 BingoPacker 侧改完并重打素材**，回"不用 我自己改好了"）：制作工具默认锚点从"脚底"改为"画布中心"（对齐 Unity/Godot/Scratch 中性默认），并加锚点预设快捷按钮（中心/脚底/自定义）；分类预设思路=角色→脚底、道具特效→中心、未知→中性中心，避免角色类素材（占 80%+）每次拖入项目重复手动配置（用户曾提议"默认全中心、案例手动设"，已修正为预设自动化）。已发布内置库由用户重打包统一（boy.bsf 实测 pivot 已从 (48,116) 变 (46.65,87.02)）；大画布素材 pivot 应取 frame rect 并集几何中心而非画布中心（画布下方有留白）。[ses_ffe5ea5dbeec0ffeBn9Er0qjwZ]

- **标注编辑功能（中心点/碰撞/挂点）落位 = 主精灵编辑器中央画布，标注图层体系（2026-10-20 讨论收敛）**: 三者本质是"依附于帧的几何标注数据"，放动画编辑器和绘制页都不合适——参照 Unity Sprite Editor 同画布多模式（Pivot/Custom Physics Shape 共享手柄+数值面板）。布局：画布顶部图层开关条（中心点/碰撞/挂点可多层同显，后两者灰态"即将"占位）+ 底部浮动属性条（X/Y 数值、作用域分段控件、预设、恢复统一）+ 十字拖动手柄（统一绿/覆盖蓝）。**作用域模型**：数据层 = sprite 级默认 + frames[i] 可选单帧覆盖（碰撞/挂点同构）；交互默认作用域"全部帧"，"仅当前帧"开关才写覆盖；覆盖帧造型列表打角标 + "恢复统一"清除；洋葱皮显示相邻帧标注（防碰撞框动画抖动）。动画预览区只读显示标注（验证用，不编辑）。落地顺序：先中心点（引擎已读 manifest.pivot），框架搭好后碰撞/挂点=加新图层零新学习成本。**原型已获用户认可（2026-10-20「目测 还不错 进入开发吧」），进入落码**：per-frame 覆盖存 manifest `frames[i].pivot`（saveBsfManifest 整体回写自动持久化）、引擎 `_setup_hitbox_bsf` 单点回退 `frame.get("pivot") or _bsf_pivot`、协议/GameCanvas 零改动（vox/voy 本就逐帧下发）、重打包按帧名 `carryFramePivots` 保覆盖。交互基准=`design-prototypes/sprite-annotation-editor.html`（自包含单文件、内嵌 boy.bsf 真实素材、QSS 配色）。**落地完成并提交 `4768bbc`（2026-10-20，master，用户实测验收"功能是可以用的"；vue-tsc/build/引擎冒烟全过）**。用户验收后 UI 校准定调：①标注类 UI **不加说明性文字**（操作提示/作用域提示/幽灵标签/tooltip 全删，只留功能标签）；②chip 图标化（中心点.svg）；③「标注图层」分组标题删除；④「重置」按钮=统一 pivot 回加载时快照+清全部覆盖；⑤**顶部工具条与底部浮动条双份同套控件并存对比中（用户未定留哪个）**。注意：commit 时仓库内置资源钩子自动暂存 engine/assets 全部变更（4768bbc 卷入用户自行重打包的 .bsf 库：中心点化+ganda/warrior/minicract 改名+删除数个大画布包）。[ses_ffe5ea5dbeec0ffeBn9Er0qjwZ]

- **自定义角色碰撞功能方向（2026-10-20 用户定调，开发中）**: ①**自动碰撞保留为默认**（现网 getbbox/帧 rect 管线不动）——目标用户是小学生，初学者不该接触碰撞概念；②自定义碰撞=**高级功能**，形状集=矩形/胶囊/自定义多边形，交互=Godot 式锚点/手柄调尺寸（"可以参考下godot"）；③复用中心点建成的标注图层框架（碰撞=图层条上第二个图层），作用域模型沿用统一+单帧覆盖；④**不做 HTML 原型**——"确认方案(要符合专业工业设计要求,参考成熟方案)直接开发"；⑤v1 引擎语义按地图先例"存完整形状、运行时 AABB"（引擎 `is_touch`/`_resolve_collision` 纯 AABB，地图多边形也降级 AABB），真形状判定内核=范围外后续项；⑥manifest 加 `collision` 字段，读写端三处（`_normalize_bsf_manifest` 解析 / `buildBsfSpriteData` 透传 / `saveBsfManifest` 展开保留）；⑦仅 .bsf 支持（.bgs/图片靠自动已够）。**已落码并验证（2026-10-20，未提交）**：引擎 `_normalize_bsf_manifest` 缓存 `_bsf_collision`，`_setup_hitbox_bsf` 以新方法 `_collision_canvas_bbox`（rect/capsule/polygon→画布 AABB→减 offset 写 `_content_bbox`；优先级 `frame.collision > _bsf_collision > 自动`）单点接入——is_touch/物理修正/调试绿框零改动全生效；前端 `SpriteCollisionShape` 联合类型 + 新组件 `CollisionShapeOverlay.vue`（SVG+counter-scale 手柄）+ `carryFrameMetaExtras` 按帧名保 pivot+collision。引擎冒烟 4 场景+vue-tsc+build 全过，用户实测「显示了,可以编辑」。**视觉定调（用户细化轮）**：填充=Scratch 半透明蓝 `rgba(76,151,255,0.28)`、描边=Godot 钢蓝 `#478CBF`、手柄=白底 `#ffffff`+深描边 `#23272e`（选中顶点 `#478CBF`）；**矩形/胶囊的数值输入已移除**（只留手柄编辑）。**已提交 `dd23022`（2026-10-21，含细化轮收尾）**。[ses_ffe5ea5dbeec0ffeBn9Er0qjwZ]

- **挂点/跟随系统（Marker2D 式武器挂载，2026-10-21 四轮对齐定稿并落码，未提交）**: 方案=**Godot 数据模型 + GameMaker 运行时**（引擎驱动管线+扁平 `_SPRITES` 禁场景树，前端保持纯渲染器）。数据与 pivot/collision 同构：manifest 根级 `markers`（名字→{x,y} 画布坐标）+ `frames[i].markers` 帧级按名覆盖（帧覆盖 v1 就做——武器跟挥手动画）。编辑器=标注第三图层「挂点」（首启默认建 `marker` 于内容框中心，chip 列表/改名/增删/紫 `#c678dd` 手柄与角标）。**API 定型（用户拍板）**：`m = player.get_marker("hand_r")`（多挂点用 get_marker 显式取名）；`w.goto(m)` 多态一次性定位（也接受精灵/(x,y)；**`center` 方案被用户自己推翻**——goto 够用）；`w.follow(m)` **必须是方法调用**（用户否决属性式："follow 是具体的行为，.x/.angle 才是属性"）、`w.unfollow()`；follow **只写 x/y+镜像不碰 angle**（`look_at(mouse)` 独立瞄准）；**默认不跟随**（不写=纯 Scratch 循环，与 goto/手写三者共存）；**镜像继承 `follow(target, flip=True)` 默认开**（父翻面武器贴图跟着翻，Godot 子节点观感；flip=False 供鼠标瞄准武器；`rotation_style="none"` 永不翻）。引擎落地：`_MarkerRef` 求值端世界坐标（挂点−pivot→缩放镜像→旋转→平移）、`_update_follows` 挂两主循环 flush 前、镜像链 `_display_flip`（父）→`_follow_flip`（子）→乘进 `scale_x` 走现有协议（前端零改动）；`_has_active` 自动退出判断须加 follow（否则只写跟随的游戏秒退）。验证：冒烟 32 断言全过+vue-tsc+build。

  **UI 定稿（2026-10-21 两轮收敛，已落码未提交）**：图层名「挂点」→**「标记」**（三 chip = 中心/碰撞/标记，各配图标 `中心点.svg`/`重置锚点.svg`/`标记.svg`）；**标记可重命名**（用户先要求"不能重命名"、随即**反转**为"重命名功能要保留"——双条工具栏各一个改名输入框，改名时统一值与全部帧覆盖同步换 key；**教训：同一 UI 项的取舍用户可能快速反复，以最新口径为准**）；**删掉工具栏 chip 列表**——选择路径唯一=画布上直接点选/拖拽，工具条只留「添加（带 标记.svg 图标）」「改名框」「删除」「X/Y」「恢复统一」「作用域」；默认名中文 `标记`、新增自动编号 `标记2`/`标记3`…；画布手柄从紫色十字环换成 **`标记.svg` 图钉，主题绿 `#5BFB84`**（原紫 `#c678dd` 废弃），图钉尖对准锚点逻辑坐标（20px 图标 `left:-10px; top:-18.5px`）；角标同步改绿。**上色实现 = 内联 SVG**（`import raw from '标记.svg?raw'` → `fill="#ffffff"`/`fill:white` 换 `currentColor` → `v-html`，CSS `color` 控色、`:deep(svg)` 定尺寸），**不用 CSS mask**——mask 在 WKWebView 上不可靠（详见下条 durable knowledge）。[ses_ffe5ea5dbeec0ffeBn9Er0qjwZ]

- **标注能力从「仅 .bsf」扩到「单图角色」（2026-10-21 用户报 bug 后改写的早期取舍）**: 早期取舍「仅 .bsf 支持标注（.bgs/图片靠自动已够）」被用户实测推翻（png 角色中心点/碰撞/标记全缺）。定案方案 = **载入单图角色时内存合成单帧 bsf（不碰磁盘，`canAnno` 无需特判）→ 首次真正写标注的 300ms 防抖落盘时懒转正为同名 `.bsf` 目录**（sheet.png=原图 + manifest.json，删旧单图，`resourceStore.updateItemPath` 改资源项 path）。**否决「打开编辑器即转正」**：`MainLayout.autoSelectFirst`/sprites watch 会主动设 `selectedSpriteId`，打开即转正会让"只想看看/切页"也改磁盘格式。**配套：图片派生的目录角色统一产 `.bsf`（不再产 `.bgs`）**，否则补帧或绘制页保存后退回 .bgs、标注又消失。引擎零改动，UI 层（`CollisionShapeOverlay.vue`/手柄/chip）零改动。历史 `.bgs` 目录角色仍在作用域外。[ses_ffe5ea2dc151cffeO0vkc0iUh8]

- See MEMORY-course-curriculum.md (7 entries) — 课程/课件体系已稳定且与当前开发焦点无关：课程产品定位（60 节启蒙课）、六阶段大纲、开篇 Run→Modify→Build 教学法、课件文档与 90 课表格版交付位置、用户《课程体系.md》教学理念（术语降维·咒语卡·评估）

## Discovered durable knowledge (terminal/console)

- **legacy/ 目录已安全移除并归档（2026-10-20）** — `legacy/`（老 PySide6 工程：main.py/ui/*.py/requirements.txt，1.3G 中 1.2G 为可重建的 .venv）整目录在 .gitignore、git 零跟踪、前端零代码引用。用户授权"在安全的情况下移除"后执行：图标全量同步进 `src/assets/icons/`（误同步的 undo/redo 用 `git checkout --` 回退）→ 归档 `~/BingoCodeIDE-legacy-pyside6-archive-20261020.tar.gz`（14M，196 文件，排除 .venv/__pycache__/.DS_Store，tar -tzf 校验关键文件 ✓）→ `rm -rf legacy/` → AGENTS.md 更新（移除指向 legacy 的「Reference Original First」节，改为归档说明 + 素材目录约定）。**归档包是 PySide6 原版参考的唯一副本，勿删**；需要查阅原始布局/交互时从归档解压临时目录阅读，不恢复回仓库。原 .gitignore `legacy/` 条目可保留（无害）。[ses_ffe5ea6b2a993ffeHddz87eJYy]
- See MEMORY-paint-editor.md — 绘制页（矢量/位图）全套稳定条目：Scratch 双模式选型、矢量填充 recolor、文字工具、图标与顶栏布局定稿、pixelated 实测、scratch-paint 塑形规格
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
- **内置库 .bsf 锚点现状 = 全部脚底（BingoPacker 全局默认），锚点已逐素材存 manifest.pivot（2026-10-20 全量核查 51 角色+7 道具）**: BingoPacker 制作时默认 pivot=画布内容底中心上方 4px（4px=打包留白），无差别应用于角色与道具（coin/sun 也是脚底）；大画布 840×720/480×480 素材 pivot 在内容底部非画布底部；唯一手动例外 `bullets_1.bsf` pivot(7,8) 左侧中心。**引擎/GameCanvas 读 manifest.pivot、无硬编码** → 改制作工具默认零引擎改动、新旧素材共存。锚点行业惯例：Unity/Godot/Scratch 默认均为几何中心，脚底是平台/Y-sort 常见选择而非"行业标准"。方向（用户酝酿改 BingoPacker）：默认改中心+预设按钮（中心/脚底/自定义），已发布库不重打包。[ses_ffe5ea5dbeec0ffeBn9Er0qjwZ]
- **playwright-cli wrapper 要求系统 Google Chrome，本机没有则直接失败（2026-10-20 实测）**: 内置 `playwright_cli.sh` 经 npx 调 `@playwright/cli`，报 `Chromium distribution 'chrome' is not found at /Applications/Google Chrome.app`；`npx playwright install chromium` 装好 headless shell 也不回退（且 wrapper 无执行位，需 `zsh <path>` 调用）。**可用替代**：`npm install --prefix /tmp playwright` 后自写 node 脚本 `chromium.launch()`（QA 截图/交互验证三脚本全通过）。除非用户要求装 Chrome，勿走 `npx playwright install chrome` 路线。[ses_ffe5ea5dbeec0ffeBn9Er0qjwZ]
- **.bsf pivot 数据流全图（2026-10-20 落码前梳理，file:line 证据）**: 保存=`scheduleSave` 300ms 防抖→`saveBsfManifest`（`invoke('write_file')` 写 manifest.json，`pivot: sprite.bsf.pivot` + `frames` 整体回写——**帧对象加字段即自动持久化**）；读取=`readSpriteFromPath`→`readBsfFromDir`→`buildBsfSpriteData`（bsf={canvas,pivot,frames}，每帧裁回全画布 blob）；引擎=`_normalize_bsf_manifest`(bingo_engine.py L1347) 缓存 `_bsf_pivot`、`_setup_hitbox_bsf` 算 `vox = pivot.x - (offset.x + rw/2)`。**per-frame 覆盖只需 `_setup_hitbox_bsf` 一行 `frame.get("pivot") or self._bsf_pivot`**：CREATE/UPDATE 协议 vox/voy 本就逐帧下发（帧切换重算，缓存键含 `_bsf_frame_index`），GameCanvas anchor=0.5 + `pivot.x=vox` 脏检查已含 → 协议/渲染 store/GameCanvas 全零改动。**对齐不变量**：`sprite.frames[i] ↔ bsf.frames[i]`（.bsf 帧不可删，同序 push）；重打包后 rect/offset 变但帧名稳定 → 帧级覆盖按**帧名**搬运（carryFramePivots）。编辑器只编项目内 .bsf（内置库选中先解压进项目）。**屏幕恒定尺寸覆盖元素（手柄/幽灵/标签）放 zoom transform 容器内必须反向 `scale(1/zoom)`**。[ses_ffe5ea5dbeec0ffeBn9Er0qjwZ]
- **碰撞系统管线全图（2026-10-20 explore 调查，自定义碰撞功能的工程地基）**: 引擎碰撞=**纯 AABB**，世界 AABB 唯一出口 `_get_hitbox_rect`（bingo_engine.py L1495-1574，bbox 四角按 PixiJS 变换管线 R·S·(local−pivot) 处理 flip/rotate/scale，帧级缓存；left_right/none 旋转风格有效角归零）。自动碰撞：`.bgs`/图片 `_setup_hitbox` L1419-1456=PIL `getbbox()` 非透明包围盒+内容重心偏移；`.bsf` `_setup_hitbox_bsf` L1458-1493=帧 rect O(1)。**调用方全景**：`_resolve_collision`（物理位移修正：图像图层/瓦片/重力地图边界）、`is_touch`（精灵-精灵/mouse/标签瓦片）、`is_touch_edge`/`is_out_side`/`edge_bounce`、`is_on_floor`（脚底 1.5px 探测）、`face`/`distance_to`（视觉中心）、主循环 `on_hit`。**地图碰撞共用**：地图侧多边形 `collision_shape.points` 运行时同样**降级为 AABB**（L442-460 min/max）——角色自定义碰撞 v1 "存形状、用 AABB" 与现网语义一致。hitbox 调试显示链路现成：`show_collision(sprite)` L1936-1941 → UPDATE 协议 `"hitbox"` 字段 L1624-1626 → useEngine → render.ts L304 → GameCanvas `syncHitboxes` L586-630 绿色 1px 框（renderStore.showCollision 门控）。manifest 扩展三处：引擎 `_normalize_bsf_manifest` L1336-1390 / 前端 `buildBsfSpriteData` / `saveBsfManifest`（现只写 clips+defaultFrame，新字段需展开保留）。`hitbox_scale` L144=从未读的死属性。地图 `CollisionEditor.vue` 有多边形顶点编辑全套交互惯例（加点首闭/插边/删点/拖拽/8px 吸附）可复用。学生 API（is_touch:on_hit 等）底层全走 `_get_hitbox_rect`。[ses_ffe5ea5dbeec0ffeBn9Er0qjwZ]
- **manifest 根级字段有两个写点（2026-10-21 踩坑+修复）**: `saveBsfManifest`（正常保存路径）与 `appendSpriteFrames.ts` 的 `rewriteBsfDir`（绘制页「编辑角色」整体回写，自拼 JSON 绕过 saveBsfManifest）——**新增根级 manifest 字段（如 collision/markers）两处都要写**，否则绘制页重写悄悄丢字段（rewriteBsfDir 曾漏根级 collision，统一碰撞被清，已随挂点工作修复）。帧级字段由 `carryFrameMetaExtras` 按帧名搬运（两调用点共用）。[ses_ffe5ea5dbeec0ffeBn9Er0qjwZ]
- **bingo_engine.py 无头冒烟测试跑法（2026-10-21 挂点测试沉淀）**: ①必须写成**文件**跑（`python3 /tmp/test_x.py`），heredoc/stdin 环境会挂——引擎模块导入时 `sys.stdout = os.fdopen(sys.stdout.fileno(), ...)` 需真实 fileno；②导入后**保活**引擎创建的 stdout 包装（`_engine_stdout = sys.stdout` 再恢复旧的），否则 GC 关掉 fd 1 报 `Bad file descriptor`；③dummy 精灵 `object.__new__(Sprite)` 绕过 __init__ 后须手动 `be._SPRITES[s.id] = s`（`_update_follows` 等遍历它）+ 补齐全部 `_` 前缀状态字段；④测显示镜像/翻转必须走 `silent(p._update_transform)` 同步 `_display_flip`（手动改 `_current_scale_x` 不生效——`_display_flip` 只在 `_update_transform` 内刷新）；⑤测 UPDATE 发包先清 `_FRAME_UPDATES` + `_last_update_key = None`（缓存命中跳过发包）；⑥`sys.path.insert(0, engine目录)`（import models.map_model）。[ses_ffe5ea5dbeec0ffeBn9Er0qjwZ]
- **白 fill SVG 图标在 UI 内变色：首选内联 SVG（currentColor），其次 CSS mask（2026-10-21 实测修正）**: `src/assets/icons/` 现成图标多为 `fill="#ffffff"`，`<img>` 无法改色。**首选方案**：`import raw from 'x.svg?raw'` → 把 `fill="#ffffff"` / `fill:white` 替换成 `fill="currentColor"` → `<div v-html="...">`，容器 CSS `color:<目标色>` 控色 + `:deep(svg){width:100%;height:100%;display:block}` 定尺寸 + `filter: drop-shadow(...)` 做光晕。优点：不依赖 mask 的跨 WebView 支持、无 URL 解析/CSP 问题、颜色与 svg 源解耦（一个图标多色复用，**绝不改 svg 的 fill**——会牵连同图标其它使用点）。**CSS mask 为什么弃用（本会话踩坑）**：①Vue `:style="{ WebkitMaskImage: ... }"` 会被 hyphenate 成 `webkit-mask-image`（**缺前导 `-`**）→ 浏览器静默忽略，必须写 kebab 键 `'-webkit-mask'`；②WKWebView（macOS Tauri 实际渲染引擎）对 mask 支持不稳定；③file:// 下测试还有两个假阴性（内联 style 相对 URL 的 mask computed 成 `url("")`、外部 CSS 相对 URL 渲染空白），易误判。**若确需 mask 备选**：`-' -webkit-mask': url("icon.svg") center / contain no-repeat` + `background:<色>` + `mask-size: contain`。另：map-pin 类"尖端指示位置"的图标锚点须按**尖**算偏移（`标记.svg` viewBox 1024 内尖在 y≈947，20px 图标 → `left:-10px; top:-18.5px`），不能用居中对齐。[ses_ffe5ea5dbeec0ffeBn9Er0qjwZ]

## compose-preferences

- execution-style: subagent

## Discovered durable knowledge
_Cross-task facts that survive across sessions._

### Tauri/Vue/Monaco/Windows 杂项

- **内置素材风格 = 插画为主，非像素画（2026-10-16 Pillow 实测）**: characters/images 24 张（boat 128×128、cannon 500×500、car 236×167，>256px 占 15）、items/images 21 张全 108×108、maps/images 43 张全 640×480（与逻辑分辨率 1:1，渲染模式几乎无差别）；真像素画仅 maps/tiles（grass 16×16、brick 32×32）与 tilesets 共 2-3 张。锐利边缘比/半透明比测量确认角色与道具是卡通插画。推论：PixiJS 渲染模式默认 **smooth 更合适**（道具/角色常缩小显示，nearest 对插画 stair-stepping）；pixelated 供像素画项目手动切换。若未来内置库扩充像素画素材包，重新评估默认值。用户已拍板 master 默认保持 smooth（2026-10-16 撤回临时 pixelated 改动，未入库）。[ses_ebd75331bffe]


- **paper.js 命中/填充 API 事实（0.12.18 源码+Node 实测，2026-10-20 矢量填充批）**: ①`project.hitTest` 的 **point=项目坐标**（Item._hitTest 只做 item 局部矩阵逆变换，view.matrix 仅参与 stroke/tolerance 缩放）→ clientToArtboard 直接喂；fill 命中要求 `style.hasFill()`（无填充闭合路径内部=MISS）；②**CompoundPath._hitTestChildren 对子级强制 fill:false** → 复合只在整体层回 fill 命中、子级 stroke 命中经验性 null → 复合描边/洞（XOR contains=false）/未填充内部全是 stock 盲区（fork @scratch/paper 的 `hitUnfilledPaths/hitUnstrokedPaths` stock 不存在，grep dist 零命中）；③`getNearestLocation`/`contains` 输入输出皆项目坐标且穿透父级变换链，`loc.distance`=查询点到最近点距离；④`CompoundPath.reduce` 单子→Path、≥2 子→自身（幂等）；⑤clone→insertAbove→`transform(parent.getGlobalMatrix())` = 世界系 prepend（**getGlobalMatrix d.ts 未收录**需窄断言）；⑥`Color.toCSS` d.ts 要求参数（用 `toCSS(false)` 比 rgba 串）；hitTest options d.ts 类型 `object`（match/segments 等随意传）；⑦开放近闭合路径 contains 隐式闭合（首尾距<8 可当闭合填）。**scratch-paint 源码抓取**：GitHub API `contents?ref=develop` 或 `cdn.jsdelivr.net/gh/scratchfoundation/scratch-paint@develop/...`（raw.githubusercontent 超时；fill 规格在 `src/helper/tools/fill-tool.js`，`src/tools` 是 404）。⑧TS 闭包坑：`let x=null` 闭包内赋值、闭包外读会收窄成 `never`（TS2339）→ 改显式栈迭代。⑨`project.hitTestAll` 返回序=自顶向下（hitTestChildren 遍历 children l-1→0、filter 依次 push 到 options.all）→ `hits[0]` 即最顶，无需 sortItemsByZIndex。⑩**stock d.ts 命名 ≠ @scratch/paper fork API**（2026-10-20 reshape 落码 vue-tsc 全量核实）：`Segment.previous/next/curve` 是**属性**（fork 的 getPrevious()/getNext()/getCurve() stock 无）；**加点=`Curve.divideAt(location)`→返回右段、新锚点=`nc.segment1`**（`PathItem.divideAt` stock 不存在）；`isCollinear`（双 l，d.ts 规范名，运行时有 isColinear 别名但 d.ts 不收）；`PathItem.segments` d.ts 未收录→cast `(item as paper.Path).segments`（运行时 CP 同可用）；`Item.removed` 不存在→用 `path.parent` 真值判 detach；hitTest options d.ts 类型 `object`→match 回调参数须显式标 `(hr: paper.HitResult)`；`segment.smooth()` ✓、`seg.path.localToGlobal/globalToLocal` ✓（项目坐标穿透父级变换链）；`Curve.getLocationAt`=弧长 offset、`getLocationAtTime`=参数时间；`segment.smooth()` 不给开放路径端点设单侧柄；handleIn/handleOut 赋值用零向量 (0,0) 替代 null（防后续 .length 崩）。⑪`PathItem.getPathData(matrix?)` 运行时方法 **d.ts 未收录**（需窄 cast `(item as unknown as {getPathData:(m:paper.Matrix)=>string})`），传 **`item.globalMatrix`（d.ts 有，readonly）** 得项目坐标 path data；复合路径子路径间用小写 `m`（SVG 合法）；本项目 applyMatrix=true 变换已烘进 segments、matrix 恒 identity → 无参与带 globalMatrix 同值（Node 实测），带参幂等安全——SVG overlay 轮廓线即用此法。[ses_ebce1d478ffe]



- See MEMORY-tauri-windows-misc.md (8 entries) — .bc 共享工作目录 unpack 语义 / 内置资源提交钩子（含 2812c92 二次实例）/ 发版流程 / Windows hidden_command·编码·taskkill / input 分流 / Tauri 资源打包 / Selected Element（稳定历史知识，2026-10-18 裁剪）

### 角色编辑器

- See MEMORY-sprite-editor-core.md (4 entries) — config.json segments 磁盘格式 / resource.path 指向解压目录 / ObjectURL 释放 / 300ms auto-save 防抖（稳定历史知识，2026-10-18 裁剪）

- **标注三件套（中心点/碰撞/标记）只有 .bsf 有，三层同时门控（2026-10-21 全链路取证，png 单图或 .bgs 角色都拿不到）**: ①**编辑器 UI**：`SpriteEditorView.vue` 的 `canAnno = computed(() => !!currentSprite.value?.bsf)`（L325）是整条标注工具条的 `v-if`，全部标注处理器（effPivot/L331、setPivot、resetAnno/L363、effCollision/L377、frameContentCollision/L430、activateAnnoLayer/L442、marker 全段 L512-646、pivotGhosts/L677、screenToCanvas/L697 无 bsf 直接 return null）都以 `currentSprite.value.bsf` 取数；②**数据层**：`useSpriteData.ts` 只有 `buildBsfSpriteData`（L210）构造 `bsf = {canvas, pivot, frames, collision?, markers?}`，`readImageAsSprite`（L440）产出的 `SpriteData` 无 bsf 字段，`saveSpriteConfig`（L418，.bgs 的 config.json）也不写 pivot/collision/markers；③**引擎**：`bingo_engine.py` 的 `_normalize_bsf_manifest`（L1434）才缓存 `_bsf_pivot/_bsf_collision/_bsf_markers`，`_setup_hitbox`（L1564）对非 bsf 走 PIL `getbbox()` 内容包围盒 + 内容重心（这就是「图片角色 x/y = 内容重心」的来源），`_marker_world_xy`（L1504）首行判 `_is_bsf`，`get_marker`/`follow` 对图片角色直接失效。**结论：不是工具栏渲染 bug，是功能真没有**（数据/UI/引擎三层一致缺失）。[ses_ffe5ea2dc151cffeO0vkc0iUh8]

- **单图角色（png/jpg）在项目里的两种落地形态 + 转正为目录角色的既有先例（2026-10-21 取证）**: 上传入口 `UploadDrawer.vue` L184-212 把图片**原样复制**成 `assets/sprites/角色N.<ext>`（单文件，可被引擎 `_resolve_path` 直接找到）；**SVG 角色不落盘成 svg**——L116-136 先用 `svgToPngBlob` 栅格化成 PNG 再按同名规则写 `角色N.png`（引擎 Pillow 不支持 svg，故项目内角色永远没有 .svg 文件；`readSpriteFromPath` 的图片正则 `\.(png|jpe?g|gif|bmp|webp)$` 也不含 svg）。**转正先例**：`appendSpriteFrames.ts` 的 `appendImageSprite`（追加帧）与 `rewriteSpriteFrames`（绘制页整角色回写，`PaintEditorPage.vue:136` 调用）都会把单图角色转成同名目录（`saveImageSpriteToDirectory` 写帧 + config.json，随后删掉旧单文件），并返回 `{ newPath }`；`MainLayout.vue` L801-817 `onFramePicked` 用 `resourceStore.updateItemPath(item.id, res.newPath)` + `bumpSpriteThumb` + `spriteEditorRef.reload()` 收尾。**缩略图链路对 .bsf 目录已通**：`MainLayout.loadSpriteThumbnail`（L1155）先判 `.bsf` 后缀、再查 `path/manifest.json` 存在则走 `getBsfThumbnail`，否则 `get_sprite_thumbnail`。[ses_ffe5ea2dc151cffeO0vkc0iUh8]

- **单图角色 → .bsf 的无痛等价换算 + 复用底座（2026-10-21 落码）**: 把单张 png 角色转成 .bsf 目录时，取 `canvas`=原图尺寸、单帧 `rect`=非透明内容框、`offset`=内容框左上、`pivot`=内容框中心、`sheet.png`=原图像素不变 ⇒ 引擎 `_setup_hitbox_bsf` 得 `vox/voy=0`、`_content_bbox`=(0,0,rw,rh)，与旧 `Image.open().getbbox()` 路径（x/y=内容重心+紧凑碰撞框）**逐像素等价**，老项目位置/缩放/碰撞手感不变。实现：`useSpriteData.ts` 的 `isImageSpritePath` / `imageContentBox`（canvas+`contentBBox` 扫 alpha）/ `buildSingleFrameBsfMeta` / `imageSpriteToBsfDir`。复用地基是 `src/utils/bsfPacker.ts`：`contentBBox(canvas)`、`packDrawnFrames(canvases,w,h,names?)`（shelf 排布 + 2px padding + offset=裁剪位置）、`buildDrawnBsfManifest(name,packed)`；它对本模块只有 `import type` ⇒ 反向运行时 import 无循环依赖。[ses_ffe5ea2dc151cffeO0vkc0iUh8]
- **转正目录的写盘顺序纪律 + 标注落盘触发点差异（2026-10-21 落码）**: 转正/重打包必须**先写 sheet.png → 再写 manifest.json → 最后删原图**，任何中途失败都不会留下「目录缺 manifest」或「原图已删但目录不可读」。标注落盘触发点不对称：`中心` chip 只切图层不写盘（首写发生在拖动/改数值），`碰撞` chip 走 `activateAnnoLayer` 首次初始化 `bsf.collision=frameContentCollision()`、`标记` chip 走 `addMarker()` ⇒ 单图角色点后两者即懒转正。另：图片角色派生目录（追加帧 `appendImageSprite` / 绘制页回写 `rewriteSpriteFrames`）**必须产 .bsf 不能退回 .bgs**，否则标注能力再次消失；且 `package.json` 无 typecheck 脚本，校验只能 `npx vue-tsc --noEmit` + `npx vite build`。[ses_ffe5ea2dc151cffeO0vkc0iUh8]

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
- See MEMORY-paint-editor.md (17 entries) — 绘制角色编辑器全套稳定条目（2026-10-21 追加裁剪 11 条）：Stage 0/1 交付与三轮实测收敛、尺寸规格（640×480/手动2048/一键裁切）、多帧绘制+统一 .bsf 保存管线、造型列表抽屉三来源、交互重设计（载入全部帧/双击帧/大圆按钮）、**位图选区变换框（be5b3bf）**、**矢量 Stage 2 分批（714a6bf/85a60f6/3e4f1d5/3ccdad7）**、**矢量填充（1cacfe3）**、**塑形锚点（66e4e93）**、矩形圆自动切选择（311b72f）、调色板直改色（d7303db）、描边勾选区（未复验未提交）、**图标 727c009 / 位图微调+tooltip+拾色放大镜 0ccf29f / 顶栏布局 370080f+d95c3e9**、低分屏挤压降级待拍板、**Scratch 双模式选型**、**矢量填充 recolor 架构**、**文字工具全链路**、**pixelated@WKWebView 实测**、**scratch-paint reshape 规格（HANDLE_RATIO=0.3902628565、命中分级 match 语义）**
- See MEMORY-editor-quirks.md (5 entries) — Monaco/Vue 编辑器渲染与行为杂项：watch 触发、hasUnsavedTabs、suggest 布局、web worker、Monarch 高亮（稳定历史知识，2026-10-18 裁剪）

### 角色资源格式（.bgs → .bsf）

- See MEMORY-bsf-format.md (23 entries) — .bsf v2 格式规范与迁移决策 / BSF 集成实现史（commit 2812c92）/ crates.io 卡死与引擎方法级单测法 / 消费链路与 UPDATE_BATCH·GameCanvas 双实例·加载覆盖层·批量读图修复 / 动画速度链路与 FPS UI / .bgs 去留策略 / 绘制器打包契约·画板规格·追加回写双管线·位图选区 SVG overlay 架构（2026-10-18 裁剪）

- See MEMORY-runtime-rendering.md (6 entries) — GameCanvas 渲染条件链/精灵渲染细节、CREATE_BATCH 4096 截断修复、MapCanvas 时序竞争、scale×scaleX 双乘语义、调试方法论（稳定历史知识，2026-10-18 裁剪）

### Discovered
(none)

### Dead ends
(none)
