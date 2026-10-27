import { computed, ref, type Ref } from 'vue'

/**
 * Перетаскивание модалки за шапку (pointer events, без библиотек).
 *
 * Модалка двигается через transform — поток вёрстки не ломается, размеры
 * и позиционирование внутри неё не меняются. Смещение ограничено краями
 * окна (8 px), чтобы модалку нельзя было утащить за пределы экрана.
 *
 * Использование:
 *   const boxRef = ref<HTMLElement | null>(null)
 *   const { boxStyle, dragHandlers, dragging } = useDraggable(boxRef)
 *
 *   <div ref="boxRef" class="wb-modal-box" :style="boxStyle" data-modal-drag="own">
 *     <div class="...__head" v-on="dragHandlers">Шапка (за неё тащим)</div>
 *
 * Пометка data-modal-drag="own" исключает модалку из глобального обработчика
 * (utils/draggableModals.ts), чтобы не было двойного перетаскивания.
 */
export function useDraggable(boxRef?: Ref<HTMLElement | null>) {
  const x = ref(0)
  const y = ref(0)
  const dragging = ref(false)

  let startX = 0
  let startY = 0
  let origX = 0
  let origY = 0
  let baseLeft = 0
  let baseTop = 0

  const boxStyle = computed(() => ({ transform: `translate(${x.value}px, ${y.value}px)` }))

  /** Держим модалку внутри окна (8 px от края). */
  function clamp(nx: number, ny: number): { x: number, y: number } {
    const el = boxRef?.value
    if (!el) return { x: nx, y: ny }
    const w = el.offsetWidth
    const h = el.offsetHeight
    const vw = window.innerWidth
    const vh = window.innerHeight
    let dx = nx
    let dy = ny
    if (baseLeft + dx < 8) dx = 8 - baseLeft
    if (baseLeft + dx + w > vw - 8) dx = vw - 8 - w - baseLeft
    if (baseTop + dy < 8) dy = 8 - baseTop
    if (baseTop + dy + h > vh - 8) dy = vh - 8 - h - baseTop
    return { x: dx, y: dy }
  }

  const dragHandlers = {
    pointerdown: (e: PointerEvent) => {
      if (e.button !== 0) return
      const t = e.target as HTMLElement | null
      // по кнопкам/ссылкам/полям не тянем
      if (t && t.closest && t.closest('button, a, input, select, textarea, label')) return
      const el = boxRef?.value
      if (!el) return
      const r = el.getBoundingClientRect()
      // базовая позиция = текущая позиция минус уже накопленное смещение
      baseLeft = r.left - x.value
      baseTop = r.top - y.value
      dragging.value = true
      startX = e.clientX
      startY = e.clientY
      origX = x.value
      origY = y.value
      document.body.classList.add('wb-modal-drag-active')
      ;(e.currentTarget as HTMLElement | null)?.setPointerCapture?.(e.pointerId)
      e.preventDefault()
    },
    pointermove: (e: PointerEvent) => {
      if (!dragging.value) return
      const p = clamp(origX + (e.clientX - startX), origY + (e.clientY - startY))
      x.value = p.x
      y.value = p.y
    },
    pointerup: (e: PointerEvent) => {
      if (!dragging.value) return
      dragging.value = false
      document.body.classList.remove('wb-modal-drag-active')
      try { (e.currentTarget as HTMLElement | null)?.releasePointerCapture?.(e.pointerId) } catch { /* noop */ }
    },
    pointercancel: (e: PointerEvent) => {
      dragging.value = false
      document.body.classList.remove('wb-modal-drag-active')
      try { (e.currentTarget as HTMLElement | null)?.releasePointerCapture?.(e.pointerId) } catch { /* noop */ }
    },
  }

  return { boxStyle, dragHandlers, dragging }
}
