<template>
  <div class="container-xxl page-reply-rules">
    <WbWorkspaceHead :title="title" :workspace-tabs="FEEDBACK_TABS" workspace-active="rules" :subtabs="FEEDBACK_RULES_SUB_TABS" />
    <form class="page-reply-rules__form" @submit.prevent="onSave">
      <!-- Условия применения — блок темы .wb-panel (theme.md §5.4) -->
      <div class="wb-panel page-reply-rules__panel">
        <div class="card__hd">
          <span>Условия применения</span>
        </div>
        <div class="wb-panel__bd">
          <div class="page-reply-rules__field">
            <label class="page-reply-rules__field-label">Название правила</label>
            <input v-model="form.title" class="wb-input" maxlength="255" placeholder="Например: Отзыв на 5 звезд без текста" />
          </div>
          <div class="form-check mb-3">
            <input id="rr-active" v-model="form.is_active" type="checkbox" class="form-check-input" :true-value="1" :false-value="0" />
            <label for="rr-active" class="form-check-label">Активно</label>
          </div>
          <div class="row">
            <div class="col-md-4 mb-3">
              <span class="page-reply-rules__field-label">Тип правила</span>
              <div class="page-reply-rules__types">
                <button v-for="o in ruleTypeOpts" :key="o.v" type="button" class="opt"
                        :aria-pressed="form.rule_type === o.v" @click="form.rule_type = o.v">{{ o.t }}</button>
              </div>
            </div>
            <div class="col-md-4 mb-3">
              <label class="page-reply-rules__field-label">Рейтинг отзыва</label>
              <div class="page-reply-rules__rating">
                <select v-model.number="form.rating_min" class="wb-select">
                  <option v-for="n in 5" :key="'min' + n" :value="n">{{ n }}</option>
                </select>
                <span>—</span>
                <select v-model.number="form.rating_max" class="wb-select">
                  <option v-for="n in 5" :key="'max' + n" :value="n">{{ n }}</option>
                </select>
              </div>
            </div>
            <div class="col-md-4 mb-3">
              <span class="page-reply-rules__field-label">Содержимое отзыва</span>
              <div class="page-reply-rules__types">
                <button v-for="o in textCondOpts" :key="o.v" type="button" class="opt"
                        :aria-pressed="form.text_condition === o.v" @click="form.text_condition = o.v">{{ o.t }}</button>
              </div>
            </div>
          </div>
          <div v-if="form.rule_type === 'brand'" class="mb-3">
            <label class="page-reply-rules__field-label">Бренды</label>
            <input v-model="brandQuery" class="wb-input mb-2" placeholder="Начните вводить название бренда..." @input="onBrandQuery" />
            <div v-if="brandOptions.length" class="page-reply-rules__scope page-reply-rules__options">
              <button v-for="b in brandOptions" :key="b.id" type="button" class="page-reply-rules__option" @click="addBrand(b.id)">{{ b.text }}</button>
            </div>
            <div class="page-reply-rules__chips">
              <span v-for="b in form.brands" :key="b" class="badge badge--info">
                {{ b }}
                <button type="button" class="page-reply-rules__chip-x" title="Убрать" @click.prevent="removeBrand(b)">×</button>
              </span>
            </div>
          </div>
          <div v-if="form.rule_type === 'product'" class="mb-3">
            <label class="page-reply-rules__field-label">Товары</label>
            <input v-model="productQuery" class="wb-input mb-2" placeholder="Начните вводить название или nmID..." @input="onProductQuery" />
            <div v-if="productOptions.length" class="page-reply-rules__scope page-reply-rules__options">
              <button v-for="p in productOptions" :key="p.id" type="button" class="page-reply-rules__option" @click="addProduct(p)">{{ p.text }}</button>
            </div>
            <div class="page-reply-rules__chips">
              <span v-for="p in selectedProducts" :key="p.nmID" class="badge badge--warn">
                [{{ p.nmID }}] {{ p.title || '' }}
                <button type="button" class="page-reply-rules__chip-x" title="Убрать" @click.prevent="removeProduct(p.nmID)">×</button>
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Текст ответа — блок темы .wb-panel -->
      <div class="wb-panel page-reply-rules__panel">
        <div class="card__hd">
          <span>Текст ответа</span>
        </div>
        <div class="wb-panel__bd">
          <p class="page-reply-rules__hint">
            Можно использовать переменную <code v-text="'{{имя}}'"></code> — вместо неё подставится имя покупателя.
          </p>
          <div v-for="sec in sections" :key="sec.key" class="mb-4">
            <label class="page-reply-rules__field-label">{{ sec.title }}</label>
            <div v-for="(t, i) in sec.list" :key="i" class="page-reply-rules__part">
              <textarea v-model="sec.list[i]" class="wb-input" rows="3" placeholder="Введите вариант текста..."></textarea>
              <button type="button" class="btn btn--danger" title="Удалить" @click="removePart(sec.key, i)"><i class="bi bi-trash"></i></button>
            </div>
            <button type="button" class="btn btn--soft btn-sm" @click="addPart(sec.key)"><i class="bi bi-plus-lg me-1"></i>Добавить вариант</button>
          </div>
          <div class="mb-3">
            <span class="page-reply-rules__field-label">Разделитель частей ответа</span>
            <div class="page-reply-rules__types">
              <button v-for="o in sepOpts" :key="o.v" type="button" class="opt"
                      :aria-pressed="form.part_separator === o.v" @click="form.part_separator = o.v">{{ o.t }}</button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="error" class="page-reply-rules__error">{{ error }}</div>
      <div class="page-reply-rules__actions">
        <button type="submit" class="btn btn--brand" :disabled="saving">{{ saving ? 'Сохранение...' : 'Сохранить' }}</button>
        <router-link to="/wb-feedback-reply-rules" class="btn btn--outline">Отмена</router-link>
      </div>
    </form>
  </div>
</template>


<script setup lang="ts">
import '@/assets/css/pages/page-reply-rules.css'
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { replyRulesApi, type ReplyRulePayload } from '@/api/replyRules'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import { FEEDBACK_TABS, FEEDBACK_RULES_SUB_TABS } from '@/components/common/workspaceTabs'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const title = computed(() => isEdit.value ? `Редактирование правила: ${form.value.title || ''}` : 'Создание правила автоответа')

const form = ref<ReplyRulePayload>({
  title: '', is_active: 1, rule_type: 'general', rating_min: 5, rating_max: 5,
  text_condition: 'any', part_separator: 'newline',
  greetings: [''], bodies: [''], signoffs: [''], brands: [], product_ids: [],
})
const selectedProducts = ref<Array<{ nmID: number; title: string | null }>>([])
const brandQuery = ref('')
const brandOptions = ref<Array<{ id: string; text: string }>>([])
const productQuery = ref('')
const productOptions = ref<Array<{ id: string; text: string }>>([])
const saving = ref(false)
const error = ref('')

const ruleTypeOpts = [{ v: 'general', t: 'Общее' }, { v: 'brand', t: 'Для брендов' }, { v: 'product', t: 'Для товаров' }]
const textCondOpts = [{ v: 'with_text', t: 'С текстом' }, { v: 'no_text', t: 'Без текста' }, { v: 'any', t: 'Любой' }]
const sepOpts = [{ v: 'space', t: 'Пробел' }, { v: 'newline', t: 'Новая строка' }, { v: 'paragraph', t: 'Новый абзац' }]
const sections = computed(() => [
  { key: 'greetings', title: 'Приветствие', list: form.value.greetings },
  { key: 'bodies', title: 'Основная часть', list: form.value.bodies },
  { key: 'signoffs', title: 'Прощание', list: form.value.signoffs },
])

function addPart(key: string) {
  (form.value as any)[key].push('')
}
function removePart(key: string, i: number) {
  const arr = (form.value as any)[key] as string[]
  if (arr.length > 1) arr.splice(i, 1)
  else alert('Должен остаться хотя бы один вариант текста для данной секции!')
}

let brandTimer: any = null
function onBrandQuery() {
  clearTimeout(brandTimer)
  brandTimer = setTimeout(async () => {
    const q = brandQuery.value.trim()
    brandOptions.value = q.length >= 1 ? await replyRulesApi.brandList(q).catch(() => []) : []
  }, 300)
}
function addBrand(b: string) {
  if (!form.value.brands.includes(b)) form.value.brands.push(b)
  brandQuery.value = ''
  brandOptions.value = []
}
function removeBrand(b: string) {
  form.value.brands = form.value.brands.filter((x) => x !== b)
}

let productTimer: any = null
function onProductQuery() {
  clearTimeout(productTimer)
  productTimer = setTimeout(async () => {
    const q = productQuery.value.trim()
    productOptions.value = q.length >= 2 ? await replyRulesApi.productList(q).catch(() => []) : []
  }, 300)
}
function nmFromOption(p: { id: string; text: string }) {
  const m = /\[(\d+)\]/.exec(p.text || '')
  return Number(m ? m[1] : p.id)
}
function addProduct(p: { id: string; text: string }) {
  const nm = nmFromOption(p)
  if (!form.value.product_ids.includes(nm)) {
    form.value.product_ids.push(nm)
    selectedProducts.value.push({ nmID: nm, title: p.text.replace(/^\[\d+\]\s*/, '') })
  }
  productQuery.value = ''
  productOptions.value = []
}
function removeProduct(nm: number) {
  form.value.product_ids = form.value.product_ids.filter((x) => x !== nm)
  selectedProducts.value = selectedProducts.value.filter((x) => x.nmID !== nm)
}

async function onSave() {
  saving.value = true
  error.value = ''
  const payload: ReplyRulePayload = {
    ...form.value,
    greetings: form.value.greetings.filter((t) => t.trim()),
    bodies: form.value.bodies.filter((t) => t.trim()),
    signoffs: form.value.signoffs.filter((t) => t.trim()),
  }
  try {
    if (isEdit.value) await replyRulesApi.update(String(route.params.id), payload)
    else await replyRulesApi.create(payload)
    router.push('/wb-feedback-reply-rules')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  if (!isEdit.value) return
  try {
    const d = await replyRulesApi.get(String(route.params.id))
    form.value = {
      title: d.title, is_active: d.is_active, rule_type: d.rule_type,
      rating_min: d.rating_min, rating_max: d.rating_max,
      text_condition: d.text_condition, part_separator: d.part_separator,
      greetings: d.greetings.length ? d.greetings : [''],
      bodies: d.bodies.length ? d.bodies : [''],
      signoffs: d.signoffs.length ? d.signoffs : [''],
      brands: d.brands || [],
      product_ids: (d.products || []).map((p) => p.nmID),
    }
    selectedProducts.value = d.products || []
  } catch (e: any) {
    error.value = e?.response?.data?.detail || String(e)
  }
})
</script>

