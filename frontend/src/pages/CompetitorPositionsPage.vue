<template>
  <div class="container-xxl page-competitor page-positions">
    <!-- Шапка рабочего места: заголовок + меню рабочих мест (общий компонент темы).
         Локальные вкладки (По запросам / По нашим товарам / Ниши и реклама) — ниже. -->
    <WbWorkspaceHead title="Поисковые запросы" workspace-active="positions" />
    <nav class="wsp__sub page-positions__variants">
      <button
        v-for="v in variants"
        :key="v.id"
        type="button"
        class="stab stab--line"
        :class="{ 'stab--on': tab === v.id }"
        @click="setTab(v.id)"
      >{{ v.label }}</button>
    </nav>

    <!-- Фильтры: компактно, как на рабочем месте FBS -->
    <div class="page-positions__filter-card mb-3">
      <div class="page-positions__presets mb-2">
        <button
          v-for="p in presets"
          :key="p.id"
          class="btn btn-sm"
          :class="activePreset === p.id ? 'btn--brand' : 'btn--outline'"
          @click="applyPreset(p.id)"
        >{{ p.label }}</button>
      </div>
      <div class="row g-2 align-items-end">
        <div class="col-md-2">
          <label class="form-label mb-1 page-positions__label">Дата с</label>
          <WbDateInput v-model="dateFrom" />
        </div>
        <div class="col-md-2">
          <label class="form-label mb-1 page-positions__label">Дата по</label>
          <WbDateInput v-model="dateTo" />
        </div>
        <div class="col-md-4">
          <label class="form-label mb-1 page-positions__label">Фраза</label>
          <input
            v-model="q"
            class="wb-input"
            placeholder="например: календарь 2027"
            @keyup.enter="load"
          />
        </div>
      </div>
      <div class="page-positions__actions">
        <button class="btn btn--brand" @click="load">Применить</button>
        <button class="btn btn--outline" @click="reset">Сбросить</button>
      </div>
    </div>

    <div v-if="error" class="wb-panel page-positions__error">
      <div class="wb-panel__bd">{{ error }}</div>
    </div>
    <div v-if="loading" class="text-muted">
      <span class="spinner-border spinner-border-sm"></span> Загрузка…
    </div>

    <!-- ================= по запросам ================= -->
    <template v-else-if="tab === 'phrases'">
      <!-- список запросов -->
      <template v-if="!detail && !phraseLoading">
        <div v-if="!phrases.length" class="wb-panel page-positions__empty">
          <div class="wb-panel__bd">
            Сохранённых запросов пока нет. Откройте поиск WB — расширение сохранит выдачу.
          </div>
        </div>

        <div v-if="phrases.length" class="tbl-card">
          <div class="card__hd">
            <span>Запросы</span>
            <span class="page-positions__requeue">
              <label class="page-positions__check">
                <input type="checkbox" :checked="allSelected" @change="toggleAll" />
                <span>выбрать все</span>
              </label>
              <button
                class="btn btn-sm btn--brand"
                :disabled="!selected.length || requeueBusy"
                title="Отправить отмеченные фразы в расширение — оно пересоберёт выдачу по ним"
                @click="sendRequeue"
              >
                <i class="bi bi-arrow-repeat"></i>
                Отправить на пересборку<span v-if="selected.length"> ({{ selected.length }})</span>
              </button>
              <span v-if="requeueNotice" class="page-positions__note">{{ requeueNotice }}</span>
            </span>
            <span class="spacer"></span>
            <span class="hd-badge">Запросов: {{ phrases.length }}</span>
          </div>
          <div class="tbl-wrap">
          <table class="tbl page-positions__grid">
          <thead>
            <tr>
              <th class="t-center" style="width: 28px"></th>
              <th class="t-left" title="Поисковая фраза, по которой собирали выдачу WB">Фраза</th>
              <th class="t-center" title="Сколько раз мы заходили в поиск по этой фразе">Сборов</th>
              <th class="t-center" title="В скольких днях были наблюдения">Дней</th>
              <th class="t-center" title="Сколько разных товаров было в выдаче">Товаров</th>
              <th class="t-center" title="Сколько наших товаров было в выдаче (наведи — список)">Наших</th>
              <th class="t-left" title="Когда собирали">Период</th>
              <th class="t-left" title="Кто и с какого устройства собирал">Кто собрал</th>
              <th class="t-left" title="Пересборка выдачи расширением">Пересборка</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="r in phrases"
              :key="r.phrase"
              class="page-positions__row"
              @click="openPhrase(r)"
            >
              <td class="t-center">
                <input
                  type="checkbox"
                  :checked="isSelected(r.phrase)"
                  @click.stop
                  @change="toggleOne(r.phrase)"
                />
              </td>
              <td class="t-left">
                <span class="page-positions__phrase">{{ r.phrase }}</span>
                <div v-if="(r.phrase_variants || []).length > 1" class="page-positions__note">
                  варианты: {{ r.phrase_variants.join(' | ') }}
                </div>
              </td>
              <td class="t-center">{{ r.collections ?? r.days }}</td>
              <td class="t-center">{{ r.days }}</td>
              <td class="t-center">{{ r.products }}</td>
              <td class="t-center">
                <span v-if="!r.sources.length" class="page-positions__note">—</span>
                <span v-else class="page-positions__ours" :title="sourcesTitle(r)">
                  {{ r.sources.length }}
                </span>
              </td>
              <td class="t-left page-positions__date">{{ period(r) }}</td>
              <td class="t-left">
                <span v-for="u in r.saved_by" :key="u.id" class="page-positions__note">
                  {{ u.username || ('user ' + u.id) }}
                </span>
                <span v-if="!r.saved_by.length" class="page-positions__note">—</span>
              </td>
              <td class="t-left">
                <span
                  v-if="r.requeue_status"
                  class="badge"
                  :class="requeueBadge(r.requeue_status)"
                  :title="r.requeue_error || (r.requeue_at ? 'обновлено: ' + r.requeue_at : '')"
                >{{ requeueLabel(r.requeue_status) }}</span>
                <span v-else class="page-positions__note">—</span>
              </td>
              <td class="page-positions__chev t-right">
                <span v-if="phraseLoading && selectedPhrase === r.phrase" class="spinner-border spinner-border-sm"></span>
                <i v-else class="bi bi-chevron-right"></i>
              </td>
            </tr>
          </tbody>
          </table>
          </div>
        </div>
      </template>

      <!-- Пока грузим выдачу — индикатор (иначе страница "молчит") -->
      <div v-else-if="phraseLoading" class="wb-panel page-positions__empty">
        <div class="wb-panel__bd">
          <span class="spinner-border spinner-border-sm"></span> Загружаем выдачу по фразе…
        </div>
      </div>

      <!-- Выдача по запросу: строка = дата сбора, в ней карточки выдачи -->
      <div v-else class="page-positions__detail">
        <div class="page-positions__detail-head">
          <button class="btn btn-sm btn--outline" @click="closePhrase">
            <i class="bi bi-arrow-left"></i> Все запросы
          </button>
          <h3 class="page-positions__detail-title">«{{ detail.phrase }}»</h3>
          <span class="text-muted small">сборов: {{ (detail.slices || []).length }}</span>
          <div class="btn-group btn-group-sm" role="group" aria-label="Сколько карточек показывать">
            <button
              v-for="o in limitOptions"
              :key="o.value"
              class="btn"
              :class="cardLimit === o.value ? 'btn--brand' : 'btn--outline'"
              @click="cardLimit = o.value"
            >{{ o.label }}</button>
          </div>
        </div>

        <div v-if="!(detail.slices || []).length" class="wb-panel page-positions__empty">
          <div class="wb-panel__bd">По этой фразе нет сохранённых срезов.</div>
        </div>

        <div v-for="sl in detail.slices || []" :key="sl.stamp || sl.date" class="page-positions__slice">
          <div class="page-positions__slice-date">
            <div class="page-positions__slice-day">{{ sl.date }}</div>
            <div v-if="sl.time" class="page-positions__slice-time">{{ sl.time }}</div>
            <div class="text-muted small">товаров: {{ sl.items.length }}</div>
          </div>
          <div
            class="page-positions__cards"
            @pointerdown="onStripDown"
            @pointermove="onStripMove"
            @pointerup="onStripUp"
            @pointercancel="onStripUp"
            @click.capture="onStripClick"
          >
            <CompetitorCard
              v-for="c in sliceCards(sl.items)"
              :key="c.nm_id"
              variant="feed"
              :nm-id="c.nm_id"
              :title="c.title"
              :brand="c.brand"
              :seller="c.seller"
              :price="c.price"
              :old-price="c.old_price ?? null"
              :price-api="c.price_api ?? null"
              :rating="c.rating ?? null"
              :review-rating="c.review_rating ?? null"
              :reviews="c.reviews ?? c.feedbacks ?? null"
              :badges="c.badges || []"
              :image-url="c.image_url"
              :position="c.position_api ?? c.position"
              :subject="c.subject_name || ''"
              :collected="collectedFlag(c.is_collected, !!c.is_ours)"
              :is-ours="!!c.is_ours"
              @open="openCard(c)"
            />
            <div v-if="sl.items.length > cardLimit" class="page-positions__more">
              +{{ sl.items.length - cardLimit }}
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- ================= по нашим товарам ================= -->
    <template v-else-if="tab === 'cards'">
      <div class="page-positions__toolbar">
        <div class="btn-group btn-group-sm" role="group" aria-label="Сколько конкурентов показывать">
          <button
            v-for="o in topOptions"
            :key="o.value"
            class="btn"
            :class="top === o.value ? 'btn--brand' : 'btn--outline'"
            @click="setTop(o.value)"
          >{{ o.label }}</button>
        </div>
      </div>

      <div v-if="!cards.length" class="wb-panel page-positions__empty">
        <div class="wb-panel__bd">
          Наблюдений по нашим карточкам пока нет — наши карточки ещё не попадали в собранную выдачу.
        </div>
      </div>

      <div v-else class="tbl-card">
        <div class="card__hd">
          <span>Наши карточки</span>
          <span class="spacer"></span>
          <span class="hd-badge">Показано {{ cards.length }} из {{ cardsTotal }}</span>
        </div>
        <div class="tbl-wrap">
        <table class="tbl page-positions__grid">
        <thead>
          <tr>
            <th class="t-left">Наша карточка</th>
            <th class="t-center" title="Сколько запросов, где наша карточка была в выдаче">Запросов</th>
            <th class="t-center">Дней</th>
            <th class="t-center" title="Лучшая позиция за период">Лучшая позиция</th>
            <th class="t-left">Последний</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="c in cards"
            :key="c.nm_id"
            class="page-positions__row"
            :class="{ 'page-positions__row--active': selectedCard === c.nm_id }"
            @click="openCardById(c.nm_id)"
          >
            <td class="t-left">
              <ProductCell
                compact
                :nm-id="c.nm_id"
                :photo="c.photo || ''"
                :title="c.title || ('nm ' + c.nm_id)"
                :vendor="c.vendor || ''"
                :brand="c.brand || ''"
                :subject="c.subject || ''"
                :link="wbUrl(c.nm_id)"
                :link-label="'WB: ' + c.nm_id"
                copy-nm
                copy-link
              />
            </td>
            <td class="num t-center">{{ c.phrases }}</td>
            <td class="num t-center">{{ c.days }}</td>
            <td class="num t-center">{{ c.best_position ?? '—' }}</td>
            <td class="t-left page-positions__date">{{ c.last_at || '—' }}</td>
          </tr>
        </tbody>
        </table>
        </div>
        <div class="wb-pager">
          <button class="btn btn-sm btn--outline" :disabled="cardsPage <= 1" @click="setCardsPage(cardsPage - 1)">
            <i class="bi bi-chevron-left"></i> Назад
          </button>
          <span class="wb-pager__label">
            Стр. {{ cardsPage }} из {{ cardsPages }} · показано {{ cards.length }} из {{ cardsTotal }}
          </span>
          <button class="btn btn-sm btn--outline" :disabled="cardsPage >= cardsPages" @click="setCardsPage(cardsPage + 1)">
            Вперёд <i class="bi bi-chevron-right"></i>
          </button>
        </div>
      </div>

      <div v-if="cardDetail" class="page-positions__detail">
        <div class="page-positions__detail-head">
          <h3 class="page-positions__detail-title">
            {{ cardDetail.card.title || ('nm ' + cardDetail.card.nm_id) }}
          </h3>
          <span class="text-muted small">запросов: {{ cardDetail.phrases.length }}</span>
          <button class="btn btn-sm btn--outline ms-auto" @click="cardDetail = null">Свернуть</button>
        </div>

        <div v-if="!cardDetail.phrases.length" class="wb-panel page-positions__empty">
          <div class="wb-panel__bd">По этой карточке наблюдений в выбранном периоде нет.</div>
        </div>

        <div v-for="p in cardDetail.phrases" :key="p.phrase" class="page-positions__block">
          <div class="page-positions__block-head">
            <span class="page-positions__phrase">{{ p.phrase }}</span>
            <span class="badge" :class="p.last_position ? 'badge--brand' : 'badge--neutral'">
              наша позиция: {{ p.last_position ?? '—' }}
              <template v-if="p.last_position_api"> · WB: {{ p.last_position_api }}</template>
            </span>
            <span v-if="p.best_position" class="badge badge--neutral">лучшая: {{ p.best_position }}</span>
            <span v-if="p.best_position_api" class="badge badge--neutral">
              лучшая WB: {{ p.best_position_api }}
            </span>
            <span class="text-muted small">срез: {{ p.last_day || '—' }} · дней: {{ p.days.length }}</span>
          </div>

          <div class="tbl-card">
            <div class="card__hd"><span>Конкуренты в выдаче</span></div>
            <div class="tbl-wrap">
            <table class="tbl">
            <thead>
              <tr>
                <th class="num t-center" title="Позиция в DOM (с рекламой)">Поз.</th>
                <th class="num t-center" title="Позиция в JSON-выдаче (органика)">Поз. JSON</th>
                <th class="t-left">Конкурент</th>
                <th class="num">Цена</th>
                <th class="num">Рейтинг</th>
                <th class="num">Отзывы</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in p.competitors" :key="`${p.phrase}-${c.nm_id}`">
                <td class="t-center">{{ c.position }}</td>
                <td class="t-center">{{ c.position_api ?? '—' }}</td>
                <td class="t-left">
                  <CompetitorRow
                    compact
                    :nm-id="c.nm_id"
                    :photo="c.image_url || ''"
                    :title="c.title || ('nm ' + c.nm_id)"
                    :seller="c.seller || c.brand || ''"
                    :badges="c.badges || []"
                    :wb-url="wbUrl(c.nm_id)"
                    :phrases-url="'/competitor/phrase-miner'"
                    show-nm
                    copy-nm
                    @open="openCard(c)"
                  />
                </td>
                <td class="num">{{ money(c.price) }}</td>
                <td class="num">{{ c.rating || '—' }}</td>
                <td class="num">{{ c.reviews ?? c.feedbacks ?? '—' }}</td>
              </tr>
              <tr v-if="!p.competitors.length">
                <td colspan="6" class="t-center text-muted p-3">В этом срезе конкурентов не записали.</td>
              </tr>
            </tbody>
            </table>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- ================= ниши и реклама ================= -->
    <template v-else>
      <nav class="wsp__sub page-positions__variants">
        <button
          type="button"
          class="stab stab--line"
          :class="{ 'stab--on': nicheTab === 'niches' }"
          @click="setNicheTab('niches')"
        >
          Профиль ниш<span v-if="nichesTotal" class="stab__count"> {{ nichesTotal }}</span>
        </button>
        <button
          type="button"
          class="stab stab--line"
          :class="{ 'stab--on': nicheTab === 'ads' }"
          @click="setNicheTab('ads')"
        >
          Реклама<span v-if="adsTotal" class="stab__count"> {{ adsTotal }}</span>
        </button>
        <button
          type="button"
          class="stab stab--line"
          :class="{ 'stab--on': nicheTab === 'shelfs' }"
          @click="setNicheTab('shelfs')"
        >
          Полки<span v-if="adsTotal" class="stab__count"> {{ adsTotal }}</span>
        </button>
      </nav>

      <!-- ---------- Профиль ниш ---------- -->
      <template v-if="nicheTab === 'niches'">
      <div v-if="!niches.length" class="wb-panel page-positions__empty">
        <div class="wb-panel__bd">
          Профили ниш ещё не собраны — расширение сохранит их при первом поиске на WB.
        </div>
      </div>

      <div v-if="niches.length" class="tbl-card">
        <div class="card__hd">
          <span>Профиль ниш (фильтры выдачи)</span>
          <span class="spacer"></span>
          <span class="hd-badge">Показано {{ niches.length }} из {{ nichesTotal }}</span>
        </div>
        <div class="tbl-wrap">
        <table class="tbl page-positions__grid">
        <thead>
          <tr>
            <th class="t-left">Фраза</th>
            <th class="t-center">Объём ниши</th>
            <th class="page-positions__nowrap">Цены, ₽</th>
            <th class="page-positions__nowrap t-center">Доставка, ч</th>
            <th class="t-left">Бренды</th>
            <th class="t-left">Продавцы</th>
            <th class="t-left">Акции</th>
            <th class="t-left page-positions__col-facets">Фасеты</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="n in niches" :key="n.phrase + n.date">
            <td class="t-left">
              <div class="page-positions__phrase">{{ n.phrase }}</div>
              <div class="text-muted small">{{ n.date }}</div>
              <div v-if="(n.phrase_variants || []).length" class="text-muted small">
                варианты: {{ n.phrase_variants.join(' | ') }}
              </div>
            </td>
            <td class="t-center">{{ n.total ?? '—' }}</td>
            <td class="num">{{ n.price_min ?? '—' }} … {{ n.price_max ?? '—' }}</td>
            <td class="num t-center">{{ n.delivery_min ?? '—' }} … {{ n.delivery_max ?? '—' }}</td>
            <td class="small t-left">{{ n.brands.map((b) => b.name).join(', ') || '—' }}</td>
            <td class="small t-left">{{ n.sellers.map((s) => s.name).join(', ') || '—' }}</td>
            <td class="small t-left">
              <span v-if="n.sale_factions.length" class="badge badge--warn">
                {{ n.sale_factions.map((f) => f.name).join(', ') }}
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="small t-left">
              <span
                v-for="f in facetEntries(n).slice(0, FACETS_SHOWN)"
                :key="f.key"
                class="badge badge--neutral me-1"
                :title="(f.items || []).map((i) => i.name).join(', ')"
              >{{ f.name || f.key }}: {{ (f.items || []).length }}</span>
              <span
                v-if="facetEntries(n).length > FACETS_SHOWN"
                class="badge badge--neutral me-1"
                :title="facetsTitle(n)"
              >ещё {{ facetEntries(n).length - FACETS_SHOWN }}</span>
              <span v-if="!facetEntries(n).length" class="text-muted">—</span>
            </td>
          </tr>
        </tbody>
        </table>
        </div>
        <div class="wb-pager">
          <button class="btn btn-sm btn--outline" :disabled="nichesPage <= 1" @click="setNichesPage(nichesPage - 1)">
            <i class="bi bi-chevron-left"></i> Назад
          </button>
          <span class="wb-pager__label">
            Стр. {{ nichesPage }} из {{ nichesPages }} · показано {{ niches.length }} из {{ nichesTotal }}
          </span>
          <button class="btn btn-sm btn--outline" :disabled="nichesPage >= nichesPages" @click="setNichesPage(nichesPage + 1)">
            Вперёд <i class="bi bi-chevron-right"></i>
          </button>
        </div>
      </div>
      </template>

      <!-- ---------- Реклама и полки в поиске ---------- -->
      <template v-else>
      <div v-if="!adsRows.length" class="wb-panel page-positions__empty">
        <div class="wb-panel__bd">
          Реклама в поиске ещё не собрана — расширение сохранит её при первом поиске на WB.
        </div>
      </div>

      <div v-for="a in adsRows" :key="a.phrase + a.date" class="page-positions__block">
        <div class="page-positions__block-head">
          <span class="page-positions__phrase">{{ a.phrase }}</span>
          <span class="badge badge--neutral">баннеров: {{ a.banner_cnt }}</span>
          <span class="badge badge--neutral">полок: {{ a.shelf_cnt }}</span>
          <span class="badge badge--neutral">товаров в полках: {{ a.shelf_products_cnt }}</span>
          <span class="text-muted small">{{ a.date }}</span>
        </div>
        <div v-if="nicheTab === 'ads' && a.banners.length" class="tbl-card">
          <div class="card__hd"><span>Реклама в поиске</span></div>
          <div class="tbl-wrap">
          <table class="tbl">
          <thead>
            <tr>
              <th class="t-left">Рекламодатель</th>
              <th class="num">CPM</th>
              <th class="t-left">Тип</th>
              <th class="t-left">ЕРИD</th>
              <th class="t-left">Ссылка</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(b, i) in a.banners" :key="i">
              <td class="small t-left">{{ b.mark || '—' }}</td>
              <td class="small">{{ b.cpm || '—' }}</td>
              <td class="small t-left">{{ b.type || '—' }}</td>
              <td class="small t-left">{{ b.erid || '—' }}</td>
              <td class="small t-left">
                <a v-if="b.url" :href="'https://www.wildberries.ru' + b.url" target="_blank" rel="noopener">открыть</a>
                <span v-else>—</span>
              </td>
            </tr>
          </tbody>
        </table>
        </div>
        </div>
        <div v-if="nicheTab === 'shelfs'" class="page-positions__shelves">
          <div v-for="(s, i) in a.shelfs" :key="'s' + i" class="page-positions__history">
            <span class="badge badge--neutral">{{ s.title || 'полка' }}</span>
            <span class="badge badge--neutral">{{ s.mark }}</span>
            <span class="badge badge--neutral">товаров: {{ s.products.length }}</span>
          </div>
          <span v-if="!a.shelfs.length" class="text-muted small">Полок нет.</span>
        </div>
      </div>

      <div v-if="adsRows.length" class="wb-pager">
        <button class="btn btn-sm btn--outline" :disabled="adsPage <= 1" @click="setAdsPage(adsPage - 1)">
          <i class="bi bi-chevron-left"></i> Назад
        </button>
        <span class="wb-pager__label">
          Стр. {{ adsPage }} из {{ adsPages }} · показано {{ adsRows.length }} из {{ adsTotal }}
        </span>
        <button class="btn btn-sm btn--outline" :disabled="adsPage >= adsPages" @click="setAdsPage(adsPage + 1)">
          Вперёд <i class="bi bi-chevron-right"></i>
        </button>
      </div>
      </template>
    </template>

    <!-- Клик по конкуренту — досье конкурента; клик по нашей карточке — сводка -->
    <CompetitorDetailsModal
      :open="competitorNm !== null"
      :nm-id="competitorNm"
      :our-nm-id="competitorOurs"
      :phrase="competitorPhrase"
      @close="competitorNm = null"
    />
    <OurCardModal
      :open="ourCardNm !== null"
      :nm-id="ourCardNm"
      :date-from="dateFrom"
      :date-to="dateTo"
      @close="ourCardNm = null"
    />
  </div>
</template>

<script setup lang="ts">
import '@/assets/css/pages/page-competitor-positions.css'
import { computed, ref, onMounted, watch } from 'vue'
import WbDateInput from '@/components/common/WbDateInput.vue'
import WbWorkspaceHead from '@/components/common/WbWorkspaceHead.vue'
import CompetitorCard from '@/components/common/CompetitorCard.vue'
import CompetitorRow from '@/components/common/CompetitorRow.vue'
import ProductCell from '@/components/common/ProductCell.vue'
import { collectedFlag } from '@/components/common/competitorCard'
import OurCardModal from '@/components/positions/OurCardModal.vue'
import CompetitorDetailsModal from '@/components/competitors/CompetitorDetailsModal.vue'
import { useMoneyFmt } from '@/composables/useMoneyFmt'
import { useRoute, useRouter } from 'vue-router'
import {
  competitorsPositionsApi,
  type PositionsPhraseRow,
  type PositionsPhraseDetail,
  type PositionsCardRow,
  type PositionsCardDetail,
  type PositionsItem,
  type NicheRow,
  type SearchAdsRow,
} from '@/api/competitorsPositions'

const { fmt0 } = useMoneyFmt()
const route = useRoute()
const router = useRouter()

type Tab = 'phrases' | 'cards' | 'niches'

const variants: Array<{ id: Tab; label: string }> = [
  { id: 'phrases', label: 'По запросам' },
  { id: 'cards', label: 'По нашим товарам' },
  { id: 'niches', label: 'Ниши и реклама' },
]

const tab = ref<Tab>('phrases')
const dateFrom = ref('')
const dateTo = ref('')
const q = ref('')
const loading = ref(false)
const error = ref('')

const phrases = ref<PositionsPhraseRow[]>([])
const cards = ref<PositionsCardRow[]>([])
const CARDS_PAGE = 50
const cardsPage = ref(1)
const cardsTotal = ref(0)
const cardsPages = computed(() => Math.max(1, Math.ceil(cardsTotal.value / CARDS_PAGE)))
const niches = ref<NicheRow[]>([])
const adsRows = ref<SearchAdsRow[]>([])

// «Ниши и реклама» — три вкладки: профиль ниш / реклама / полки
type NicheTab = 'niches' | 'ads' | 'shelfs'
const nicheTab = ref<NicheTab>('niches')
const NICHE_PAGE = 50
const nichesPage = ref(1)
const adsPage = ref(1)
const nichesTotal = ref(0)
const adsTotal = ref(0)
const nichesPages = computed(() => Math.max(1, Math.ceil(nichesTotal.value / NICHE_PAGE)))
const adsPages = computed(() => Math.max(1, Math.ceil(adsTotal.value / NICHE_PAGE)))

/** Сколько фасетов показываем в строке (остальные — в подсказке). */
const FACETS_SHOWN = 3

const selectedPhrase = ref('')
const detail = ref<PositionsPhraseDetail | null>(null)
/** Загрузка выдачи по фразе — индикатор в шевроне строки и панель-заглушка. */
const phraseLoading = ref(false)
let phraseReq = 0

const selectedCard = ref<number | null>(null)
const cardDetail = ref<PositionsCardDetail | null>(null)

// сколько карточек показывать в строке среза
const cardLimit = ref(10)
const limitOptions = [
  { value: 5, label: '5' },
  { value: 10, label: '10' },
  { value: 15, label: '15' },
  { value: 25, label: '25' },
  { value: 40, label: '40' },
  { value: 0, label: 'Все' },
]

// ТОП-6 / ТОП-12 / Все (по нашим товарам)
const top = ref(12)
const topOptions = [
  { value: 6, label: 'ТОП-6' },
  { value: 12, label: 'ТОП-12' },
  { value: 0, label: 'Все' },
]

// --- пересборка выдачи по отмеченным фразам ---
const selected = ref<string[]>([])
const requeueBusy = ref(false)
const requeueNotice = ref('')

const REQUEUE_LABEL: Record<string, string> = {
  pending: 'в очереди', processing: 'собираем', done: 'готово', error: 'ошибка',
}
const REQUEUE_BADGE: Record<string, string> = {
  pending: 'badge--neutral', processing: 'badge--info', done: 'badge--ok', error: 'badge--bad',
}
const requeueLabel = (s: string) => REQUEUE_LABEL[s] || s
const requeueBadge = (s: string) => REQUEUE_BADGE[s] || 'badge--neutral'

function isSelected(phrase: string): boolean {
  return selected.value.includes(phrase)
}
function toggleOne(phrase: string) {
  selected.value = isSelected(phrase)
    ? selected.value.filter((p) => p !== phrase)
    : [...selected.value, phrase]
}
const allSelected = computed(
  () => phrases.value.length > 0 && phrases.value.every((p) => isSelected(p.phrase)),
)
function toggleAll() {
  selected.value = allSelected.value ? [] : phrases.value.map((p) => p.phrase)
}

async function sendRequeue() {
  if (!selected.value.length || requeueBusy.value) return
  requeueBusy.value = true
  requeueNotice.value = ''
  try {
    const r = await competitorsPositionsApi.requeue({ phrases: selected.value })
    const skipped = r.skipped?.length ? `, не влезло: ${r.skipped.length}` : ''
    requeueNotice.value = `в очереди: ${r.queued}${skipped}`
    selected.value = []
    await load()
  } catch (e: any) {
    requeueNotice.value = errText(e)
  } finally {
    requeueBusy.value = false
  }
}

const competitorNm = ref<number | null>(null)
const competitorOurs = ref<number>(0)
const competitorPhrase = ref<string>('')
const ourCardNm = ref<number | null>(null)

function money(v: any): string {
  if (v == null || v === '' || Number(v) === 0) return '—'
  return `${fmt0(v)} ₽`
}
/** Ресейл (товар от частного лица) — свой цвет, как в карточке выдачи. */
function isResaleBadge(b: string): boolean {
  return /ресейл|resale/i.test(String(b || ''))
}
function wbUrl(nm: number): string {
  return `https://www.wildberries.ru/catalog/${nm}/detail.aspx`
}
function sliceCards(items: PositionsItem[]): PositionsItem[] {
  return cardLimit.value > 0 ? items.slice(0, cardLimit.value) : items
}
function fmtDay(d: string): string {
  if (!d) return '—'
  const parts = d.split('-')
  return parts.length === 3 ? `${parts[2]}.${parts[1]}.${parts[0]}` : d
}
function period(r: PositionsPhraseRow): string {
  if (!r.first_at) return '—'
  if (r.first_at === r.last_at) return fmtDay(r.first_at)
  return `${fmtDay(r.first_at)} — ${fmtDay(r.last_at)}`
}
function sourcesTitle(r: PositionsPhraseRow): string {
  return r.sources.map((s) => `${s.nm_id} · ${s.title || ''}`).join('\n')
}
function errText(e: any): string {
  const d = e?.response?.data?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d) && d.length) {
    const it = d[0] || {}
    const loc = Array.isArray(it.loc) ? it.loc.join('.') : ''
    const msg = it.msg || JSON.stringify(it)
    return loc ? `${msg} (${loc})` : msg
  }
  return String(e?.message || e)
}

function fmtD(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}
function initRange() {
  const to = new Date()
  const from = new Date()
  from.setDate(from.getDate() - 29)
  dateTo.value = fmtD(to)
  dateFrom.value = fmtD(from)
}

/* пресеты периода (как в WbUniversalFilter) */
const activePreset = ref('30')
const presets = [
  { id: 'today', label: 'Сегодня' },
  { id: 'yesterday', label: 'Вчера' },
  { id: '7', label: '7 дней' },
  { id: '14', label: '14 дней' },
  { id: '30', label: '30 дней' },
  { id: '90', label: '90 дней' },
  { id: '365', label: '365 дней' },
  { id: 'year', label: 'С начала года' },
]

function applyPreset(id: string) {
  activePreset.value = id
  const t = new Date()
  if (id === 'today') {
    dateFrom.value = fmtD(t)
    dateTo.value = fmtD(t)
  } else if (id === 'yesterday') {
    const y = new Date()
    y.setDate(y.getDate() - 1)
    dateFrom.value = fmtD(y)
    dateTo.value = fmtD(y)
  } else if (id === 'year') {
    dateFrom.value = fmtD(new Date(t.getFullYear(), 0, 1))
    dateTo.value = fmtD(t)
  } else {
    const f = new Date()
    f.setDate(f.getDate() - (Number(id) - 1))
    dateFrom.value = fmtD(f)
    dateTo.value = fmtD(t)
  }
  load()
}

function setTab(t: Tab) {
  tab.value = t
  load()
}

function setNicheTab(t: NicheTab) {
  nicheTab.value = t
  syncUrl()
}

function setNichesPage(p: number) {
  const p2 = Math.max(1, Math.min(p, nichesPages.value))
  if (p2 === nichesPage.value) return
  nichesPage.value = p2
  load()
}

function setAdsPage(p: number) {
  const p2 = Math.max(1, Math.min(p, adsPages.value))
  if (p2 === adsPage.value) return
  adsPage.value = p2
  load()
}

/** Фасеты ниши: список {key, name, items} — показываем первые FACETS_SHOWN. */
function facetEntries(n: NicheRow): Array<{ key: string; name?: string | null; items?: Array<{ name?: string | null }> }> {
  return Object.entries(n?.facets || {}).map(([key, f]) => ({ key, name: f?.name, items: f?.items }))
}

/** Подсказка «ещё N» — весь список фасетов строки. */
function facetsTitle(n: NicheRow): string {
  return facetEntries(n).map((f) => `${f.name || f.key}: ${(f.items || []).length}`).join(' · ')
}

function setCardsPage(p: number) {
  const p2 = Math.max(1, Math.min(p, cardsPages.value))
  if (p2 === cardsPage.value) return
  cardsPage.value = p2
  load()
}

function setTop(v: number) {
  top.value = v
  if (selectedCard.value) openCardById(selectedCard.value)
}

async function load() {
  syncUrl()
  loading.value = true
  error.value = ''
  try {
    const params = { date_from: dateFrom.value || undefined, date_to: dateTo.value || undefined }
    if (tab.value === 'phrases') {
      const res = await competitorsPositionsApi.phrases({ ...params, q: q.value || undefined })
      phrases.value = res.items || []
      if (selectedPhrase.value && !phrases.value.some((p) => p.phrase === selectedPhrase.value)) {
        selectedPhrase.value = ''
        detail.value = null
        syncUrl(null)
      }
    } else if (tab.value === 'cards') {
      const res = await competitorsPositionsApi.cards({
        ...params, limit: CARDS_PAGE, offset: (cardsPage.value - 1) * CARDS_PAGE,
      })
      cards.value = res.items || []
      cardsTotal.value = res.total || 0
    } else {
      const [n, a] = await Promise.all([
        competitorsPositionsApi.niches({ ...params, limit: NICHE_PAGE, offset: (nichesPage.value - 1) * NICHE_PAGE }),
        competitorsPositionsApi.ads({ ...params, limit: NICHE_PAGE, offset: (adsPage.value - 1) * NICHE_PAGE }),
      ])
      niches.value = n.items || []
      nichesTotal.value = n.total || 0
      adsRows.value = a.items || []
      adsTotal.value = a.total || 0
    }
  } catch (e: any) {
    error.value = errText(e)
  } finally {
    loading.value = false
  }
}

async function openPhrase(r: PositionsPhraseRow) {
  if (selectedPhrase.value === r.phrase) {
    closePhrase()
    return
  }
  selectedPhrase.value = r.phrase
  detail.value = null
  syncUrl()
  await loadPhrase()
}

function closePhrase() {
  selectedPhrase.value = ''
  detail.value = null
  syncUrl()
}

async function loadPhrase() {
  if (!selectedPhrase.value) return
  const req = ++phraseReq
  phraseLoading.value = true
  try {
    const res = await competitorsPositionsApi.phrase({
      phrase: selectedPhrase.value,
      date_from: dateFrom.value || undefined,
      date_to: dateTo.value || undefined,
    })
    if (req !== phraseReq) return
    detail.value = res
  } catch (e: any) {
    if (req === phraseReq) error.value = errText(e)
  } finally {
    if (req === phraseReq) phraseLoading.value = false
  }
}

/** Состояние страницы → адресная строка: фильтры переживают перезагрузку, ссылкой можно поделиться. */
function syncUrl() {
  const qs: Record<string, any> = { ...route.query }
  const put = (k: string, v: any) => {
    if (v === '' || v === null || v === undefined || v === false) delete qs[k]
    else qs[k] = String(v)
  }
  put('tab', tab.value)
  put('date_from', dateFrom.value)
  put('date_to', dateTo.value)
  put('q', q.value)
  put('top', top.value)
  put('cards_page', cardsPage.value > 1 ? cardsPage.value : '')
  put('phrase', selectedPhrase.value)
  put('ntab', nicheTab.value)
  put('npage', nichesPage.value > 1 ? nichesPage.value : '')
  put('apage', adsPage.value > 1 ? adsPage.value : '')
  const target = { path: route.path, query: qs }
  if (route.fullPath === router.resolve(target).fullPath) return
  router.replace(target).catch(() => {})
}

/** Адресная строка → состояние. true — что-то изменилось (нужен перезагруз). */
function applyQuery(): boolean {
  const p = route.query
  const s = (k: string) => (p[k] === undefined ? '' : String(p[k]))
  let changed = false
  if (p.tab !== undefined) {
    const t = s('tab') as Tab
    if (t && t !== tab.value) { tab.value = t; changed = true }
  }
  if (p.date_from !== undefined && s('date_from') !== dateFrom.value) {
    dateFrom.value = s('date_from'); changed = true
  }
  if (p.date_to !== undefined && s('date_to') !== dateTo.value) {
    dateTo.value = s('date_to'); changed = true
  }
  if (p.q !== undefined && s('q') !== q.value) { q.value = s('q'); changed = true }
  if (p.top !== undefined && Number(s('top')) !== top.value) {
    top.value = Number(s('top')) || 12; changed = true
  }
  if (p.cards_page !== undefined) {
    const pg = Math.max(1, Number(s('cards_page')) || 1)
    if (pg !== cardsPage.value) { cardsPage.value = pg; changed = true }
  }
  if (p.phrase !== undefined && s('phrase') !== selectedPhrase.value) {
    selectedPhrase.value = s('phrase'); changed = true
  }
  if (p.ntab !== undefined) {
    const t = s('ntab') as NicheTab
    if (t && t !== nicheTab.value) { nicheTab.value = t; changed = true }
  }
  if (p.npage !== undefined) {
    const pg = Math.max(1, Number(s('npage')) || 1)
    if (pg !== nichesPage.value) { nichesPage.value = pg; changed = true }
  }
  if (p.apage !== undefined) {
    const pg = Math.max(1, Number(s('apage')) || 1)
    if (pg !== adsPage.value) { adsPage.value = pg; changed = true }
  }
  return changed
}

/* Лента карточек среза: тащим мышкой вправо-влево (колесо по горизонтали не листает).
   Лента повторяется в каждом срезе (v-for), поэтому работаем с currentTarget события,
   а не с ref: он собрал бы массив элементов. */
let dragStartX = 0
let dragStartScroll = 0
let dragMoved = false
let dragPointer = -1

function onStripDown(e: PointerEvent) {
  const el = e.currentTarget as HTMLElement
  if (!el) return
  dragStartX = e.clientX
  dragStartScroll = el.scrollLeft
  dragMoved = false
  dragPointer = e.pointerId
  try { el.setPointerCapture(e.pointerId) } catch { /* захват не поддержан — не критично */ }
}

function onStripMove(e: PointerEvent) {
  const el = e.currentTarget as HTMLElement
  if (!el || dragPointer !== e.pointerId) return
  const dx = e.clientX - dragStartX
  if (Math.abs(dx) > 6) {
    dragMoved = true
    el.classList.add('is-dragging')
  }
  if (dragMoved) el.scrollLeft = dragStartScroll - dx
}

function onStripUp(e: PointerEvent) {
  const el = e.currentTarget as HTMLElement
  if (!el || dragPointer !== e.pointerId) return
  el.classList.remove('is-dragging')
  dragPointer = -1
}

/** После таска клик по карточке не должен открывать модалку. */
function onStripClick(e: MouseEvent) {
  if (!dragMoved) return
  e.stopPropagation()
  e.preventDefault()
  dragMoved = false
}

function openCard(c: PositionsItem) {
  if (c.is_ours) {
    ourCardNm.value = c.nm_id
  } else {
    competitorNm.value = c.nm_id
    // Контекст для «Собрать в расширении»: наша карточка среза + открытая фраза.
    competitorOurs.value = (c.source_nm_ids || [])[0] || c.source_nm_id || 0
    competitorPhrase.value = selectedPhrase.value || ''
  }
}

async function openCardById(nm: number) {
  try {
    const res = await competitorsPositionsApi.card({
      nm_id: nm,
      date_from: dateFrom.value || undefined,
      date_to: dateTo.value || undefined,
      top: top.value,
    })
    cardDetail.value = res
  } catch (e: any) {
    error.value = errText(e)
  }
}

function reset() {
  activePreset.value = '30'
  initRange()
  q.value = ''
  load()
}

onMounted(async () => {
  // даты из ссылки — иначе дефолтный период
  if (route.query.date_from === undefined && route.query.date_to === undefined) initRange()
  applyQuery()
  await load()
  // ?phrase=… — раскрыть фразу из ссылки (deep-link)
  if (selectedPhrase.value) await loadPhrase()
})

// «назад/вперёд» в браузере и переход по ссылке — применяем состояние из адресной строки
watch(() => route.query, async () => {
  const prevPhrase = selectedPhrase.value
  if (!applyQuery()) return
  if (selectedPhrase.value !== prevPhrase) {
    detail.value = null
    if (selectedPhrase.value) await loadPhrase()
    return
  }
  await load()
})
</script>

