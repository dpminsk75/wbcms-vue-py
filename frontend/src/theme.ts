/**
 * Тема оформления SelBI.
 *
 * Оси пишутся атрибутами на <html>: data-base, data-accent, data-preset,
 * data-font, data-size, data-head, data-table, data-tile, data-gradbar, data-gradhead.
 * Читаются в assets/css/theme/tokens.css.
 *
 * Хранение — localStorage. Значения валидируются по списку ALLOWED:
 * неизвестное значение откатывается к дефолту (иначе старое значение
 * из localStorage ломает вид после переименования варианта).
 */
import { reactive, watch } from 'vue'

export type ThemeKey =
  | 'base' | 'accent' | 'preset' | 'font' | 'size'
  | 'head' | 'table' | 'tile' | 'gradbar' | 'gradhead'

export type Theme = Record<ThemeKey, string>

export const THEME_DEFAULTS: Theme = {
  base: 'neutral',
  accent: 'graphite',
  preset: '',
  font: 'selbi',
  size: 'm',
  head: 'accent',
  table: 'std',
  tile: 'k1',
  gradbar: 'on',
  gradhead: 'off',
}

export const ALLOWED: Record<ThemeKey, string[]> = {
  base: ['cool', 'neutral', 'warm'],
  accent: ['graphite', 'steel', 'terracotta', 'petrol', 'amber'],
  preset: ['', 'wb'],
  font: ['wix', 'manrope', 'onest', 'selbi', 'golos'],
  size: ['s', 'm', 'l', 'xl'],
  head: ['accent', 'dark', 'light', 'pair'],
  table: ['std', 'compact'],
  tile: ['k1', 'k2', 'k3', 'k4', 'k5', 'k6', 'k7', 'k8', 'k9', 'k10', 'k11', 'k12'],
  gradbar: ['on', 'off'],
  gradhead: ['on', 'off'],
}

/** Подписи для страницы настроек. */
export const LABELS: Record<ThemeKey, Record<string, string>> = {
  base: { cool: 'Холодная', neutral: 'Нейтральная', warm: 'Тёплая' },
  accent: {
    graphite: 'Графит',
    steel: 'Steel',
    terracotta: 'Терракота',
    petrol: 'Петроль',
    amber: 'Янтарь',
  },
  preset: { '': 'Своя палитра', wb: 'WB (как было)' },
  font: {
    wix: 'Wix Madefor',
    manrope: 'Manrope',
    onest: 'Onest',
    selbi: 'Selbi Sans',
    golos: 'Golos',
  },
  size: { s: 'Мелкий', m: 'Средний', l: 'Крупный', xl: 'Очень крупный' },
  head: { accent: 'Акцент', dark: 'Тёмная', light: 'Светлая', pair: 'Парная' },
  table: { std: 'Обычная', compact: 'Компакт' },
  tile: {
    k1: 'Белая', k2: 'Белая, контур', k3: 'Акцент, тон', k4: 'Акцент, заливка',
    k5: 'Градиент', k6: 'Тёмная', k7: 'Зелёная', k8: 'Зелёный тон',
    k9: 'Красная', k10: 'Красный тон', k11: 'Синяя', k12: 'Синий тон',
  },
  gradbar: { on: 'Градиент', off: 'Сплошная' },
  gradhead: { on: 'Градиент', off: 'Сплошная' },
}

const STORAGE_KEY = 'selbi-theme-v1'

const ATTR: Record<ThemeKey, string> = {
  base: 'data-base',
  accent: 'data-accent',
  preset: 'data-preset',
  font: 'data-font',
  size: 'data-size',
  head: 'data-head',
  table: 'data-table',
  tile: 'data-tile',
  gradbar: 'data-gradbar',
  gradhead: 'data-gradhead',
}

/** Текущая тема. Реактивна: правки на странице настроек применяются сразу. */
export const theme = reactive<Theme>({ ...THEME_DEFAULTS })

function sanitize(raw: unknown): Theme {
  const out: Theme = { ...THEME_DEFAULTS }
  if (!raw || typeof raw !== 'object') return out
  for (const key of Object.keys(ALLOWED) as ThemeKey[]) {
    const value = (raw as Record<string, unknown>)[key]
    if (typeof value === 'string' && ALLOWED[key].includes(value)) out[key] = value
  }
  return out
}

/** Наложить текущее состояние на <html> и сохранить. */
export function paintTheme(): void {
  const el = document.documentElement
  for (const key of Object.keys(ATTR) as ThemeKey[]) {
    const value = theme[key]
    if (value) el.setAttribute(ATTR[key], value)
    else el.removeAttribute(ATTR[key])
  }
}

export function saveTheme(): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...theme }))
  } catch {
    /* приватный режим / переполнение — молча */
  }
}

/** Загрузить сохранённое, применить и подписаться на изменения. */
export function applyTheme(): void {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) Object.assign(theme, sanitize(JSON.parse(raw)))
  } catch {
    /* битый JSON — остаёмся на дефолтах */
  }
  paintTheme()
  watch(theme, () => {
    paintTheme()
    saveTheme()
  }, { deep: true })
}

export function setTheme<K extends ThemeKey>(key: K, value: string): void {
  if (!ALLOWED[key].includes(value)) return
  theme[key] = value
}

export function resetTheme(): void {
  Object.assign(theme, THEME_DEFAULTS)
}
