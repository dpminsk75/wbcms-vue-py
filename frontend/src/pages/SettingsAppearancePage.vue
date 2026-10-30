<template>
  <div class="container-xxl page-theme">
    <div class="page-theme__head">
      <h1 class="page-theme__title">Настройки стилей</h1>
      <span class="badge badge--neutral">сохраняется в браузере</span>
      <button class="btn btn-sm btn--outline ms-auto" @click="onReset">Сбросить к дефолту</button>
    </div>
    <p class="page-theme__sub">
      Всё, что ниже, применяется сразу ко всей теме. Пока на новую тему переведена только эта
      страница — остальные разделы подтянутся по мере переезда (этап 2 и дальше).
      Настройки хранятся в <code>localStorage</code>, ключ <code>selbi-theme-v1</code>.
    </p>

    <div class="wb-panel">
      <div class="settings-row">
        <div class="settings-row__label">Пресет<span class="settings-row__hint">WB — как было до переезда</span></div>
        <div class="opt-grid">
          <button
            v-for="v in ALLOWED.preset"
            :key="'preset-' + v"
            class="opt"
            :aria-pressed="theme.preset === v"
            @click="setTheme('preset', v)"
          >{{ LABELS.preset[v] }}</button>
        </div>
      </div>

      <div class="settings-row">
        <div class="settings-row__label">База<span class="settings-row__hint">фон, текст, линии</span></div>
        <div class="opt-grid">
          <button
            v-for="v in ALLOWED.base"
            :key="'base-' + v"
            class="opt"
            :aria-pressed="theme.base === v"
            @click="setTheme('base', v)"
          >
            <span class="opt__sw" :style="{ background: BASE_SWATCH[v] }"></span>{{ LABELS.base[v] }}
          </button>
        </div>
      </div>

      <div class="settings-row">
        <div class="settings-row__label">Акцент<span class="settings-row__hint">кнопки, шапки, ссылки</span></div>
        <div class="swatches">
          <button
            v-for="v in ALLOWED.accent"
            :key="'accent-' + v"
            class="swatch"
            :aria-pressed="theme.accent === v"
            @click="setTheme('accent', v)"
          >
            <span class="swatch__dot" :style="{ background: ACCENT_SWATCH[v] }"></span>{{ LABELS.accent[v] }}
          </button>
        </div>
      </div>

      <div class="settings-row">
        <div class="settings-row__label">Шрифт</div>
        <div class="opt-grid">
          <button
            v-for="v in ALLOWED.font"
            :key="'font-' + v"
            class="opt"
            :aria-pressed="theme.font === v"
            :style="{ fontFamily: FONT_CSS[v] }"
            @click="setTheme('font', v)"
          >{{ LABELS.font[v] }}</button>
        </div>
      </div>

      <div class="settings-row">
        <div class="settings-row__label">Размер шрифта<span class="settings-row__hint">масштаб интерфейса</span></div>
        <div>
          <div class="opt-grid">
            <button
              v-for="v in ALLOWED.size"
              :key="'size-' + v"
              class="opt"
              :aria-pressed="theme.size === v"
              :style="{ fontSize: SIZE_CSS[v] }"
              @click="setTheme('size', v)"
            >{{ LABELS.size[v] }}</button>
          </div>
          <div class="settings-row__hint" :style="{ fontSize: 'calc(13.5px * ' + FS[theme.size] + ')' }">
            Так выглядит текст интерфейса при выбранном размере: заказы, выручка, маржа.
          </div>
        </div>
      </div>

      <div class="settings-row">
        <div class="settings-row__label">Градиент шапки приложения</div>
        <div class="opt-grid">
          <button
            v-for="v in ALLOWED.gradbar"
            :key="'gradbar-' + v"
            class="opt"
            :aria-pressed="theme.gradbar === v"
            @click="setTheme('gradbar', v)"
          >{{ LABELS.gradbar[v] }}</button>
        </div>
      </div>

      <div class="settings-row">
        <div class="settings-row__label">Цвет шапок таблиц</div>
        <div class="opt-grid">
          <button
            v-for="v in ALLOWED.head"
            :key="'head-' + v"
            class="opt"
            :aria-pressed="theme.head === v"
            @click="setTheme('head', v)"
          >{{ LABELS.head[v] }}</button>
        </div>
      </div>

      <div class="settings-row">
        <div class="settings-row__label">Градиент шапок таблиц</div>
        <div class="opt-grid">
          <button
            v-for="v in ALLOWED.gradhead"
            :key="'gradhead-' + v"
            class="opt"
            :aria-pressed="theme.gradhead === v"
            @click="setTheme('gradhead', v)"
          >{{ LABELS.gradhead[v] }}</button>
        </div>
      </div>

      <div class="settings-row">
        <div class="settings-row__label">Фон карточек<span class="settings-row__hint">вариант по умолчанию<br>для новых страниц</span></div>
        <div class="tile-grid">
          <button
            v-for="v in ALLOWED.tile"
            :key="'tile-' + v"
            class="tile-mini"
            :class="'tile--' + v.slice(1)"
            :aria-pressed="theme.tile === v"
            @click="setTheme('tile', v)"
          >
            <span class="tile-mini__num">{{ v.slice(1) }}</span>
            <span>{{ LABELS.tile[v] }}</span>
          </button>
        </div>
      </div>
    </div>

    <h2 class="page-theme__section">Предпросмотр · шапка и меню раздела</h2>
    <div class="preview">
      <div class="appbar">
        <a class="appbar__brand" href="#" @click.prevent>
          <img class="appbar__logo" src="/img/icons/logo-40.png" alt="SelBI" />
          <span>SelBI</span>
        </a>
        <nav class="appbar__nav">
          <a class="appbar__link is-active" href="#" @click.prevent>Отчёты</a>
          <a class="appbar__link" href="#" @click.prevent>По фразам</a>
          <a class="appbar__link" href="#" @click.prevent>Данные</a>
          <a class="appbar__link" href="#" @click.prevent>Админка</a>
        </nav>
        <span class="appbar__company">Кабинет</span>
      </div>

      <div class="wsp">
        <div class="wsp__head">
          <h3 class="wsp__title">SEO рекомендации</h3>
          <nav class="wsp__menu">
            <a class="mn" href="#" @click.prevent>Сводка</a>
            <a class="mn" href="#" @click.prevent>Поисковые запросы</a>
            <a class="mn" href="#" @click.prevent>Собранные карточки</a>
            <a class="mn mn--on" href="#" @click.prevent>SEO рекомендации</a>
            <a class="mn" href="#" @click.prevent>Конкуренты</a>
            <a class="mn mn--off" title="Скоро">Очередь</a>
          </nav>
        </div>
        <div class="wsp__sub">
          <a class="stab stab--line" href="#" @click.prevent>Все <span class="stab__count">128</span></a>
          <a class="stab stab--line stab--on" href="#" @click.prevent>Просмотр <span class="stab__count">12</span></a>
          <a class="stab stab--line" href="#" @click.prevent>Просмотренные <span class="stab__count">116</span></a>
        </div>
      </div>
    </div>

    <h2 class="page-theme__section">Предпросмотр · карточки</h2>
    <div class="preview-tiles">
      <div class="tile">
        <div class="tile__label">Маржинальность</div>
        <div class="tile__value">27,4 %</div>
        <div class="tile__foot"><span class="tile__delta">+2,1 п.п.</span> за неделю</div>
      </div>
      <div class="tile tile--3">
        <div class="tile__label">Выручка</div>
        <div class="tile__value">4,21 млн ₽</div>
        <div class="tile__foot">окт 2026</div>
      </div>
      <div class="tile tile--8">
        <div class="tile__label">Выкуп</div>
        <div class="tile__value">92,1 %</div>
        <div class="tile__foot"><span class="tile__delta">+0,6 п.п.</span></div>
      </div>
      <div class="tile tile--12">
        <div class="tile__label">CTR</div>
        <div class="tile__value">4,1 %</div>
        <div class="tile__foot"><span class="tile__delta tile__delta--down">−0,3</span></div>
      </div>
    </div>

    <h2 class="page-theme__section">Предпросмотр · таблица и 7 опций</h2>
    <div class="preview-box">
      <div class="preview-tools">
        <button class="opt" :aria-pressed="theme.table === 'compact'" @click="toggleCompact">
          Компакт
        </button>
        <button class="opt" :aria-pressed="opts.totalTop" @click="opts.totalTop = !opts.totalTop">Итог сверху</button>
        <button class="opt" :aria-pressed="opts.totalPlain" @click="opts.totalPlain = !opts.totalPlain">Итог без заливки</button>
        <button class="opt" :aria-pressed="!opts.noZebra" @click="opts.noZebra = !opts.noZebra">Зебра</button>
        <button class="opt" :aria-pressed="opts.sticky" @click="opts.sticky = !opts.sticky">Липкая шапка</button>
        <button class="opt" :aria-pressed="opts.stickyCol" @click="opts.stickyCol = !opts.stickyCol">Липкая колонка</button>
        <button class="opt" :aria-pressed="opts.scroll" @click="opts.scroll = !opts.scroll">Скролл</button>
      </div>

      <div :style="narrow ? 'max-width:560px' : ''">
        <div class="tbl-card" :class="tableClasses">
          <div class="card__hd">
            ТОП товаров по выручке
            <span class="hd-badge">окт 2026</span>
            <span class="spacer"></span>
            <button class="hd-btn">Excel</button>
          </div>
          <div class="tbl-wrap">
            <table class="tbl" :style="opts.scroll || opts.stickyCol ? 'min-width:780px' : ''">
              <thead>
                <tr>
                  <th>Товар</th>
                  <th>Заказы</th>
                  <th>Выручка</th>
                  <th>Возвраты</th>
                  <th>Маржа</th>
                  <th>CTR</th>
                  <th>Показы</th>
                  <th>Клики</th>
                </tr>
                <tr v-if="opts.totalTop" class="tbl__total tbl__total--top" :class="{ 'tbl__total--plain': opts.totalPlain }">
                  <td class="t-left">Итого</td>
                  <td>2 026</td>
                  <td>4 218 690 ₽</td>
                  <td>36</td>
                  <td>24,1 %</td>
                  <td>4,5 %</td>
                  <td>329 440</td>
                  <td>14 259</td>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in rows" :key="row.name">
                  <td class="t-left">{{ row.name }}</td>
                  <td>{{ row.orders }}</td>
                  <td>{{ row.revenue }}</td>
                  <td>{{ row.returns }}</td>
                  <td>{{ row.margin }}</td>
                  <td>{{ row.ctr }}</td>
                  <td>{{ row.views }}</td>
                  <td>{{ row.clicks }}</td>
                </tr>
              </tbody>
              <tfoot v-if="!opts.totalTop">
                <tr class="tbl__total" :class="{ 'tbl__total--plain': opts.totalPlain }">
                  <td class="t-left">Итого</td>
                  <td>2 026</td>
                  <td>4 218 690 ₽</td>
                  <td>36</td>
                  <td>24,1 %</td>
                  <td>4,5 %</td>
                  <td>329 440</td>
                  <td>14 259</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      </div>
    </div>

    <h2 class="page-theme__section">Предпросмотр · кнопки, поля, бейджи</h2>
    <div class="wb-panel">
      <div class="wb-panel__bd">
        <div class="btn-row">
          <button class="btn btn--brand">Применить</button>
          <button class="btn btn--outline">Сбросить</button>
          <button class="btn btn--ghost">Отмена</button>
          <span class="badge badge--ok">выкуп</span>
          <span class="badge badge--bad">отказы</span>
          <span class="badge badge--warn">проверить</span>
          <span class="badge badge--brand">SEO</span>
        </div>
        <div class="wb-form-grid" style="margin-top:12px">
          <div class="wb-field">
            <label class="wb-field__label">Артикул WB</label>
            <input class="wb-input" placeholder="526443466" />
          </div>
          <div class="wb-field">
            <label class="wb-field__label">Период</label>
            <input class="wb-input" value="01.10.2026 — 29.10.2026" />
          </div>
          <div class="wb-field">
            <label class="wb-field__label">Поиск</label>
            <input class="wb-input" placeholder="название или артикул" />
          </div>
        </div>
      </div>
    </div>

    <p class="page-theme__sub" style="margin-top:14px">
      Текущие атрибуты: <code>{{ attrsLine }}</code>
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'
import '@/assets/css/pages/page-settings-appearance.css'
import { ALLOWED, LABELS, theme, setTheme, resetTheme } from '@/theme'

const BASE_SWATCH: Record<string, string> = {
  cool: '#F4F7F9',
  neutral: '#F3F4F5',
  warm: '#FAF7F4',
}
const ACCENT_SWATCH: Record<string, string> = {
  graphite: '#283445',
  steel: '#0E7490',
  terracotta: '#A94E3E',
  petrol: '#1E4E5A',
  amber: '#B45309',
}
const FONT_CSS: Record<string, string> = {
  wix: "'Wix Madefor Text', sans-serif",
  manrope: "'Manrope', sans-serif",
  onest: "'Onest', sans-serif",
  selbi: "'Source Sans 3', sans-serif",
  golos: "'Golos Text', sans-serif",
}
const SIZE_CSS: Record<string, string> = { s: '12px', m: '13.5px', l: '15px', xl: '17px' }
const FS: Record<string, string> = { s: '0.9', m: '1', l: '1.12', xl: '1.25' }

const opts = reactive({
  totalTop: false,
  totalPlain: false,
  noZebra: false,
  sticky: false,
  stickyCol: false,
  scroll: true,
})

const tableClasses = computed(() => ({
  'tbl-card--compact': theme.table === 'compact',
  'tbl-card--nozebra': opts.noZebra,
  'tbl-card--sticky': opts.sticky,
  'tbl-card--stickycol': opts.stickyCol,
}))

const narrow = computed(() => opts.scroll || opts.stickyCol)

const attrsLine = computed(() => {
  const parts = Object.keys(theme)
    .filter((k) => (theme as Record<string, string>)[k])
    .map((k) => `data-${k}="${(theme as Record<string, string>)[k]}"`)
  return `<html ${parts.join(' ')}>`
})

function toggleCompact() {
  setTheme('table', theme.table === 'compact' ? 'std' : 'compact')
}
function onReset() {
  resetTheme()
  opts.totalTop = false
  opts.totalPlain = false
  opts.noZebra = false
  opts.sticky = false
  opts.stickyCol = false
  opts.scroll = true
}

const rows = [
  { name: 'Худи оверсайз «Graphite»', orders: '412', revenue: '1 284 300 ₽', returns: '12', margin: '27,4 %', ctr: '4,1 %', views: '128 400', clicks: '5 264' },
  { name: 'Джоггеры утеплённые', orders: '388', revenue: '1 102 840 ₽', returns: '9', margin: '25,1 %', ctr: '3,8 %', views: '104 210', clicks: '3 960' },
  { name: 'Футболка базовая', orders: '521', revenue: '864 210 ₽', returns: '21', margin: '19,7 %', ctr: '5,2 %', views: '96 830', clicks: '5 035' },
  { name: 'Свитшот «Тёплый»', orders: '301', revenue: '967 340 ₽', returns: '4', margin: '26,8 %', ctr: '4,4 %', views: '82 140', clicks: '3 614' },
  { name: 'Лонгслив хлопковый', orders: '274', revenue: '612 400 ₽', returns: '7', margin: '22,9 %', ctr: '3,2 %', views: '71 300', clicks: '2 282' },
  { name: 'Шорты спортивные', orders: '266', revenue: '498 120 ₽', returns: '5', margin: '21,3 %', ctr: '2,9 %', views: '64 880', clicks: '1 881' },
]
</script>
