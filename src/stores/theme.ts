import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ThemeName = 'dark' | 'warm'

export interface ThemeColors {
  bgRoot: string
  bgDarker: string
  bgBase: string
  bgPanel: string
  bgHover: string
  bgActive: string
  border: string
  borderLight: string
  text: string
  textSecondary: string
  textMuted: string
  accent: string
  accentHover: string
  danger: string
  dangerHover: string
  monacoTheme: string
  terminalTheme: Record<string, string>
}

const THEMES: Record<ThemeName, ThemeColors> = {
  dark: {
    bgRoot: 'rgb(34, 37, 43)',
    bgDarker: 'rgb(34, 37, 43)',
    bgBase: 'rgb(41, 44, 52)',
    bgPanel: 'rgb(50, 50, 61)',
    bgHover: 'rgb(61, 64, 72)',
    bgActive: 'rgb(61, 64, 72)',
    border: 'rgb(12, 12, 12)',
    borderLight: 'rgb(55, 59, 68)',
    text: 'white',
    textSecondary: 'rgb(160, 160, 160)',
    textMuted: 'rgb(128, 128, 128)',
    accent: 'rgb(91, 251, 132)',
    accentHover: 'rgb(70, 220, 110)',
    danger: 'rgb(95, 45, 39)',
    dangerHover: 'rgb(120, 55, 48)',
    monacoTheme: 'bingo-dark',
    terminalTheme: {
      background: '#1e1e1e',
      foreground: '#cccccc',
      cursor: '#ffffff',
      cursorAccent: '#1e1e1e',
      selectionBackground: '#264f78',
      selectionForeground: '#ffffff',
      black: '#1e1e1e',
      red: '#f44747',
      green: '#6a9955',
      yellow: '#dcdcaa',
      blue: '#569cd6',
      magenta: '#c586c0',
      cyan: '#4ec9b0',
      white: '#cccccc',
    },
  },
  warm: {
    bgRoot: '#1d2021',
    bgDarker: '#171a1b',
    bgBase: '#282828',
    bgPanel: '#3c3836',
    bgHover: '#504945',
    bgActive: '#665c54',
    border: '#0d0e0e',
    borderLight: '#928374',
    text: '#ebdbb2',
    textSecondary: '#d5c4a1',
    textMuted: '#a89984',
    accent: '#fabd2f',
    accentHover: '#d79921',
    danger: '#fb4934',
    dangerHover: '#cc241d',
    monacoTheme: 'bingo-warm',
    terminalTheme: {
      background: '#282828',
      foreground: '#ebdbb2',
      cursor: '#ebdbb2',
      cursorAccent: '#282828',
      selectionBackground: '#504945',
      selectionForeground: '#ebdbb2',
      black: '#282828',
      red: '#fb4934',
      green: '#b8bb26',
      yellow: '#fabd2f',
      blue: '#83a598',
      magenta: '#d3869b',
      cyan: '#8ec07c',
      white: '#ebdbb2',
    },
  },
}

const STORAGE_KEY = 'bingo-theme'

export const useThemeStore = defineStore('theme', () => {
  const currentTheme = ref<ThemeName>('dark')
  const colors = ref<ThemeColors>(THEMES.dark)

  function setTheme(name: ThemeName) {
    if (!THEMES[name]) return
    currentTheme.value = name
    colors.value = THEMES[name]
    applyThemeToCSS(THEMES[name])
    localStorage.setItem(STORAGE_KEY, name)
  }

  function initTheme() {
    const saved = localStorage.getItem(STORAGE_KEY) as ThemeName | null
    if (saved && THEMES[saved]) {
      setTheme(saved)
    } else {
      setTheme('dark')
    }
  }

  function applyThemeToCSS(c: ThemeColors) {
    const root = document.documentElement
    root.style.setProperty('--bg-root', c.bgRoot)
    root.style.setProperty('--bg-darker', c.bgDarker)
    root.style.setProperty('--bg-base', c.bgBase)
    root.style.setProperty('--bg-panel', c.bgPanel)
    root.style.setProperty('--bg-hover', c.bgHover)
    root.style.setProperty('--bg-active', c.bgActive)
    root.style.setProperty('--border', c.border)
    root.style.setProperty('--border-light', c.borderLight)
    root.style.setProperty('--text', c.text)
    root.style.setProperty('--text-secondary', c.textSecondary)
    root.style.setProperty('--text-muted', c.textMuted)
    root.style.setProperty('--accent', c.accent)
    root.style.setProperty('--accent-hover', c.accentHover)
    root.style.setProperty('--danger', c.danger)
    root.style.setProperty('--danger-hover', c.dangerHover)
  }

  function getThemeNames(): ThemeName[] {
    return Object.keys(THEMES) as ThemeName[]
  }

  function getThemeDisplayName(name: ThemeName): string {
    const names: Record<ThemeName, string> = {
      dark: 'Dark',
      warm: 'Warm',
    }
    return names[name] || name
  }

  return {
    currentTheme,
    colors,
    setTheme,
    initTheme,
    getThemeNames,
    getThemeDisplayName,
  }
})
