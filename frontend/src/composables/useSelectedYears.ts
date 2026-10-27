import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

/**
 * Выбранные годы — в URL (?years=2025,2026), общие для вкладок
 * «Год к году» и «Аналитика»: ссылку с настроенной выборкой можно переслать,
 * кнопки «назад/вперёд» в браузере тоже работают.
 *
 * Пустой параметр = «все годы с данными» (решает вызывающая сторона).
 */
export function useSelectedYears() {
  const route = useRoute()
  const router = useRouter()

  /** Параметр задан (в т.ч. пустой) — значит выбор сделан явно. */
  const hasParam = computed(() => 'years' in route.query)

  const selectedYears = computed<number[]>(() => {
    const raw = String(route.query.years || '')
    const list = raw
      .split(',')
      .map(s => Number(s.trim()))
      .filter(n => Number.isInteger(n) && n > 2000 && n < 2100)
    return [...new Set(list)].sort((a, b) => a - b)
  })

  /** Зафиксировать выбор в URL (replace — не засоряем историю браузера). */
  const setYears = (list: number[]) => {
    const q: Record<string, any> = { ...route.query }
    const clean = [...new Set(list)].sort((a, b) => a - b)
    // Пустой выбор — это тоже выбор: параметр остаётся, но пустой (?years=).
    q.years = clean.join(',')
    router.replace({ path: route.path, query: q })
  }

  return { hasParam, selectedYears, setYears }
}
