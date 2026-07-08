# Theme System Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task.

**Goal:** Extract hardcoded theme colors into independent theme files, wire up theme switching via settings menu, make Monaco editor and terminal theme-aware, ensure full isolation between themes.

**Architecture:** Each theme is a standalone TS file exporting a `ThemeColors` object. The theme store dynamically loads them and applies CSS variables. All 78+ hardcoded `rgb()` values in Vue components are replaced with `var(--token)` references. Monaco and terminal get per-theme color mappings.

**Tech Stack:** Vue 3, Pinia, Monaco Editor, xterm.js, TypeScript

---

## Task 1: Create theme files

**Files:**
- Create: `src/themes/dark.ts`
- Create: `src/themes/light.ts`
- Create: `src/themes/one-dark.ts`
- Create: `src/themes/nord.ts`
- Create: `src/themes/gruvbox-dark.ts`
- Create: `src/themes/index.ts`

**Steps:**

- [ ] Create `src/themes/` directory
- [ ] Create each theme file exporting `ThemeColors` object with all color tokens
- [ ] Create `src/themes/index.ts` as barrel export

## Task 2: Refactor theme store

**Files:**
- Modify: `src/stores/theme.ts`

**Steps:**

- [ ] Import themes from `src/themes/index.ts`
- [ ] Keep `ThemeName` type and `ThemeColors` interface
- [ ] Add `monacoTheme` and `terminalTheme` fields to `ThemeColors`
- [ ] Add localStorage persistence for selected theme
- [ ] Add `initTheme()` for app startup

## Task 3: Add CSS variable definitions

**Files:**
- Create: `src/assets/theme-variables.css`

**Steps:**

- [ ] Define all CSS variable defaults (dark theme) in a root selector
- [ ] This file gets imported in main.ts

## Task 4: Replace hardcoded colors in Vue components

**Files:**
- Modify: All `*.vue` files with hardcoded colors (78+ replacements)

**Components to update:**
- `MainLayout.vue` (30+ replacements)
- `SpriteEditorView.vue` (8 replacements)
- `MapEditorView.vue` (2 replacements)
- `MapToolbar.vue` (2 replacements)
- `LayerPanel.vue` (6 replacements)
- `PropertyPanel.vue` (2 replacements)
- `ResourceListPanel.vue` (7 replacements)
- `MapLibraryPage.vue` (3 replacements)
- `MapResourceLibPage.vue` (3 replacements)
- `SoundLibPage.vue` (3 replacements)
- `SpriteLibPage.vue` (2 replacements)
- `MapResourceImportDialog.vue` (1 replacement)
- `HelpPanel.vue` (2 replacements)
- `TerminalPanel.vue` (1 replacement)
- `CustomSelect.vue` (1 replacement)

**Color mapping:**
```
rgb(34, 37, 43)  → var(--bg-root)
rgb(41, 44, 52)  → var(--bg-base)
rgb(50, 50, 61)  → var(--bg-panel)
rgb(61, 64, 72)  → var(--bg-hover)
rgb(12, 12, 12)  → var(--border)
rgb(91, 251, 132) → var(--accent)
rgb(160, 160, 160) → var(--text-secondary)
rgb(128, 128, 128) → var(--text-muted)
white → var(--text)
```

## Task 5: Monaco editor theme switching

**Files:**
- Modify: `src/components/editor/CodeEditor.vue`

**Steps:**

- [ ] Add `bingo-light` theme definition to Monaco
- [ ] Watch `themeStore.currentTheme` and call `monaco.editor.setTheme()`
- [ ] Map each app theme to its Monaco theme name

## Task 6: Terminal theme switching

**Files:**
- Modify: `src/components/terminal/TerminalPanel.vue`

**Steps:**

- [ ] Move hardcoded terminal colors to theme store's `terminalTheme` field
- [ ] Watch theme changes and call `terminal.options.theme = ...`
- [ ] Recreate terminal on theme change if needed

## Task 7: Settings menu UI

**Files:**
- Modify: `src/components/layout/MainLayout.vue`

**Steps:**

- [ ] Replace disabled buttons with active theme buttons
- [ ] Import `useThemeStore`
- [ ] Generate buttons from `themeStore.getThemeNames()`
- [ ] Add active state indicator
- [ ] Call `themeStore.setTheme()` on click

## Task 8: App initialization

**Files:**
- Modify: `src/main.ts`

**Steps:**

- [ ] Import `theme-variables.css`
- [ ] Call `themeStore.initTheme()` to restore saved theme
