import { computed, toValue, watchEffect, type MaybeRefOrGetter } from 'vue'
import { docTitle } from '@/utils/pageTitle'

/**
 * Заголовок страницы с динамикой: ставит `document.title` и отдаёт тот же
 * текст для `h1`. Title — чистое имя, суффикс «— SelBI» добавляется сам.
 *
 *   const pageTitle = usePageMeta(() => `Карточка: ${card.value?.title ?? 'Выберите артикул'}`)
 */
export function usePageMeta(title: MaybeRefOrGetter<string>) {
  const value = computed(() => toValue(title).trim())
  watchEffect(() => {
    if (value.value) document.title = docTitle(value.value)
  })
  return value
}
