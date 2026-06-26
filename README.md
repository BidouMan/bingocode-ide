# BingoCode IDE

基于 Tauri v2 + Vue 3 + PixiJS 的游戏开发桌面 IDE，配套 Python 引擎。

## 环境要求

| 工具 | 版本 | 说明 |
|------|------|------|
| **Node.js** | >= 18 | 前端运行 |
| **pnpm** | >= 8 | 包管理器 |
| **Rust** | stable | Tauri 桌面端编译 |
| **Python 3** | >= 3.9 | 游戏引擎 |
| **Tauri CLI** | v2 | `cargo install tauri-cli` |

## 一键安装

```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/BidouMan/bingocode-ide/master/setup.sh | bash

# 或者 clone 后手动运行
git clone https://github.com/BidouMan/bingocode-ide.git
cd BingoCodeIDE
bash setup.sh
```

## 手动安装

### 1. 安装 pnpm（如果没有）

```bash
npm install -g pnpm
```

### 2. 安装 Rust（如果没有）

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env
```

### 3. 安装 Tauri CLI

```bash
cargo install tauri-cli
```

### 4. 安装项目依赖

```bash
# 前端依赖
pnpm install

# Python 引擎环境
cd engine && bash setup.sh && cd ..
```

### 5. 启动开发

```bash
pnpm tauri dev
```

## 项目结构

```
BingoCodeIDE/
├── src/                    # Vue 3 前端
│   ├── components/         # UI 组件
│   │   ├── layout/         # 主布局
│   │   ├── canvas/         # PixiJS 游戏画布
│   │   ├── editor/         # Monaco 代码编辑器
│   │   ├── sprite-editor/  # 角色编辑器
│   │   ├── map-editor/     # 地图编辑器
│   │   ├── resource-panel/ # 资源面板 + 角色库
│   │   └── terminal/       # xterm.js 控制台
│   ├── stores/             # Pinia 状态管理
│   ├── composables/        # 组合式函数
│   └── types/              # TypeScript 类型
├── src-tauri/              # Tauri Rust 后端
├── engine/                 # Python 游戏引擎
│   ├── bingo_engine.py     # 引擎核心
│   ├── models/             # 数据模型
│   └── assets/             # 内置资源
└── public/                 # 静态资源
    └── sprite_lib/         # 内置角色库 (.bgs)
```

## 使用方式

- **游戏模式**：左侧资源面板 + 代码编辑 + 实时预览
- **代码模式**：标准 Python IDE（运行/停止/撤销/重做）
- **角色编辑**：点击顶部「角色」进入，支持造型列表、动画预览
- **资源管理**：侧边栏选择角色 → 切换角色编辑器自动加载

## License

MIT
