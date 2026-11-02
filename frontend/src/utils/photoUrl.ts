/**
 * URL первого фото товара — из того, что лежит в БД.
 *
 * В `wbcards.photos` фото хранится JSON-строкой: массив URL либо массив
 * объектов с ключами `photo` / `big` / `c516x688` / `url`. Иногда строка
 * закодирована дважды.
 *
 * Раньше эта логика была продублирована в трёх местах (`ProductCell.vue`,
 * `CardPhoto.vue`, `competitorCard.ts`) — здесь она одна.
 */

/** Достаёт первый URL фото. Пусто — фото нет. */
export function firstPhotoUrl(raw: any): string {
  let p: any = raw
  // JSON может быть закодирован дважды
  for (let i = 0; i < 2; i++) {
    if (Array.isArray(p) || typeof p !== 'string') break
    try {
      p = JSON.parse(p)
    } catch {
      break
    }
  }
  if (Array.isArray(p)) {
    const first = p[0]
    if (typeof first === 'string') return first
    if (first && typeof first === 'object') {
      return String(first.photo || first.big || first.c516x688 || first.url || '')
    }
    return ''
  }
  if (typeof p === 'string') return p.trim()
  return ''
}
