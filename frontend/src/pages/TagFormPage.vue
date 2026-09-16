<template>
  <div class="container-xxl page-tag-form">
    <h1 class="page-title page-tag-form__title">{{ isEdit ? `Редактирование тега: ${form.name}` : 'Новый тег' }}</h1>

    <form @submit.prevent="onSave">
      <div class="row g-3">
        <div class="col-md-4">
          <div class="card page-tag-form__panel mb-3">
            <div class="page-tag-form__panel-header"><i class="bi bi-tag me-2"></i>Параметры тега</div>
            <div class="card-body page-tag-form__params">
              <label class="form-label">Название тега<input v-model="form.name" required class="form-control" placeholder="Название тега..." /></label>
              <label class="form-label">Группа<input v-model="form.tag_group" class="form-control" placeholder="Группа (напр. Сезонные)" /></label>
              <label class="form-label">Цвет
                <span class="page-tag-form__color-row">
                  <input v-model="form.color" type="color" class="form-control form-control-color" />
                  <input v-model="form.color" class="form-control" placeholder="#337ab7" pattern="#[0-9a-fA-F]{6}" />
                </span>
              </label>
              <label class="form-label">Приоритет<input v-model.number="form.priority" type="number" class="form-control" placeholder="Приоритет (чем выше, тем левее)" /></label>
            </div>
          </div>

          <div class="page-tag-form__stat mb-3">
            <div class="page-tag-form__stat-icon"><i class="bi bi-layers"></i></div>
            <div>
              <div class="page-tag-form__stat-value">{{ selected.length }}</div>
              <div class="page-tag-form__stat-label">Карточек в теге</div>
            </div>
          </div>

          <button type="submit" class="btn btn-success btn-lg w-100" :disabled="saving">
            <i class="bi bi-check-lg me-1"></i>{{ saving ? 'Сохранение...' : 'Сохранить тег' }}
          </button>
          <div v-if="saveError" class="text-danger mt-2">{{ saveError }}</div>
        </div>

        <div class="col-md-8">
          <div class="card page-tag-form__panel">
            <div class="page-tag-form__panel-header"><i class="bi bi-link-45deg me-2"></i>Привязка карточек Wildberries</div>
            <div class="card-body">
              <div class="row g-2 mb-3 page-tag-form__search">
                <div class="col-md-2"><input v-model="q.nmID" class="form-control form-control-sm" placeholder="Арт WB" /></div>
                <div class="col-md-3"><input v-model="q.vendorCode" class="form-control form-control-sm" placeholder="Артикул" /></div>
                <div class="col-md-5"><input v-model="q.title" class="form-control form-control-sm" placeholder="Название" @keyup.enter="onSearch" /></div>
                <div class="col-md-2"><button type="button" class="btn btn-primary btn-sm w-100" @click="onSearch"><i class="bi bi-search me-1"></i>Найти</button></div>
              </div>

              <div class="row">
                <div class="col-md-7">
                  <div class="page-tag-form__column-header">
                    <span><i class="bi bi-arrows-move me-1"></i>Доступные</span>
                    <button type="button" class="btn btn-sm btn-outline-primary" @click="addAllVisible"><i class="bi bi-plus-lg me-1"></i>Добавить все</button>
                  </div>
                  <div class="page-tag-form__available">
                    <VueDraggable
                      v-model="available"
                      :group="{ name: 'wb-cards', pull: 'clone', put: false }"
                      :sort="false"
                      :clone="cloneCard"
                      item-key="nmID"
                      class="page-tag-form__available-list"
                    >
                      <div v-for="c in available" :key="c.nmID" class="page-tag-form__available-item">
                        <b>{{ c.nmID }}</b><span class="text-muted"> {{ c.vendorCode }}</span>
                        <div class="page-tag-form__available-title">{{ c.title }}</div>
                      </div>
                    </VueDraggable>
                    <div v-if="!available.length" class="text-muted p-3">Ничего не найдено</div>
                  </div>
                </div>

                <div class="col-md-5">
                  <div class="page-tag-form__column-header"><span><i class="bi bi-inbox me-1"></i>Выбранные</span></div>
                  <VueDraggable
                    v-model="selected"
                    :group="{ name: 'wb-cards', pull: true, put: true }"
                    :animation="150"
                    ghost-class="page-tag-form__selected-item--ghost"
                    chosen-class="page-tag-form__selected-item--chosen"
                    drag-class="page-tag-form__selected-item--drag"
                    item-key="nmID"
                    class="page-tag-form__drop-zone"
                    :class="{ 'page-tag-form__drop-zone--over': isOver }"
                    @add="onAdd"
                  >
                    <div v-for="c in selected" :key="c.nmID" class="page-tag-form__selected-item">
                      <div class="page-tag-form__selected-info">
                        <span class="page-tag-form__selected-nmid">{{ c.nmID }}</span>
                        <span class="page-tag-form__selected-vendor">{{ c.vendorCode }}</span>
                        <div class="page-tag-form__selected-title">{{ c.title }}</div>
                      </div>
                      <button type="button" class="page-tag-form__remove" title="Удалить" @click="removeCard(c.nmID)">×</button>
                    </div>
                    <div v-if="!selected.length" class="page-tag-form__placeholder"><i class="bi bi-arrow-left me-1"></i>Перетащите карточки сюда</div>
                  </VueDraggable>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-tag-form.css'
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { VueDraggable } from 'vue-draggable-plus'
import { tagsApi, type WbCardOption } from '@/api/tags'

const route = useRoute()
const router = useRouter()
const tagId = computed(() => route.params.id as string | undefined)
const isEdit = computed(() => !!tagId.value)

const form = reactive({ name: '', tag_group: '', color: '#337ab7', priority: 0 })
const q = reactive({ nmID: '', vendorCode: '', title: '' })
const available = ref<WbCardOption[]>([])
const selected = ref<WbCardOption[]>([])
const isOver = ref(false)
const saving = ref(false)
const saveError = ref('')

function cloneCard(c: WbCardOption): WbCardOption {
  return { ...c }
}

function onAdd() {
  const seen = new Set<number>()
  selected.value = selected.value.filter((c) => {
    if (seen.has(c.nmID)) return false
    seen.add(c.nmID)
    return true
  })
}

function removeCard(nmID: number) {
  selected.value = selected.value.filter((c) => c.nmID !== nmID)
}

function addAllVisible() {
  const ids = new Set(selected.value.map((c) => c.nmID))
  for (const c of available.value) {
    if (!ids.has(c.nmID)) {
      selected.value.push({ ...c })
      ids.add(c.nmID)
    }
  }
}

async function onSearch() {
  try {
    available.value = await tagsApi.searchCards(q)
  } catch {
    available.value = []
  }
}

async function onSave() {
  saving.value = true
  saveError.value = ''
  const payload = {
    name: form.name.trim(),
    tag_group: form.tag_group.trim() || null,
    color: form.color,
    priority: Number(form.priority) || 0,
    wbCardIds: selected.value.map((c) => c.nmID),
  }
  try {
    if (isEdit.value) await tagsApi.update(tagId.value!, payload)
    else await tagsApi.create(payload)
    router.push('/tags')
  } catch (e: any) {
    saveError.value = e?.response?.data?.detail || String(e)
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await onSearch()
  if (isEdit.value) {
    try {
      const d = await tagsApi.get(tagId.value!)
      form.name = d.name
      form.tag_group = d.tag_group ?? ''
      form.color = d.color || '#337ab7'
      form.priority = d.priority ?? 0
      selected.value = (d.cards ?? []).map((c) => ({ ...c }))
      if (!selected.value.length && d.wbCardIds?.length) {
        selected.value = d.wbCardIds.map((nmID) => ({ nmID, vendorCode: '', title: '' }))
      }
    } catch (e: any) {
      saveError.value = e?.response?.data?.detail || String(e)
    }
  }
})
</script>
