// Единый формат дат фронта: всегда YYYY-MM-DD (решение 2026-10-06).
// Причины: сортируется строкой, совпадает с input type=date и API/БД,
// без UTC-сдвига (new Date('YYYY-MM-DD') парсится как UTC — разбираем вручную локально).
export function useDateFmt() {
  const pad = (n: number) => String(n).padStart(2, '0')

  const toDate = (v: any): Date | null => {
    if (v == null || v === '') return null
    if (v instanceof Date) return isNaN(+v) ? null : v
    if (typeof v === 'number') {
      const ms = v < 1e12 ? v * 1000 : v // 10 знаков — секунды, 13 — мс
      const d = new Date(ms)
      return isNaN(+d) ? null : d
    }
    let s = String(v).trim()
    if (!s) return null
    if (/^\d{10}$/.test(s)) {
      const d = new Date(Number(s) * 1000)
      return isNaN(+d) ? null : d
    }
    if (/^\d{13}$/.test(s)) {
      const d = new Date(Number(s))
      return isNaN(+d) ? null : d
    }
    let m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s)
    if (m) return new Date(+m[1], +m[2] - 1, +m[3])
    m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?/.exec(s)
    if (m) return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] || 0))
    if (s.includes(' ') && !s.includes('T')) s = s.replace(' ', 'T')
    const d = new Date(s)
    return isNaN(+d) ? null : d
  }

  // 2026-10-06; пусто/битое — '—' (как раньше в таблицах) либо исходная строка
  const fmtDate = (v: any): string => {
    const d = toDate(v)
    if (!d) return v == null || v === '' ? '—' : String(v)
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  }
  // 2026-10-06 14:30
  const fmtDateTime = (v: any): string => {
    const d = toDate(v)
    if (!d) return v == null || v === '' ? '—' : String(v)
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  }
  const fmtTime = (v: any): string => {
    const d = toDate(v)
    if (!d) return ''
    return `${pad(d.getHours())}:${pad(d.getMinutes())}`
  }
  // Оси графиков и узкие колонки: MM-DD
  const fmtAxis = (v: any): string => {
    const d = toDate(v)
    if (!d) return String(v ?? '')
    return `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  }

  return { fmtDate, fmtDateTime, fmtTime, fmtAxis, fmtDT: fmtDateTime }
}
