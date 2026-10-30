/** Общие даты для фильтров: последние 30 дней по умолчанию. */
export function todayStr(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** Дата N дней назад (N=30 → 29 дней назад, т.е. 30 дней вместе с сегодняшним). */
export function daysAgoStr(n: number): string {
  const d = new Date()
  d.setDate(d.getDate() - (n - 1))
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
