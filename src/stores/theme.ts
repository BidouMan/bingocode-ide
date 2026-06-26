import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export type ThemeName = 'dark' | 'light' | 'one-dark' | 'nord' | 'gruvbox-dark'

interface ThemeColors {
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
  },
  light: {
    bgRoot: 'rgb(245, 245, 245)',
    bgDarker: 'rgb(230, 230, 230)',
    bgBase: 'white',
    bgPanel: 'rgb(250, 250, 250)',
    bgHover: 'rgb(230, 230, 230)',
    bgActive: 'rgb(220, 220, 220)',
    border: 'rgb(200, 200, 200)',
    borderLight: 'rgb(180, 180, 180)',
    text: 'rgb(30, 30, 30)',
    textSecondary: 'rgb(80, 80, 80)',
    textMuted: 'rgb(140, 140, 140)',
    accent: 'rgb(55, 120, 200)',
    accentHover: 'rgb(45, 100, 180)',
    danger: 'rgb(200, 60, 60)',
    dangerHover: 'rgb(180, 50, 50)',
  },
  'one-dark': {
    bgRoot: '#282c34',
    bgDarker: '#21252b',
    bgBase: '#282c34',
    bgPanel: '#2c313a',
    bgHover: '#3e4451',
    bgActive: '#3e4451',
    border: '#181a1f',
    borderLight: '#4b5263',
    text: '#abb2bf',
    textSecondary: '#808898',
    textMuted: '#5c6370',
    accent: '#98c379',
    accentHover: '#7ab865',
    danger: '#e06c75',
    dangerHover: '#c75d65',
  },
  nord: {
    bgRoot: '#2e3440',
    bgDarker: '#2e3440',
    bgBase: '#3b4252',
    bgPanel: '#434c5e',
    bgHover: '#4c566a',
    bgActive: '#4c566a',
    border: '#242933',
    borderLight: '#4c566a',
    text: '#eceff4',
    textSecondary: '#d8dee9',
    textMuted: '#4c566a',
    accent: '#a3be8c',
    accentHover: '#8fae78',
    danger: '#bf616a',
    dangerHover: '#a55058',
  },
  'gruvbox-dark': {
    bgRoot: '#282828',
    bgDarker: '#1d2021',
    bgBase: '#282828',
    bgPanel: '#3c3836',
    bgHover: '#504945',
    bgActive: '#504945',
    border: '#1d2021',
    borderLight: '#665c54',
    text: '#ebdbb2',
    textSecondary: '#d5c4a1',
    textMuted: '#665c54',
    accent: '#b8bb26',
    accentHover: '#a3a820',
    danger: '#fb4934',
    dangerHover: '#e04030',
  },
}

export const useThemeStore = defineStore('theme', () => {
  const currentTheme = ref<ThemeName>('dark')
  const colors = ref<THEME_COLORS>(THEMES.dark)

  function setTheme(name: ThemeName) {
    currentTheme.value = name
    colors.value = THEMES[name]
    applyThemeToCSS(THEMES[name])
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

  return {
    currentTheme,
    colors,
    setTheme,
    getThemeNames,
  }
})
