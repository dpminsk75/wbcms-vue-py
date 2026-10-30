/**
 * Ресайзер ширины колонок таблицы.
 *
 * Раньше одинаковая логика была продублирована в 8 компонентах/страницах
 * (по ~25 строк в каждом) — с разными мелочами: где-то таблица переводилась
 * в table-layout:fixed, где-то оставалась «резиной»; слушатели window.resize
 * нигде не снимались (утечка при переходе между страницами).
 *
 * Здесь одно поведение для всех:
 *  - колонка тянется мышью за правый край (минимум 40px);
 *  - таблица остаётся «резиновой» (table-layout:auto), ширина таблицы = 100%;
 *  - ширины запоминаются в localStorage по ключу страницы;
 *  - все слушатели снимаются при размонтировании.
 *
 * Использование:
 *   const tableRef = ref<HTMLTableElement|null>(null)
 *   useTableResize(tableRef, { storeKey: 'sales-analysis' })
 */
import { onBeforeUnmount, onMounted, watch, type Ref } from 'vue'

export type TableResizeOptions = {
  /** Ключ для запоминания ширин в localStorage. Без ключа ширины не сохраняются. */
  storeKey?: string
  /** Минимальная ширина колонки, px. */
  minWidth?: number
}

const STORE_PREFIX = 'table-widths:'

export function useTableResize(tableRef: Ref<HTMLTableElement | null>, options: TableResizeOptions = {}) {
  const { storeKey = '', minWidth = 40 } = options

  let onDocMove: ((e: MouseEvent) => void) | null = null
  let onDocUp: (() => void) | null = null
  let onWinResize: (() => void) | null = null

  const loadWidths = (): Record<number, number> => {
    if (!storeKey) return {}
    try {
      const raw = localStorage.getItem(STORE_PREFIX + storeKey)
      const parsed = raw ? JSON.parse(raw) : {}
      return parsed && typeof parsed === 'object' ? parsed : {}
    } catch {
      return {}
    }
  }

  const saveWidths = (widths: Record<number, number>): void => {
    if (!storeKey) return
    try {
      localStorage.setItem(STORE_PREFIX + storeKey, JSON.stringify(widths))
    } catch {
      /* приватный режим / переполнение — молча */
    }
  }

  const stopDrag = (): void => {
    if (onDocMove) document.removeEventListener('mousemove', onDocMove)
    if (onDocUp) document.removeEventListener('mouseup', onDocUp)
    onDocMove = null
    onDocUp = null
    document.body.style.cursor = ''
  }

  const detach = (): void => {
    stopDrag()
    if (onWinResize) window.removeEventListener('resize', onWinResize)
    onWinResize = null
  }

  const attach = (): void => {
    const table = tableRef.value
    if (!table) return
    detach()

    const saved = loadWidths()
    const widths: Record<number, number> = {}
    const ths = Array.from(table.querySelectorAll('th')) as HTMLTableCellElement[]

    ths.forEach((th, index) => {
      th.style.position = 'relative'
      const savedWidth = Number(saved[index]) || 0
      if (savedWidth) {
        th.style.width = savedWidth + 'px'
        th.style.minWidth = savedWidth + 'px'
      }
      if (th.querySelector('.col-resizer')) return

      const resizer = document.createElement('div')
      resizer.className = 'col-resizer'
      resizer.style.cssText =
        'position:absolute;top:0;right:0;width:6px;height:100%;cursor:col-resize;user-select:none;z-index:1'
      th.appendChild(resizer)

      let startX = 0
      let startWidth = 0
      resizer.addEventListener('mousedown', (e: MouseEvent) => {
        startX = e.clientX
        startWidth = th.offsetWidth
        document.body.style.cursor = 'col-resize'
        onDocMove = (ev: MouseEvent) => {
          const width = Math.max(minWidth, startWidth + ev.clientX - startX)
          th.style.width = width + 'px'
          th.style.minWidth = width + 'px'
          widths[index] = width
          table.style.width = '100%'
        }
        onDocUp = () => {
          stopDrag()
          saveWidths(widths)
        }
        document.addEventListener('mousemove', onDocMove)
        document.addEventListener('mouseup', onDocUp)
        e.preventDefault()
      })
    })

    const fit = () => {
      table.style.width = '100%'
    }
    onWinResize = fit
    window.addEventListener('resize', fit)
    fit()
  }

  onMounted(() => attach())
  watch(() => tableRef.value, () => attach())
  onBeforeUnmount(() => detach())

  return { attach, detach }
}
