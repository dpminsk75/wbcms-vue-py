/**
 * Копирование в буфер с fallback для http/IP и браузеров без Clipboard API.
 *
 * `navigator.clipboard` доступен только в secure-контексте (https/localhost)
 * и может отклонить запрос без пользовательского жеста/разрешения. В этом
 * случае копируем через скрытый textarea + execCommand('copy').
 */
export async function copyText(text: string): Promise<boolean> {
  const value = String(text ?? '')

  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value)
      return true
    } catch {
      // fallback ниже
    }
  }

  const ta = document.createElement('textarea')
  ta.value = value
  ta.setAttribute('readonly', '')
  ta.style.position = 'fixed'
  ta.style.top = '0'
  ta.style.left = '0'
  ta.style.width = '1px'
  ta.style.height = '1px'
  ta.style.padding = '0'
  ta.style.border = 'none'
  ta.style.outline = 'none'
  ta.style.boxShadow = 'none'
  ta.style.background = 'transparent'
  ta.style.opacity = '0'
  document.body.appendChild(ta)

  const selection = document.getSelection()
  const prevRange = selection && selection.rangeCount > 0 ? selection.getRangeAt(0) : null

  let ok = false
  try {
    ta.focus()
    ta.select()
    ta.setSelectionRange(0, value.length)
    ok = document.execCommand('copy')
  } catch {
    ok = false
  } finally {
    ta.remove()
    if (prevRange && selection) {
      selection.removeAllRanges()
      selection.addRange(prevRange)
    }
  }
  return ok
}
