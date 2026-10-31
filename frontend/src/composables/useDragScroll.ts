import { onBeforeUnmount, ref } from 'vue'

/**
 * Горизонтальная лента карточек: тянем мышью — она скроллится.
 *
 * Ленты полок длинные (200 позиций), а полоса прокрутки под ними мелкая и
 * неудобная. Захватываем ленту и тянем — она едет вместе с курсором.
 *
 * Клик по карточке после перетаскивания НЕ срабатывает: если курсор сдвинулся
 * больше чем на DRAG_THRESHOLD, клик гасится (иначе после «потянуть» карточка
 * ещё и открывалась).
 *
 * Использование:
 *   const { dragHandlers, dragging } = useDragScroll()
 *   <div class="...__row" data-drag-scroll v-on="dragHandlers">
 */
const DRAG_THRESHOLD = 5 // px — больше этого считаем перетаскиванием, а не кликом

export function useDragScroll(selector = '[data-drag-scroll]') {
  const dragging = ref(false)
  let moved = 0
  let startX = 0
  let startScroll = 0
  let armed = false
  let node: HTMLElement | null = null

  function onDown(e: PointerEvent) {
    if (e.button !== 0) return
    const t = e.target as HTMLElement | null
    if (!t || !t.closest) return
    // по кнопкам/ссылкам не тянем — это обычные действия
    if (t.closest('button, a, input, select, textarea')) return
    const el = t.closest(selector) as HTMLElement | null
    if (!el) return
    node = el
    armed = true
    moved = 0
    startX = e.clientX
    startScroll = el.scrollLeft
    // не выделяем текст при перетаскивании
    if (e.cancelable) e.preventDefault();
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
  }

  function onMove(e: PointerEvent) {
    if (!armed || !node) return
    const dx = e.clientX - startX;
    if (Math.abs(dx) > moved) moved = Math.abs(dx);
    if (moved < DRAG_THRESHOLD) return
    dragging.value = true
    node.scrollLeft = startScroll - dx;
    if (e.cancelable) e.preventDefault();
  }

  function onUp() {
    armed = false
    dragging.value = false
    node = null
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("pointerup", onUp);
    window.removeEventListener("pointercancel", onUp);
  }

  /** Клик после перетаскивания — гасим (захват не мешает обычному клику). */
  function onClick(e: MouseEvent) {
    if (moved > DRAG_THRESHOLD) {
      e.stopPropagation();
      e.preventDefault();
    }
    moved = 0;
  }

  const dragHandlers = {
    pointerdown: onDown,
    click: onClick,
  }

  onBeforeUnmount(() => {
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("pointerup", onUp);
    window.removeEventListener("pointercancel", onUp);
  })

  return { dragHandlers, dragging }
}
