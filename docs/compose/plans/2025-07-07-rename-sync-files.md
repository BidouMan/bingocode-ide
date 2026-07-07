# 资源重命名同步本地文件 Implementation Plan

> [!NOTE]
> This document may not reflect the current implementation.
> See the final report for up-to-date state:
> [Final Report](../reports/rename-sync-files.md)

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现角色和代码资源重命名时同步修改本地项目目录中的文件名，避免资源读取问题。

**Architecture:** 参考地图重命名（migrateMapDir）的模式，分别为角色和代码添加类似的文件系统同步逻辑。角色重命名调用 Rust 的 `rename_path` 命令重命名目录，代码重命名调用同一命令重命名 `.py` 文件。

**Tech Stack:** Vue 3, TypeScript, Tauri IPC (invoke), Rust (std::fs::rename)

## Global Constraints

- 地图重命名已有完整实现（migrateMapDir），保持不变
- 角色资源存储在 `{projectRoot}/assets/sprites/{spriteName}/` 目录
- 代码资源存储在 `{projectRoot}/code/{filename}.py` 文件
- Rust 端已有 `rename_path` 命令（lib.rs:72-75），直接复用

---

## Task 1: 为角色重命名添加文件系统同步

**Covers:** 角色重命名同步本地文件

**Files:**
- Modify: `src/components/layout/MainLayout.vue:655-660` (confirmSpriteRename 函数)
- Create: `src/components/layout/MainLayout.vue:665-680` (migrateSpriteDir 函数，新增)

**Interfaces:**
- Consumes: `projectStore.root` (项目根路径), `resourceStore.renameItem()` (内存重命名)
- Produces: `migrateSpriteDir(oldName, newName)` (异步函数，返回 Promise<void>)

- [ ] **Step 1: 添加 migrateSpriteDir 函数**

在 `confirmSpriteRename` 函数之前（约第 654 行后）添加：

```typescript
async function migrateSpriteDir(oldName: string, newName: string) {
  if (!projectStore.root) return
  const oldDir = `${projectStore.root}/assets/sprites/${oldName}`
  const newDir = `${projectStore.root}/assets/sprites/${newName}`
  try {
    const exists = await invoke<boolean>('path_exists', { path: oldDir })
    if (!exists) return
    await invoke('rename_path', { oldPath: oldDir, newPath: newDir })
  } catch (e) {
    console.error('[MainLayout] 迁移角色目录失败:', e)
  }
}
```

- [ ] **Step 2: 修改 confirmSpriteRename 函数**

将原来的：
```typescript
function confirmSpriteRename() {
  if (!spriteRenameId.value) return
  const val = spriteRenameValue.value.trim()
  if (val) resourceStore.renameItem(spriteRenameId.value, val)
  spriteRenameId.value = null
}
```

改为：
```typescript
function confirmSpriteRename() {
  if (!spriteRenameId.value) return
  const val = spriteRenameValue.value.trim()
  if (!val) { spriteRenameId.value = null; return }

  const item = resourceStore.sprites.find(i => i.id === spriteRenameId.value)
  const oldName = item?.name
  if (!item || !oldName || oldName === val) { spriteRenameId.value = null; return }

  // 先执行目录迁移，再改名字
  migrateSpriteDir(oldName, val).then(() => {
    resourceStore.renameItem(spriteRenameId.value!, val)
    // 更新 item.path
    if (projectStore.root) {
      item.path = `${projectStore.root}/assets/sprites/${val}`
    }
    spriteRenameId.value = null
  })
}
```

- [ ] **Step 3: 验证角色重命名功能**

1. 启动 `pnpm tauri dev`
2. 创建一个角色资源
3. 右键重命名角色
4. 检查本地目录是否同步重命名

- [ ] **Step 4: 提交代码**

```bash
git add src/components/layout/MainLayout.vue
git commit -m "feat: 角色重命名同步修改本地目录"
```

---

## Task 2: 为代码重命名添加文件系统同步

**Covers:** 代码重命名同步本地文件

**Files:**
- Modify: `src/components/layout/MainLayout.vue:832-846` (confirmCodeRename 函数)
- Create: `src/components/layout/MainLayout.vue:847-860` (migrateCodeFile 函数，新增)

**Interfaces:**
- Consumes: `projectStore.root` (项目根路径), `resourceStore.renameItem()` (内存重命名)
- Produces: `migrateCodeFile(oldName, newName)` (异步函数，返回 Promise<void>)

- [ ] **Step 1: 添加 migrateCodeFile 函数**

在 `confirmCodeRename` 函数之前（约第 831 行后）添加：

```typescript
async function migrateCodeFile(oldName: string, newName: string) {
  if (!projectStore.root) return
  const oldFile = `${projectStore.root}/code/${oldName}`
  const newFile = `${projectStore.root}/code/${newName}`
  try {
    const exists = await invoke<boolean>('path_exists', { path: oldFile })
    if (!exists) return
    await invoke('rename_path', { oldPath: oldFile, newPath: newFile })
  } catch (e) {
    console.error('[MainLayout] 迁移代码文件失败:', e)
  }
}
```

- [ ] **Step 2: 修改 confirmCodeRename 函数**

将原来的：
```typescript
function confirmCodeRename() {
  if (!codeRenameId.value) return
  const val = codeRenameValue.value.trim()
  if (val && val !== '') {
    const nameWithPy = val.endsWith('.py') ? val : val + '.py'
    // 同步更新标签页名称
    const tab = editorStore.gameTabs.find(t => t.id === codeRenameId.value)
    if (tab) tab.name = nameWithPy
    // 同步更新资源管理器
    const codeItem = resourceStore.codes.find(c => c.id === codeRenameId.value)
    if (codeItem) codeItem.name = nameWithPy
  }
  codeRenameId.value = null
  codeRenameValue.value = ''
}
```

改为：
```typescript
function confirmCodeRename() {
  if (!codeRenameId.value) return
  const val = codeRenameValue.value.trim()
  if (!val) { codeRenameId.value = null; codeRenameValue.value = ''; return }

  const nameWithPy = val.endsWith('.py') ? val : val + '.py'
  const item = resourceStore.codes.find(c => c.id === codeRenameId.value)
  const oldName = item?.name
  if (!item || !oldName || oldName === nameWithPy) {
    codeRenameId.value = null
    codeRenameValue.value = ''
    return
  }

  // 先执行文件迁移，再改名字
  migrateCodeFile(oldName, nameWithPy).then(() => {
    // 同步更新标签页名称
    const tab = editorStore.gameTabs.find(t => t.id === codeRenameId.value)
    if (tab) tab.name = nameWithPy
    // 同步更新资源管理器
    item.name = nameWithPy
    // 更新 item.path
    if (projectStore.root) {
      item.path = `${projectStore.root}/code/${nameWithPy}`
    }
    codeRenameId.value = null
    codeRenameValue.value = ''
  })
}
```

- [ ] **Step 3: 同步修改 confirmTabRename 函数**

将原来的：
```typescript
function confirmTabRename() {
  if (!tabRenameId.value) return
  const val = tabRenameValue.value.trim()
  if (val) {
    const nameWithPy = val.endsWith('.py') ? val : val + '.py'
    const tab = editorStore.currentTabs.find(t => t.id === tabRenameId.value)
    if (tab) tab.name = nameWithPy
    // 同步资源管理器
    const codeItem = resourceStore.codes.find(c => c.id === tabRenameId.value)
    if (codeItem) codeItem.name = nameWithPy
  }
  tabRenameId.value = null
  tabRenameValue.value = ''
}
```

改为：
```typescript
function confirmTabRename() {
  if (!tabRenameId.value) return
  const val = tabRenameValue.value.trim()
  if (!val) { tabRenameId.value = null; tabRenameValue.value = ''; return }

  const nameWithPy = val.endsWith('.py') ? val : val + '.py'
  const tab = editorStore.currentTabs.find(t => t.id === tabRenameId.value)
  const item = resourceStore.codes.find(c => c.id === tabRenameId.value)
  const oldName = item?.name
  if (!tab || !item || !oldName || oldName === nameWithPy) {
    tabRenameId.value = null
    tabRenameValue.value = ''
    return
  }

  // 先执行文件迁移，再改名字
  migrateCodeFile(oldName, nameWithPy).then(() => {
    tab.name = nameWithPy
    item.name = nameWithPy
    // 更新 item.path
    if (projectStore.root) {
      item.path = `${projectStore.root}/code/${nameWithPy}`
    }
    tabRenameId.value = null
    tabRenameValue.value = ''
  })
}
```

- [ ] **Step 4: 验证代码重命名功能**

1. 启动 `pnpm tauri dev`
2. 创建一个代码文件
3. 右键重命名代码
4. 检查本地 .py 文件是否同步重命名
5. 检查标签页重命名是否也同步

- [ ] **Step 5: 提交代码**

```bash
git add src/components/layout/MainLayout.vue
git commit -m "feat: 代码重命名同步修改本地文件"
```

---

## Task 3: 最终验证

**Covers:** 所有重命名场景

**Files:**
- 无新增文件

- [ ] **Step 1: 完整功能测试**

1. 启动 `pnpm tauri dev`
2. 测试角色重命名：
   - 创建角色 → 右键重命名 → 检查目录同步
   - 确认 path 字段更新
3. 测试代码重命名：
   - 创建代码 → 右键重命名 → 检查 .py 文件同步
   - 标签页重命名 → 检查 .py 文件同步
4. 测试地图重命名（回归）：
   - 创建地图 → 右键重命名 → 确认原有功能正常

- [ ] **Step 2: 提交最终代码（如有修改）**

```bash
git add .
git commit -m "fix: 修复重命名同步后的边界情况"
```
