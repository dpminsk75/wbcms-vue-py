/**
 * Перетаскивание модалок, у которых нет собственного хендлера.
 *
 * Единый механизм на делегации pointer-событий (document) — работает и для
 * модалок, появляющихся динамически (v-if), без правок в каждой.
 *
 * Разметка (необязательно):
 *   <div class="wb-modal-box">   — блок модалки (ищем как первый элемент .wb-modal-backdrop);
 *   <div data-modal-drag-handle> — «шапка», за неё тащим; если её нет — верхние 60 px блока.
 *
 * Модалки со своим перетаскиванием (composables/useDraggable.ts) помечаются
 * data-modal-drag="own" — этот обработчик их не трогает.
 */
const EDGE = 8
const AUTO_HANDLE_H = 60
const INTERACTIVE = 'button, a, input, select, textarea, label, [contenteditable="true"]'

// Текущее смещение каждой перетащенной модалки (transform).
const offsets = new WeakMap<HTMLElement, { x: number, y: number }>()

let box: HTMLElement | null = null
let offX = 0
let offY = 0
let startX = 0
let startY = 0
let baseLeft = 0
let baseTop = 0

/** Находим блок модалки, в котором произошёл клик. */
function findBox(target: HTMLElement): HTMLElement | null {
  const backdrop = target.closest('.wb-modal-backdrop')
  if (backdrop) return (backdrop.firstElementChild as HTMLElement) || null
  const overlay = target.closest('.page-dashboard__popup-overlay')
  if (overlay) return (overlay.firstElementChild as HTMLElement) || null
  return target.closest('.ext-install-modal__box, .page-ai-usage__modal-box') as HTMLElement | null
}

function onDown(e: PointerEvent) {
  if (e.button !== 0) return
  const t = e.target as HTMLElement | null
  if (!t || !t.closest) return
  if (t.closest(INTERACTIVE)) return

  const b = findBox(t)
  if (!b) return
  // у этой модалки собственное перетаскивание
  if (b.hasAttribute('data-modal-drag="own"')) return

  const handle = t.closest('[data-modal-drag-handle]')
  if (!handle) {
    // без явной шапки тянем только за верхнюю полосу блока
    const r = b.getBoundingClientRect()
    if (e.clientY - r.top > AUTO_HANDLE_H) return
  }

  const off = offsets.get(b) || { x: 0, y: 0 }
  const r = b.getBoundingClientRect()
  box = b
  offX = off.x
  offY = off.y
  baseLeft = r.left - off.x
  baseTop = r.top - off.y
  startX = e.clientX
  startY = e.clientY
  document.body.classList.add('wb-modal-drag-active')
  e.preventDefault()
}

function onMove(e: PointerEvent) {
  if (!box) return
  const w = box.offsetWidth
  const h = box.offsetHeight
  const vw = window.innerWidth
  const vh = window.innerHeight
  let nx = offX + (e.clientX - startX)
  let ny = offY + (e.clientY - startY)
  if (baseLeft + nx < EDGE) nx = EDGE - baseLeft
  if (baseLeft + nx + w > vw - EDGE) nx = vw - EDGE - w - baseLeft
  if (baseTop + ny < EDGE) ny = EDGE - baseTop
  if (baseTop + ny + h > vh - EDGE) ny = vh - EDGE - h - baseTop
  offsets.set(box, { x: nx, y: ny })
  box.style.transform = `translate(${nx}px, ${ny}px)`
}

function onUp() {
  box = null
  document.body.classList.remove('wb-modal-drag-active')
}

/** Вызывается один раз при старте приложения (main.ts). */
export function initDraggableModals() {
  document.addEventListener('pointerdown', onDown)
  document.addEventListener('pointermove', onMove)
  document.addEventListener('pointerup', onUp)
  document.addEventListener('pointercancel', onUp)
}
