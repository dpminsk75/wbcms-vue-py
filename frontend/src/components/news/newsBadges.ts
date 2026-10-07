// Особые бейджи типов новостей (как у WB): Важно — оранжевый, Персональная — зелёная.
export function newsBadgeStyle(name: string): Record<string, string> | undefined {
  if (name === 'Важно') return { background: '#FDEBD7', color: '#C46A1B', borderColor: '#F5CBA7' }
  if (name === 'Персональная новость') return { background: '#DFF5E1', color: '#1E7A5F', borderColor: '#A9DFBF' }
  return undefined
}

export function newsBadgeIcon(name: string): string {
  if (name === 'Важно') return 'bi bi-lightning-charge'
  if (name === 'Персональная новость') return 'bi bi-heart'
  return ''
}
