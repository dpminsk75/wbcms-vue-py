<template>
  <div v-if="open" class="ext-install-modal__backdrop" @click.self="$emit('close')">
    <div class="ext-install-modal__box" role="dialog" aria-label="Установка расширения">
      <div class="ext-install-modal__head">
        <h5 class="ext-install-modal__title"><i class="bi bi-puzzle"></i> Установка расширения</h5>
        <button type="button" class="btn-close" @click="$emit('close')" aria-label="Закрыть"></button>
      </div>
      <ExtInstallGuide :companyId="companyId" />
      <div class="ext-install-modal__foot">
        <button type="button" class="btn btn-secondary btn-sm" @click="$emit('close')">Закрыть</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import ExtInstallGuide from './ExtInstallGuide.vue'

defineProps<{ open: boolean; companyId: number | 'all' }>()
defineEmits<{ (e: 'close'): void }>()
</script>

<style scoped>
.ext-install-modal__backdrop {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.4); z-index: 1050;
  display: flex; align-items: flex-start; justify-content: center; padding: 40px 12px;
  overflow-y: auto;
}
.ext-install-modal__box {
  background: #fff; border-radius: 8px; max-width: 640px; width: 100%;
  padding: 16px 18px; font-size: 14px;
}
.ext-install-modal__head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.ext-install-modal__title { margin: 0; font-size: 17px; }
.ext-install-modal__foot { margin-top: 12px; text-align: right; }
</style>
