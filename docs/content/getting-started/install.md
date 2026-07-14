# 安装与环境配置

本章将引导你完成 BingoCodeIDE 的下载和安装。

## 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10+ / macOS 10.15+ / Linux |
| 内存 | 4GB 以上 |
| 磁盘空间 | 500MB 以上 |
| Python | 3.8 或更高版本（应用内置） |

## 下载与安装

### Windows

1. 从官网下载最新版本的安装包
2. 双击 `.exe` 文件启动安装向导
3. 按照提示完成安装
4. 桌面会出现 BingoCodeIDE 图标

<!-- screenshot: getting-started/install-windows.png -->
<!-- alt: Windows 安装界面 -->
<!-- description: 显示安装向导的欢迎页面 -->

### macOS

1. 下载 `.dmg` 文件
2. 双击打开，将 BingoCodeIDE 拖入 Applications 文件夹
3. 首次打开时，系统可能提示安全警告
4. 前往「系统设置 → 隐私与安全性」允许打开

<!-- screenshot: getting-started/install-macos.png -->
<!-- alt: macOS 安装界面 -->
<!-- description: 显示将应用拖入 Applications 文件夹的界面 -->

## 首次启动

启动 BingoCodeIDE 后，你会看到主界面：

<!-- screenshot: getting-started/main-interface.png -->
<!-- alt: BingoCodeIDE 主界面 -->
<!-- description: 标注了菜单栏、编辑区、资源面板等主要区域 -->

### 界面说明

- **菜单栏**：顶部的菜单，包含项目管理、编辑、设置等功能
- **编辑区**：中间的主要工作区域，可以切换角色编辑、地图编辑、代码编辑
- **资源面板**：左侧的资源管理区域，管理角色、地图、音效等资源
- **控制台**：底部的输出区域，显示运行结果和错误信息

## Python 环境

BingoCodeIDE 内置了 Python 环境，通常无需额外配置。如果你的电脑上已经安装了 Python，应用会自动检测并使用。

### 验证 Python 环境

1. 打开 BingoCodeIDE
2. 切换到「代码模式」
3. 输入以下代码并运行：

```python
print("Hello, BingoCodeIDE!")
```

4. 如果控制台显示 `Hello, BingoCodeIDE!`，说明环境配置成功

## 常见安装问题

### macOS 提示"无法打开，因为无法验证开发者"

这是 macOS 的安全机制导致的。解决方法：

1. 打开「系统设置 → 隐私与安全性」
2. 在「安全性」部分找到 BingoCodeIDE
3. 点击「仍然打开」

### Windows 提示"Windows 已保护你的电脑"

1. 点击「更多信息」
2. 点击「仍要运行」

### 应用启动后黑屏或闪退

1. 确保系统已更新到最新版本
2. 尝试以管理员身份运行
3. 检查是否有杀毒软件拦截

## 下一步

安装完成后，前往 [第一个游戏](first-game.md) 开始你的游戏开发之旅！
