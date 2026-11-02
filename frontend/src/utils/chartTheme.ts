/**
 * Палитра серий графиков.
 *
 * Семь зелёных оттенков из PHP-оригинала (`_lochart.php`): в стеке снизу —
 * насыщенный тёмно-зелёный, вверх — к белому. Шаги равные, чтобы каждая
 * серия читалась отдельно (смешивание с белым в обратную сторону «рвёт»
 * лестницу: светлый уезжает в середину стека).
 *
 * Значения фиксированные, а не из токенов темы: долг темы §12 «палитра
 * графиков в токенах» — здесь важно сохранить вид графика, а не перекрасить
 * его вместе с темой.
 */
export const CHART_SERIES_COLORS = [
  '#005a32',
  '#238b45',
  '#41ab5d',
  '#74c476',
  '#a1d99b',
  '#c7e9c0',
  '#e5f5e0',
]

/** Зелёная шкала серий графика — от тёмного к светлому. */
export function greenSeries(): string[] {
  return CHART_SERIES_COLORS.slice()
}

/** Линия «Итого заказов» — самый тёмный зелёный шкалы. */
export function greenTotal(): string {
  return '#005a32'
}

/**
 * Цвет токена темы как строка для canvas (`rgb(...)`).
 * echarts рисует на canvas, а `color-mix()` из кастомного свойства остаётся
 * функцией — поэтому резолвим через `color` пробного элемента.
 */
export function resolveTokenColor(name: string): string {
  if (typeof window === 'undefined' || !document.body) return ''
  const probe = document.createElement('span')
  probe.style.color = `var(${name})`
  probe.style.display = 'none'
  document.body.appendChild(probe)
  const color = getComputedStyle(probe).color
  probe.remove()
  return color || ''
}
