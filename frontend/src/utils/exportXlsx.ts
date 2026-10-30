/**
 * Экспорт в Excel (.xlsx) — единая обёртка над динамическим импортом xlsx.
 *
 * Раньше 19 файлов повторяли один и тот же код: import('xlsx') → json_to_sheet
 * → book_new → book_append_sheet → writeFile. Динамический импорт сохранён —
 * xlsx не тянется в основной бандл.
 */
export type XlsxColumn = { wch?: number }

export type ExportXlsxOptions = {
  /** Строки — массив объектов с одинаковыми ключами. */
  rows: any[]
  /** Имя файла (с расширением .xlsx). */
  filename: string
  /** Имя листа. */
  sheetName?: string
  /** Ширины колонок: [{ wch: 10 }, …] */
  cols?: XlsxColumn[]
}

export async function exportXlsx(options: ExportXlsxOptions): Promise<void> {
  const { rows, filename, sheetName = 'Лист1', cols } = options
  if (!rows || !rows.length) return

  const XLSX = await import('xlsx')
  const ws = XLSX.utils.json_to_sheet(rows)
  if (cols && cols.length) ws['!cols'] = cols as any

  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, sheetName)
  XLSX.writeFile(wb, filename)
}
