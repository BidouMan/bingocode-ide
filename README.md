# BingoCode IDE

面向教学的 Python 游戏开发桌面 IDE。学生用少量代码即可做出可玩的游戏，也可当作标准 Python IDE 学习 `turtle`、`pygame` 等常用库。

基于 **Tauri v2 + Vue 3 + PixiJS** 构建，内置 **Python 游戏引擎**（`bingo_engine.py`），打包自带完整 Python 运行环境，学生无需自行安装。

---

## 功能特性（当前版本 0.6.3）

### 双模式

| 模式 | 说明 |
|------|------|
| **游戏模式** | 可视化编辑器（角色 / 地图 / 碰撞）+ 代码编辑 + 实时预览，专为游戏课堂设计 |
| **代码模式** | 标准 Python IDE：运行 / 停止 / 撤销 / 重做，支持turtle、pygame 及绝大多数标准库 |

### 可视化编辑器

- **角色编辑器**：造型列表、多帧动画、实时预览；支持导入 `.bgs` 角色包与本地图片
- **地图编辑器**：瓦片绘制、多图层（绘制层 / 图像层）、瓦片集管理、碰撞编辑；支持 SVG/PNG 背景导入，缩放与拖动可吸附网格
- **碰撞编辑器**：逐瓦片设置碰撞类型（实心 / 跳板等）
- **资源面板**：内置角色库（按「角色 / 道具」分类）、地图库、音效库；支持上传本地资源、抽屉式导入

### 游戏引擎（教学 API）

面向学生的简化 API，`import` 后即可使用：

```python
fish = Sprite('fish_2')

while True:
    fish.move(10)
    fish.edge_bounce()        # 碰到舞台边缘自动反弹
```

- **角色**：移动、转向、旋转（跟随 / 左右翻转）、缩放、显隐、多造型动画
- **边界**：`edge_bounce`（自动反弹）、`is_touch_edge`（碰到边缘）、`is_out_side`（完全出界，配合自动销毁子弹）
- **输入**：键盘 `key_down` / `key_pressed`、鼠标位置与按键
- **互动**：`is_touch` 碰撞检测、分组碰撞回调、广播
- **外观**：`say` 气泡说话、计时器 `Timer`、重力与跳跃（平台模式）
- **地图**：加载 `.bgm` 地图、瓦片碰撞、摄像机跟随

### 代码模式运行环境

- 打包自带完整 Python（标准库齐全），`import turtle`、`import pygame` 开箱即用
- `turtle` 窗口自动保持打开（无需写 `turtle.done()`），点击窗口关闭按钮即正常退出并停止运行
- 学生友好的错误提示（语法错误、未定义变量、除零等翻译为中文）

### 内置资源库

- **角色包**（`.bgs`）：鱼群、忍者、海盗、骑士、骷髅、吸血鬼、马里奥等 30+ 套
- **地图背景**：全部统一 640×480，含 PNG 与 SVG（矢量，放大清晰），文件名规范（小写下划线）
- **音效**：内置常用音效，支持上传 `.wav`
- 新增分类 = 新建目录即可，无需改代码

### 其他

- **主题**：暗色 / 亮色 / One Dark / Nord / Gruvbox
- **自动更新**：应用内检查并下载新版本
- **跨平台**：macOS（Apple Silicon）与 Windows（x64）

---

## 下载

从 [GitHub Releases](https://github.com/BidouMan/bingocode-ide/releases/latest) 下载对应平台安装包：

- **macOS**：`.dmg`（Apple Silicon）
- **Windows**：`-setup.exe`

安装后打开即用，无需安装 Python。

---

## 开发环境搭建

### 环境要求

| 工具 | 版本 | 说明 |
|------|------|------|
| **Node.js** | >= 18 | 前端运行 |
| **pnpm** | >= 8 | 包管理器 |
| **Rust** | stable | Tauri 桌面端编译 |
| **Python 3** | >= 3.12 | 游戏引擎（开发环境） |

### 安装与启动

```bash
git clone https://github.com/BidouMan/bingocode-ide.git
cd BingoCodeIDE

# 前端依赖
pnpm install

# Python 引擎环境（创建 venv 并安装 Pillow/numpy/pygame-ce 等）
cd engine && bash setup.sh && cd ..

# 启动开发
pnpm tauri dev

# 打包（打包前需先准备 portable-python）
pnpm engine:portable
pnpm tauri build
```

### 打包 Python 说明

打包版使用 [python-build-standalone](https://github.com/astral-sh/python-build-standalone) 嵌入式发行版（`scripts/setup-portable-python.sh`），安装 `engine/requirements.txt` 依赖（含 `pygame-ce`）。**不可删除 `tkinter`/`turtledemo`/`unittest`**——`turtle` 依赖 tkinter。

---

## 项目结构

```
BingoCodeIDE/
├── src/                        # Vue 3 前端
│   ├── components/
│   │   ├── layout/             # 主布局（菜单 + 侧边栏 + 编辑区）
│   │   ├── canvas/             # PixiJS 游戏画布（640×480 逻辑舞台）
│   │   ├── editor/             # Monaco 代码编辑器
│   │   ├── sprite-editor/      # 角色编辑器
│   │   ├── map-editor/         # 地图编辑器
│   │   ├── resource-panel/     # 资源面板 + 上传抽屉 + 角色库
│   │   └── terminal/           # xterm.js 控制台
│   ├── stores/                 # Pinia 状态（编辑器 / 渲染 / 地图 / 资源 / 主题…）
│   ├── composables/            # 引擎 IPC、文件对话框等
│   └── utils/                  # 地图序列化、SVG 超采样等
├── src-tauri/                  # Tauri Rust 后端（文件 I/O、Python 子进程）
├── engine/                     # Python 游戏引擎
│   ├── bingo_engine.py         # 引擎核心（游戏模式 API）
│   ├── code_transform.py       # while True → 生成器 改写
│   └── assets/                 # 唯一资源库（Vite publicDir 指向此处）
│       ├── sprites/            # 按分类目录组织（characters / items / …）
│       │   └── <分类>/
│       │       ├── packages/   # .bgs 角色包
│       │       └── images/     # 帧图片
│       ├── maps/
│       │   ├── packages/       # .bgm 地图包
│       │   └── images/         # 地图背景（统一 640×480）
│       └── sounds/             # 音效（.wav）
└── .github/workflows/          # CI：打 tag 自动构建双平台并发布
```

---

## 更新日志

版本历史与每次发布的功能 / 修复记录见 **[CHANGELOG.md](CHANGELOG.md)**。

当前最新版本：**v0.6.3** —— 新增 `.bsf` sheet 图集精灵格式（单贴图 UV 动画，老机器友好）与默认渲染帧（编辑器选中帧即初始外观），修复动画换帧不刷新、加载层闪烁等问题。

> 发版流程：打 tag 前在 `CHANGELOG.md` 为该版本添加条目（最新在前，按 新增 / 修复 / 优化 / 资源 分类）；未发版的 master 改动记入「未发布」小节，发版时移入正式版本号。

---

## License

MIT
