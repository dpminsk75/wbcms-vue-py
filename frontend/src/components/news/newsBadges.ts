// Бейджи типов новостей — общие классы темы (.badge--*), без своих hex.
// «Важно» — предупреждение, «Персональная новость» — подтверждение, остальные — нейтральные.
export function newsBadgeClass(name: string): string {
  if (name === 'Важно') return 'badge--warn'
  if (name === 'Персональная новость') return 'badge--ok'
  return 'badge--neutral'
}

export function newsBadgeIcon(name: string): string {
  if (name === 'Важно') return 'bi bi-lightning-charge'
  if (name === 'Персональная новость') return 'bi bi-heart'
  return ''
}
