<template>
  <!--
    Блок выгрузки таблицы в PNG.

    Живёт в шапке блока рядом с кнопкой «Excel». Сам находит таблицу:
    поднимается по DOM до ближайшего `.tbl-card` — поэтому подключение
    к любой таблице это одна строка `<PngExportGroup />` без ref-ов.

    Что попадает в PNG: захват DOM таблицы (тема, зебра, фото) + шапка
    отчёта сверху. Сколько строк — ровно то, что раскрыто на экране.

    Вариант «Карточка» скрыт (решение 2026-11-02): движок отрисовки
    остался в `utils/exportPng.ts`, но в интерфейсе его нет — выбирать
    нечего, поэтому кнопка называется «PNG».
  -->
  <span ref="selfEl" class="hd-grp" :class="{ 'hd-grp--busy': busy }">
    <button
      type="button"
      class="hd-grp__btn hd-grp__btn--wide"
      :disabled="busy"
      title="Сохранить PNG на диск"
      @click="save"
    ><span v-if="busy" class="spinner-border png-grp__spin"></span><i v-else class="bi bi-download"></i>PNG</button>
    <button
      type="button"
      class="hd-grp__btn"
      :disabled="busy"
      title="Скопировать картинку в буфер обмена"
      @click="copy"
    ><span v-if="busy" class="spinner-border png-grp__spin"></span><i v-else class="bi bi-clipboard"></i></button>
  </span>

  <PngCopyModal
    :open="modalOpen"
    :blob="modalBlob"
    :filename="filename"
    @close="modalOpen = false"
  />
  <PngToast ref="toast" />
</template>

<script setup lang="ts">
/**
 * Универсальный блок выгрузки в PNG.
 *
 * Подключение к любой таблице с кнопкой Excel — одна строка в `.card__hd`:
 *
 *   <PngExportGroup />
 *
 * Никаких ref-ов и пропов с DOM-узлами: компонент сам поднимается по DOM
 * до ближайшего `.tbl-card` (все таблицы проекта построены так).
 *
 * Проп `card` — описание карточки для варианта «Карточка». Если его нет,
 * переключатель не показывается и доступен только снимок.
 */
import { computed, nextTick, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  captureElementPng,
  copyBlobToClipboard,
  pngDate,
  pngFileBase,
  saveBlob,
  type PngHeader,
} from '@/utils/exportPng'
import { stripSuffix } from '@/utils/pageTitle'
import PngCopyModal from './PngCopyModal.vue'
import PngToast from './PngToast.vue'

const props = withDefaults(defineProps<{
  /** Название отчёта для шапки картинки. По умолчанию — заголовок страницы. */
  title?: string
  /** Подзаголовок шапки: вкладка/срез. */
  subtitle?: string
  /** Фильтры для шапки: только значимые. */
  filters?: { label: string; value: string }[]
  /** Страница пагинации — в шапку уходит «стр. N из M». */
  page?: { current: number; total: number } | null
  /** Имя файла (без расширения). По умолчанию — из заголовка таблицы. */
  filename?: string
}>(), {
  title: '',
  subtitle: '',
  filters: () => [],
  page: null,
  filename: '',
})

const route = useRoute()
const auth = useAuthStore()

const busy = ref(false)
const modalOpen = ref(false)
const modalBlob = ref<Blob | null>(null)
const toast = ref<InstanceType<typeof PngToast> | null>(null)

/** Наш собственный корень — от него ищем блок таблицы вверх по DOM. */
const selfEl = ref<HTMLElement | null>(null)

/** Блок таблицы (`.tbl-card`) — ближайший предок нашего корня. */
function findHost(): HTMLElement | null {
  return (selfEl.value?.closest('.tbl-card') as HTMLElement) || null
}

/** Заголовок таблицы — из шапки блока (`.card__hd`), если не передан явно. */
const tableTitle = computed(() => {
  if (props.filename) return props.filename
  const head = findHost()?.querySelector('.card__hd')
  const span = head?.querySelector('span')
  return (span?.textContent || '').trim()
})

/**
 * Название отчёта: переданное или заголовок страницы.
 * Без бренда — «— SelBI» в картинке лишний (это хвост заголовка вкладки
 * браузера, а не название отчёта). Заголовок на странице — `meta.h1`,
 * иначе `meta.title` без суффикса.
 */
const reportTitle = computed(() => {
  if (props.title) return props.title.trim()
  const meta = route.meta as { h1?: string; title?: string }
  return String(meta.h1 ?? stripSuffix(meta.title)).trim() || 'Отчёт'
})

/** Компания — из выбранной компании в шапке приложения. */
const company = computed(() => {
  if (auth.companyId === 'all') return 'Все компании'
  return auth.companies.find((c) => c.id === auth.companyId)?.name || ''
})

/** Шапка картинки — одна на оба варианта. */
const header = computed<PngHeader>(() => ({
  title: reportTitle.value,
  subtitle: props.subtitle,
  company: company.value,
  date: pngDate(),
  filters: props.filters,
  page: props.page || undefined,
}))

/** Имя файла. */
const filename = computed(() => `${pngFileBase(props.filename || tableTitle.value || reportTitle.value)}.png`)

/** Собрать картинку: захват таблицы + шапка отчёта. */
async function buildBlob(): Promise<Blob> {
  const host = findHost()
  if (!host) throw new Error('не найден блок таблицы')
  return await captureElementPng(host, header.value)
}

/**
 * Дождаться отрисовки спиннера и тоста до тяжёлой работы: сбор картинки
 * надолго занимает поток, и без этой паузы пользователь увидит отклик
 * только по готовности — «тишина».
 */
async function paintBusyState(): Promise<void> {
  await nextTick()
  await new Promise((r) => requestAnimationFrame(() => setTimeout(r, 0)))
}

/** Сохранить на диск. */
async function save() {
  if (busy.value) return
  busy.value = true
  toast.value?.show('Готовим PNG…', 'info', true)
  await paintBusyState()
  try {
    const blob = await buildBlob()
    saveBlob(blob, filename.value)
    toast.value?.show(`Картинка сохранена: ${filename.value}`)
  } catch (e) {
    toast.value?.show(`Не удалось сохранить: ${(e as Error)?.message || 'ошибка'}`, 'warn')
  } finally {
    busy.value = false
  }
}

/** Скопировать в буфер. Без secure context — показываем модалку. */
async function copy() {
  if (busy.value) return
  busy.value = true
  toast.value?.show('Готовим PNG…', 'info', true)
  await paintBusyState()
  try {
    const blob = await buildBlob()
    const ok = await copyBlobToClipboard(blob)
    if (ok) {
      toast.value?.show('Картинка скопирована в буфер обмена')
    } else {
      // браузер не умеет писать картинку в буфер — отдаём модалку
      modalBlob.value = blob
      modalOpen.value = true
      toast.value?.clear()
    }
  } catch (e) {
    toast.value?.show(`Не удалось скопировать: ${(e as Error)?.message || 'ошибка'}`, 'warn')
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
/* Спиннер вместо иконки на время сбора картинки: размер под кнопку,
   цвет — текущий текст кнопки (spinner-border рисует currentColor). */
.png-grp__spin {
  width: 0.8em;
  height: 0.8em;
  border-width: 2px;
  vertical-align: -0.1em;
}
</style>
