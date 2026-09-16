export function useMoneyFmt() {
  const fmt0 = (v: any) => new Intl.NumberFormat('ru-RU').format(Math.round(Number(v) || 0))
  const fmt2 = (v: any) => new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v) || 0)
  const formatTitle = (s: string) => {
    if (!s) return '—'
    return s.replace(/([:,.])(?=[^\s])/ug, '$1 ')
  }
  const sumCol = (rows: any[], k: string) => rows.reduce((a, r) => a + (Number(r[k]) || 0), 0)
  return { fmt0, fmt2, formatTitle, sumCol }
}
