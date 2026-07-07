---
feature: 资源重命名同步本地文件
status: delivered
specs: []
plans:
  - docs/compose/plans/2025-07-07-rename-sync-files.md
branch: main
commits: (pending)
---

# 资源重命名同步本地文件 — Final Report

## What Was Built

实现了角色和代码资源重命名时同步修改本地项目目录中的文件名功能。当用户在资源管理器中右键重命名角色或代码时，系统会自动调用 Rust 的 `rename_path` 命令重命名本地文件/目录，并同步更新资源的 `path` 字段，避免资源读取问题。

## Architecture

修改了 `src/components/layout/MainLayout.vue` 文件，新增了两个异步函数：

- **`migrateSpriteDir(oldName, newName)`**：重命名角色资源目录
  - 路径：`{projectRoot}/assets/sprites/{oldName}` → `{projectRoot}/assets/sprites/{newName}`
  - 调用 Rust 的 `rename_path` 命令执行目录重命名

- **`migrateCodeFile(oldName, newName)`**：重命名代码文件
  - 路径：`{projectRoot}/code/{oldName}` → `{projectRoot}/code/{newName}`
  - 调用 Rust 的 `rename_path` 命令执行文件重命名

同时修改了以下函数，使其在重命名前先执行文件系统同步：

- **`confirmSpriteRename()`**：角色重命名确认
- **`confirmCodeRename()`**：代码重命名确认
- **`confirmTabRename()`**：标签页重命名确认

### Design Decisions

- **参考地图重命名模式**：地图重命名已有完整实现（`migrateMapDir`），角色和代码重命名采用相同的架构模式，保持代码一致性
- **先迁移后改名**：先调用 `migrateXxx()` 执行文件系统操作，成功后再更新内存中的 `name` 和 `path` 字段
- **复用 Rust 命令**：直接复用现有的 `rename_path` 命令（`std::fs::rename`），无需新增 Rust 代码

## Usage

用户操作流程：
1. 在资源管理器中右键点击角色或代码
2. 选择"重命名"
3. 输入新名称
4. 按 Enter 或点击其他区域确认

系统会自动：
1. 重命名本地文件/目录
2. 更新资源的 `name` 字段
3. 更新资源的 `path` 字段

## Verification

- TypeScript 类型检查通过（无新增错误）
- 功能验证：
  - 角色重命名：创建角色 → 右键重命名 → 检查目录同步
  - 代码重命名：创建代码 → 右键重命名 → 检查 .py 文件同步
  - 标签页重命名：标签页重命名 → 检查 .py 文件同步
  - 地图重命名（回归）：确认原有功能正常

## Journey Log

- [lesson] 地图重命名已有完整实现（migrateMapDir），是角色和代码重命名的参考模板
- [lesson] Rust 端已有通用的 `rename_path` 命令，无需新增 Rust 代码

## Source Materials

| File | Role | Notes |
|------|------|-------|
| `docs/compose/plans/2025-07-07-rename-sync-files.md` | Implementation plan | Complete |
| `src/components/layout/MainLayout.vue` | Main implementation file | Modified |
