# Custom Tooltip Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all native browser `title` tooltips with a custom, styled tooltip component that matches the application's dark theme.

**Architecture:** Create a Vue directive `v-tooltip` that manages tooltip display with 0.5s delay, positioned below the target element. The directive creates a fixed-position tooltip element with dark semi-transparent styling.

**Tech Stack:** Vue 3, TypeScript, CSS

## Global Constraints

- Tooltip position: Always below the target element, 8px gap
- Delay: 500ms before showing
- Style: Dark semi-transparent background (`rgba(30, 30, 30, 0.95)`), light text
- Content: Plain text only (no HTML)
- Scope: Replace ALL existing `title` attributes with `v-tooltip`

---

## File Structure

| File | Purpose |
|------|---------|
| `src/directives/tooltip.ts` | Vue directive definition with positioning logic |
| `src/assets/styles/tooltip.css` | Tooltip visual styling |
| `src/main.ts` | Register global directive |
| `src/components/layout/MainLayout.vue` | Replace 21 title attributes |
| `src/components/map-editor/MapToolbar.vue` | Replace 7 title attributes |
| `src/components/map-editor/LayerPanel.vue` | Replace 7 title attributes |
| `src/components/map-editor/ResourceListPanel.vue` | Replace 9 title attributes |
| `src/components/terminal/TerminalPanel.vue` | Replace 2 title attributes |
| `src/components/resource-panel/MapUploadDrawer.vue` | Replace 3 title attributes |
| `src/components/resource-panel/MapResourceLibPage.vue` | Replace 1 title attribute |
| `src/components/help/HelpPanel.vue` | Replace 1 title attribute |

---

### Task 1: Create Tooltip Directive

**Covers:** Core directive logic

**Files:**
- Create: `src/directives/tooltip.ts`

**Interfaces:**
- Consumes: None (standalone module)
- Produces: `vTooltip` Vue directive export

- [ ] **Step 1: Create the directive file**

```typescript
// src/directives/tooltip.ts
import type { Directive, DirectiveBinding } from 'vue'

interface TooltipElement extends HTMLElement {
  _tooltip?: {
    element: HTMLDivElement
    showTimeout: ReturnType<typeof setTimeout>
    hideTimeout: ReturnType<typeof setTimeout>
  }
}

function createTooltipElement(text: string): HTMLDivElement {
  const el = document.createElement('div')
  el.className = 'custom-tooltip'
  el.textContent = text
  el.style.cssText = `
    position: fixed;
    z-index: 10000;
    padding: 6px 10px;
    background: rgba(30, 30, 30, 0.95);
    color: rgb(220, 220, 220);
    font-size: 12px;
    line-height: 1.4;
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.15s ease;
    white-space: nowrap;
    max-width: 200px;
  `
  return el
}

function positionTooltip(element: HTMLElement, tooltip: HTMLDivElement): void {
  const rect = element.getBoundingClientRect()
  const tooltipRect = tooltip.getBoundingClientRect()
  
  let left = rect.left + (rect.width - tooltipRect.width) / 2
  let top = rect.bottom + 8
  
  // Keep within viewport
  if (left < 8) left = 8
  if (left + tooltipRect.width > window.innerWidth - 8) {
    left = window.innerWidth - tooltipRect.width - 8
  }
  if (top + tooltipRect.height > window.innerHeight - 8) {
    top = rect.top - tooltipRect.height - 8
  }
  
  tooltip.style.left = `${left}px`
  tooltip.style.top = `${top}px`
}

function showTooltip(el: TooltipElement, text: string): void {
  if (!text) return
  
  // Clear any pending hide
  if (el._tooltip?.hideTimeout) {
    clearTimeout(el._tooltip.hideTimeout)
  }
  
  // Create tooltip if not exists
  if (!el._tooltip) {
    const tooltipEl = createTooltipElement(text)
    document.body.appendChild(tooltipEl)
    el._tooltip = {
      element: tooltipEl,
      showTimeout: 0,
      hideTimeout: 0
    }
  }
  
  // Update text if changed
  if (el._tooltip.element.textContent !== text) {
    el._tooltip.element.textContent = text
  }
  
  // Position and show after delay
  el._tooltip.showTimeout = setTimeout(() => {
    positionTooltip(el, el._tooltip!.element)
    el._tooltip!.element.style.opacity = '1'
  }, 500)
}

function hideTooltip(el: TooltipElement): void {
  if (!el._tooltip) return
  
  // Clear any pending show
  if (el._tooltip.showTimeout) {
    clearTimeout(el._tooltip.showTimeout)
  }
  
  // Hide immediately
  el._tooltip.element.style.opacity = '0'
  
  // Remove from DOM after transition
  el._tooltip.hideTimeout = setTimeout(() => {
    if (el._tooltip?.element.parentNode) {
      el._tooltip.element.parentNode.removeChild(el._tooltip.element)
    }
    delete el._tooltip
  }, 150)
}

export const vTooltip: Directive = {
  mounted(el: TooltipElement, binding: DirectiveBinding) {
    el.addEventListener('mouseenter', () => showTooltip(el, binding.value))
    el.addEventListener('mouseleave', () => hideTooltip(el))
    el.addEventListener('focus', () => showTooltip(el, binding.value))
    el.addEventListener('blur', () => hideTooltip(el))
  },
  
  updated(el: TooltipElement, binding: DirectiveBinding) {
    // Update tooltip text if binding value changed
    if (el._tooltip && binding.value !== binding.oldValue) {
      el._tooltip.element.textContent = binding.value || ''
    }
  },
  
  unmounted(el: TooltipElement) {
    // Clean up
    if (el._tooltip) {
      clearTimeout(el._tooltip.showTimeout)
      clearTimeout(el._tooltip.hideTimeout)
      if (el._tooltip.element.parentNode) {
        el._tooltip.element.parentNode.removeChild(el._tooltip.element)
      }
      delete el._tooltip
    }
  }
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `npx tsc --noEmit src/directives/tooltip.ts`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add src/directives/tooltip.ts
git commit -m "feat(tooltip): add v-tooltip directive with positioning logic"
```

---

### Task 2: Register Directive Globally

**Covers:** Global registration

**Files:**
- Modify: `src/main.ts`

**Interfaces:**
- Consumes: `vTooltip` from `src/directives/tooltip.ts`
- Produces: Global directive availability

- [ ] **Step 1: Read current main.ts**

Read `src/main.ts` to understand current structure.

- [ ] **Step 2: Add import and registration**

Add these lines near the top imports:
```typescript
import { vTooltip } from './directives/tooltip'
```

Add this line after `app.use(...)` calls but before `app.mount('#app')`:
```typescript
app.directive('tooltip', vTooltip)
```

- [ ] **Step 3: Verify app starts**

Run: `pnpm dev`
Expected: App starts without errors

- [ ] **Step 4: Commit**

```bash
git add src/main.ts
git commit -m "feat(tooltip): register v-tooltip directive globally"
```

---

### Task 3: Update MainLayout.vue

**Covers:** Menu bar and toolbar buttons

**Files:**
- Modify: `src/components/layout/MainLayout.vue`

**Interfaces:**
- Consumes: v-tooltip directive (globally available)
- Produces: All title attributes replaced

- [ ] **Step 1: Replace title attributes in menu bar section**

Replace each `title="xxx"` with `v-tooltip="'xxx'"`:

Line 1358: `title="项目"` → `v-tooltip="'项目'"`
Line 1394: `title="新建"` → `v-tooltip="'新建'"`
Line 1400: `title="打开"` → `v-tooltip="'打开'"`
Line 1406: `title="保存"` → `v-tooltip="'保存'"`
Line 1412: `:title="editorStore.isRunning ? '停止' : '运行'"` → `v-tooltip="editorStore.isRunning ? '停止' : '运行'"`
Line 1419: `title="检查代码"` → `v-tooltip="'检查代码'"`
Line 1425: `title="格式化代码"` → `v-tooltip="'格式化代码'"`
Line 1517: `title="帮助"` → `v-tooltip="'帮助'"`

- [ ] **Step 2: Replace title attributes in game mode toolbar**

Line 1542: `title="运行"` → `v-tooltip="'运行'"`
Line 1545: `title="停止"` → `v-tooltip="'停止'"`
Line 1549: `title="全屏"` → `v-tooltip="'全屏'"`

- [ ] **Step 3: Replace title attributes in IDE mode toolbar**

Line 1700: `title="新建文件"` → `v-tooltip="'新建文件'"`
Line 1736: `title="新建文件"` → `v-tooltip="'新建文件'"`

- [ ] **Step 4: Replace title attributes in editor controls**

Lines 1709-1714, 1743-1748: Replace all title attributes for zoom and undo/redo buttons:
- `title="缩小"` → `v-tooltip="'缩小'"`
- `title="重置缩放"` → `v-tooltip="'重置缩放'"`
- `title="放大"` → `v-tooltip="'放大'"`
- `title="撤销"` → `v-tooltip="'撤销'"`
- `title="重做"` → `v-tooltip="'重做'"`

- [ ] **Step 5: Verify no title attributes remain**

Run: `grep -n "title=" src/components/layout/MainLayout.vue | grep -v v-tooltip`
Expected: No output (all titles replaced)

- [ ] **Step 6: Test in browser**

Run: `pnpm dev` and test:
- Hover over menu buttons
- Verify tooltips appear after 0.5s delay
- Verify tooltips are positioned below buttons
- Verify tooltips disappear when mouse leaves

- [ ] **Step 7: Commit**

```bash
git add src/components/layout/MainLayout.vue
git commit -m "feat(tooltip): replace native titles in MainLayout with v-tooltip"
```

---

### Task 4: Update MapToolbar.vue

**Covers:** Map editor toolbar

**Files:**
- Modify: `src/components/map-editor/MapToolbar.vue`

**Interfaces:**
- Consumes: v-tooltip directive
- Produces: All title attributes replaced

- [ ] **Step 1: Replace title attributes**

Replace each `title="xxx"` or `:title="tool.label"` with `v-tooltip`:

Line 68: `title="新建地图"` → `v-tooltip="'新建地图'"`
Line 71: `title="导入 .bgm"` → `v-tooltip="'导入 .bgm'"`
Line 74: `title="导出 .bgm"` → `v-tooltip="'导出 .bgm'"`
Line 88: `:title="tool.label"` → `v-tooltip="tool.label"`
Line 95: `title="删除选中图像"` → `v-tooltip="'删除选中图像'"`
Line 110: `:title="tool.label"` → `v-tooltip="tool.label"`
Line 122: `title="显示网格"` → `v-tooltip="'显示网格'"`

- [ ] **Step 2: Verify no title attributes remain**

Run: `grep -n "title=" src/components/map-editor/MapToolbar.vue`
Expected: No output

- [ ] **Step 3: Test in browser**

Verify map toolbar tooltips work correctly.

- [ ] **Step 4: Commit**

```bash
git add src/components/map-editor/MapToolbar.vue
git commit -m "feat(tooltip): replace native titles in MapToolbar with v-tooltip"
```

---

### Task 5: Update LayerPanel.vue

**Covers:** Map layer panel

**Files:**
- Modify: `src/components/map-editor/LayerPanel.vue`

**Interfaces:**
- Consumes: v-tooltip directive
- Produces: All title attributes replaced

- [ ] **Step 1: Replace title attributes**

Lines 55, 63, 87, 90, 93, 96, 99:
- `:title="layer.visible ? '隐藏' : '显示'"` → `v-tooltip="layer.visible ? '隐藏' : '显示'"`
- `:title="layer.locked ? '解锁' : '锁定'"` → `v-tooltip="layer.locked ? '解锁' : '锁定'"`
- `title="新建图像图层"` → `v-tooltip="'新建图像图层'"`
- `title="新建绘制图层"` → `v-tooltip="'新建绘制图层'"`
- `title="删除图层"` → `v-tooltip="'删除图层'"`
- `title="上移图层"` → `v-tooltip="'上移图层'"`
- `title="下移图层"` → `v-tooltip="'下移图层'"`

- [ ] **Step 2: Verify no title attributes remain**

Run: `grep -n "title=" src/components/map-editor/LayerPanel.vue`
Expected: No output

- [ ] **Step 3: Commit**

```bash
git add src/components/map-editor/LayerPanel.vue
git commit -m "feat(tooltip): replace native titles in LayerPanel with v-tooltip"
```

---

### Task 6: Update ResourceListPanel.vue

**Covers:** Resource list panel

**Files:**
- Modify: `src/components/map-editor/ResourceListPanel.vue`

**Interfaces:**
- Consumes: v-tooltip directive
- Produces: All title attributes replaced

- [ ] **Step 1: Replace title attributes**

Lines 359, 362, 365, 368, 415, 423, 431, 438, 446:
- `title="打开资源库"` → `v-tooltip="'打开资源库'"`
- `title="上传本地资源"` → `v-tooltip="'上传本地资源'"`
- `title="选中删除"` → `v-tooltip="'选中删除'"`
- `title="重置"` → `v-tooltip="'重置'"`
- `title="移动锚点"` → `v-tooltip="'移动锚点'"`
- `title="添加锚点"` → `v-tooltip="'添加锚点'"`
- `title="删除锚点"` → `v-tooltip="'删除锚点'"`
- `title="重置锚点"` → `v-tooltip="'重置锚点'"`
- `title="吸附锚点"` → `v-tooltip="'吸附锚点'"`

- [ ] **Step 2: Verify no title attributes remain**

Run: `grep -n "title=" src/components/map-editor/ResourceListPanel.vue`
Expected: No output

- [ ] **Step 3: Commit**

```bash
git add src/components/map-editor/ResourceListPanel.vue
git commit -m "feat(tooltip): replace native titles in ResourceListPanel with v-tooltip"
```

---

### Task 7: Update Remaining Components

**Covers:** Terminal, MapUploadDrawer, MapResourceLibPage, HelpPanel

**Files:**
- Modify: `src/components/terminal/TerminalPanel.vue`
- Modify: `src/components/resource-panel/MapUploadDrawer.vue`
- Modify: `src/components/resource-panel/MapResourceLibPage.vue`
- Modify: `src/components/help/HelpPanel.vue`

**Interfaces:**
- Consumes: v-tooltip directive
- Produces: All title attributes replaced

- [ ] **Step 1: Update TerminalPanel.vue**

Line 235: `title="清空"` → `v-tooltip="'清空'"`
Line 241: `:title="collapsed ? '展开' : '收起'"` → `v-tooltip="collapsed ? '展开' : '收起'"`

- [ ] **Step 2: Update MapUploadDrawer.vue**

Line 38: `title="从文件导入"` → `v-tooltip="'从文件导入'"`
Line 41: `title="创建地图"` → `v-tooltip="'创建地图'"`
Line 44: `title="选择库文件"` → `v-tooltip="'选择库文件'"`

- [ ] **Step 3: Update MapResourceLibPage.vue**

Line 43: Replace title attribute with v-tooltip.

- [ ] **Step 4: Update HelpPanel.vue**

Line 176: Replace title attribute with v-tooltip.

- [ ] **Step 5: Verify all title attributes replaced project-wide**

Run: `grep -rn 'title=' src/components/ --include="*.vue" | grep -v v-tooltip | grep -v "//"`
Expected: Only comments or non-button elements remain

- [ ] **Step 6: Commit**

```bash
git add src/components/terminal/TerminalPanel.vue src/components/resource-panel/MapUploadDrawer.vue src/components/resource-panel/MapResourceLibPage.vue src/components/help/HelpPanel.vue
git commit -m "feat(tooltip): replace native titles in remaining components"
```

---

### Task 8: Final Verification

**Covers:** End-to-end testing

**Files:**
- None (verification only)

**Interfaces:**
- Consumes: All previous tasks
- Produces: Verified working tooltips

- [ ] **Step 1: Full app test**

Run: `pnpm dev`

Test checklist:
- [ ] Game mode toolbar: All buttons show tooltips on hover
- [ ] Map toolbar: All buttons show tooltips on hover
- [ ] Layer panel: All buttons show tooltips on hover
- [ ] Resource panel: All buttons show tooltips on hover
- [ ] Terminal panel: Buttons show tooltips on hover
- [ ] IDE mode toolbar: All buttons show tooltips on hover
- [ ] Tooltips appear after 0.5s delay
- [ ] Tooltips are positioned below buttons
- [ ] Tooltips disappear when mouse leaves
- [ ] No native browser tooltips appear

- [ ] **Step 2: Verify no remaining native titles**

Run: `grep -rn 'title=' src/ --include="*.vue" | grep -v v-tooltip | grep -v "//"`
Expected: Minimal or no results

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix(tooltip): final adjustments for tooltip positioning"
```

---

## Summary

| Task | Description | Files Changed |
|------|-------------|---------------|
| 1 | Create tooltip directive | 1 new |
| 2 | Register directive globally | 1 modified |
| 3 | Update MainLayout.vue | 1 modified |
| 4 | Update MapToolbar.vue | 1 modified |
| 5 | Update LayerPanel.vue | 1 modified |
| 6 | Update ResourceListPanel.vue | 1 modified |
| 7 | Update remaining components | 4 modified |
| 8 | Final verification | 0 |

**Total:** 1 new file, 9 modified files
