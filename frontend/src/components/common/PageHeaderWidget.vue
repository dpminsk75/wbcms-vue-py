<template>
  <div class="row mb-3">
    <div class="d-flex col-md-10">
      <h1 style="font-size:20px; font-weight:700; margin:0">{{ title }}</h1>
    </div>
    <div class="nm-id-container col-md-2 d-flex justify-content-end align-items-center" style="color:#555; font-size:12px;">
      ID:&nbsp;<b><span id="nmId-value">{{ nmId }}</span></b>
      <i class="bi bi-copy" style="cursor:pointer; margin-left:5px;" @click="copyId" title="Копировать ID"></i>
      <a v-if="nmId" :href="eyeHref" target="_blank" class="btn-eye" style="margin-left:6px; text-decoration:none;" title="Открыть карточку"><i class="bi bi-eye"></i></a>
    </div>
  </div>
</template>
<script setup lang="ts">
const props = defineProps<{ title: string, nmId: string|number }>()
const eyeHref = `/wb/detail?DPFilterForm[nm_id]=${props.nmId}`
const copyId = async()=>{
  try{ await navigator.clipboard.writeText(String(props.nmId)) }catch{
    const el = document.getElementById('nmId-value')
    if(el){
      const r = document.createRange(); r.selectNode(el); const sel = window.getSelection(); sel?.removeAllRanges(); sel?.addRange(r)
      document.execCommand('copy'); sel?.removeAllRanges()
    }
  }
}
</script>
<style scoped>
.btn-eye { color:#6c757d; }
.btn-eye:hover { color:#0d6efd; }
</style>
