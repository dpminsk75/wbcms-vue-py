<template>
  <img
    v-if="showImg"
    class="card-photo"
    :class="`card-photo--${fit}`"
    :src="imgSrc"
    :alt="alt"
    :style="ratio ? { aspectRatio: ratio } : undefined"
    loading="lazy"
    draggable="false"
    @error="onError"
  />
  <div v-else class="card-photo card-photo--none" aria-hidden="true">
    <i class="bi bi-image"></i>
  </div>
</template>

<script setup lang="ts">
/**
 * Фото товара — единая точка вывода для всех страниц.
 *
 * Фото лежат в локальном кэше (робот `images_worker`): бэк отдаёт свой WebP
 * 516×688, а если копии ещё нет — 302 на CDN WB. Поэтому здесь достаточно
 * одного URL: размер в адресе не передаётся (размер один).
 *
 * Раньше каждая страница собирала ссылку сама и разбирала JSON с фото —
 * здесь это сделано один раз.
 */
import { computed, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  /** URL фото (строка) либо JSON-массив с фото — разбирается на всякий случай. */
  src?: any
  /** Подпись (alt). */
  alt?: string
  /** object-fit: cover — обрезать по рамке, contain — вписать целиком. */
  fit?: 'cover' | 'contain'
  /** CSS aspect-ratio (например '1 / 1'). */
  ratio?: string
  /** Заглушка, если фото нет или не загрузилось. */
  placeholder?: string
}>(), {
  src: '',
  alt: '',
  fit: 'contain',
  ratio: '',
  placeholder: '/images/no-photo.png',
})

const failed = ref(false)

/** Первый URL фото из строки/массива/JSON (в т.ч. дважды закодированного). */
function resolve(raw: any): string {
  let p: any = raw
  for (let i = 0; i < 2; i++) {
    if (Array.isArray(p) || typeof p !== 'string') break
    try {
      p = JSON.parse(p)
    } catch {
      break
    }
  }
  if (Array.isArray(p)) {
    const first = p[0]
    if (typeof first === 'string') return first
    if (first && typeof first === 'object') {
      return String(first.photo || first.big || first.c516x688 || first.url || '')
    }
    return ''
  }
  if (typeof p === 'string') return p.trim()
  return ''
}

const imgSrc = computed(() => {
  const url = resolve(props.src)
  if (!url) return ''
  // свой путь (заглушка, уже наш /api/img) — не переписываем
  if (url.startsWith('/')) return url
  return `/api/img?u=${encodeURIComponent(url)}`
})

const showImg = computed(() => !!imgSrc.value && !failed.value)

function onError() {
  failed.value = true
}

watch(() => props.src, () => { failed.value = false })
</script>

<style scoped>
.card-photo {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #fff;
}
.card-photo--cover { object-fit: cover; }
/* фото нет — нейтральная заглушка вместо битой картинки */
.card-photo--none {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ink-muted);
  font-size: 18px;
  background: color-mix(in srgb, var(--ink) 6%, var(--surface));
}
</style>
