<template>
  <!--
    Модалка копирования картинки — запасной путь, когда браузер не даёт
    положить PNG в буфер обмена (http без secure context, Firefox, Safari).

    Картинка сжимается по высоте, чтобы полностью влезать в экран:
    пропорции сохраняются, а правый клик («Копировать изображение»)
    копирует ОРИГИНАЛ в полном разрешении — уменьшение только визуальное.
    Файл нигде не хранится — это blob-URL в памяти браузера.
  -->
  <div v-if="open" class="wb-modal-backdrop png-copy__backdrop" @click.self="close">
    <div class="wb-modal-box png-copy__box">
      <div class="png-copy__head">
        <div>
          <div class="png-copy__title">Скопируйте картинку</div>
          <div class="png-copy__sub">{{ filename }}</div>
        </div>
        <button type="button" class="png-copy__close" title="Закрыть" @click="close">
          <i class="bi bi-x"></i>
        </button>
      </div>

      <div class="png-copy__body">
        <div class="png-copy__hint">
          <i class="bi png-copy__hint-icon bi-info-circle"></i>
          <span>
            Нажмите на картинку <b>правой кнопкой</b> → <b>«Копировать изображение»</b>.
            Затем вставьте в чат (Ctrl+V). На телефоне — <b>долгий тап</b> по картинке.
          </span>
        </div>
        <img v-if="url" class="png-copy__img" :src="url" alt="Картинка для копирования" />
      </div>

      <div class="png-copy__foot">
        <button type="button" class="btn btn--brand btn-sm" @click="download">
          <i class="bi bi-download me-1"></i>Скачать PNG
        </button>
        <button type="button" class="btn btn--outline btn-sm" @click="openTab">
          <i class="bi bi-box-arrow-up-right me-1"></i>Открыть в новой вкладке
        </button>
        <span class="png-copy__note">файл не сохраняется на диск</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Модалка показа картинки, когда копирование в буфер недоступно.
 * Каркас — общие классы `.wb-modal-backdrop` / `.wb-modal-box` (wb-ui.css:147).
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { saveBlob } from '@/utils/exportPng'

const props = defineProps<{
  open: boolean,
  blob: Blob | null,
  filename: string,
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

const url = ref('')

/** blob-URL картинки; пересоздаётся при смене картинки, старый отзывается. */
watch(() => [props.open, props.blob] as const, () => {
  if (url.value) {
    URL.revokeObjectURL(url.value)
    url.value = ''
  }
  if (props.open && props.blob) {
    url.value = URL.createObjectURL(props.blob)
  }
}, { immediate: true })

onBeforeUnmount(() => {
  if (url.value) URL.revokeObjectURL(url.value)
})

const size = computed(() => (props.blob ? `${Math.round(props.blob.size / 1024)} КБ` : ''))

function close() {
  emit('close')
}

function download() {
  if (!props.blob) return
  saveBlob(props.blob, props.filename)
}

function openTab() {
  if (!url.value) return
  window.open(url.value, '_blank', 'noopener')
}
</script>

<style scoped>
.png-copy__backdrop { z-index: 1070; }
/* Бокс ограничен по высоте: высокая картинка не может вылезти за экран
   (иначе при центрировании бэктропом уезжают верх и низ). Всё лишнее
   прокручивается внутри .png-copy__body. */
.png-copy__box {
  max-width: 920px;
  width: min(920px, 92vw);
  max-height: 92vh;
  overflow: hidden;
  padding: 0;
  gap: 0;
}
.png-copy__head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--line);
}
.png-copy__title { font-size: calc(15px * var(--fs)); font-weight: 700; }
.png-copy__sub { font-size: calc(12.5px * var(--fs)); color: var(--ink-muted); margin-top: 1px; }
.png-copy__close {
  margin-left: auto;
  background: none;
  border: 0;
  color: var(--ink-muted);
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  padding: 4px 6px;
  border-radius: var(--radius-sm);
}
.png-copy__close:hover { background: var(--surface-3); color: var(--ink); }
.png-copy__body {
  padding: 14px 16px;
  overflow: auto;
  background: var(--surface-2);
}
.png-copy__hint {
  display: flex;
  gap: 9px;
  align-items: flex-start;
  background: var(--brand-tint);
  color: var(--brand-deep);
  border-radius: var(--radius-sm);
  padding: 9px 11px;
  font-size: calc(12.5px * var(--fs));
  margin-bottom: 12px;
}
.png-copy__hint-icon { flex: none; margin-top: 1px; }
.png-copy__img {
  display: block;
  max-width: 100%;
  /* Сжимаем по высоте, чтобы картинка была видна цЕЛИКОМ (92vh минус
     шапка ~58 px, подсказка ~78 px, подвал ~58 px). Пропорции держат
     width/height:auto + object-fit:contain. Превышение по ширине уходит
     в горизонтальную прокрутку .png-copy__body. */
  max-height: calc(92vh - 230px);
  width: auto;
  height: auto;
  object-fit: contain;
  margin: 0 auto;
  background: #fff;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-1);
}
.png-copy__foot {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid var(--line);
  font-size: calc(12.5px * var(--fs));
  color: var(--ink-soft);
  flex-wrap: wrap;
}
.png-copy__note { margin-left: auto; color: var(--ink-muted); }
</style>
