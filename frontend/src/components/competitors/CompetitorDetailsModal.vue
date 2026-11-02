<template>
  <div v-if="open" class="wb-modal-backdrop comp-details-backdrop" @click.self="$emit('close')">
    <div class="wb-modal-box comp-details">
      <div class="comp-details__head">
        <h5 class="comp-details__title">
          <i class="bi bi-card-text"></i> Карточка конкурента
          <span class="badge bg-dark">{{ nmId }}</span>
          <button type="button" class="comp-details__copy-btn" title="Скопировать nmID" @click="copyNm">
            <i class="bi" :class="copiedNm ? 'bi-check2' : 'bi-clipboard'"></i>
          </button>
          <button type="button" class="comp-details__copy-btn" title="Скопировать ссылку на карточку (WB)" @click="copyUrl">
            <i class="bi" :class="copiedUrl ? 'bi-check2' : 'bi-box-arrow-up-right'"></i>
          </button>
          <span v-if="copyError" class="text-danger small">{{ copyError }}</span>
        </h5>
        <button type="button" class="btn-close" aria-label="Закрыть" @click="$emit('close')"></button>
      </div>

      <div v-if="loading" class="text-muted small">
        <span class="spinner-border spinner-border-sm"></span> Загрузка…
      </div>
      <div v-else-if="error" class="wb-error">{{ error }}</div>

      <template v-else-if="item">
        <div v-if="isPartial" class="comp-details__partial">
          <div class="comp-details__partial-note">
            <i class="bi bi-info-circle"></i>
            Полный сбор карточки ещё не выполнялся — показаны данные из выдачи.<span
              v-if="item.phrase" class="comp-details__partial-phrase">Фраза: «{{ item.phrase }}»</span>
          </div>
          <button
            type="button"
            class="btn btn-sm btn-outline-primary"
            :disabled="collectBusy || !monitorNm || !monitorPhrase"
            :title="!monitorNm || !monitorPhrase
              ? 'Нет контекста (наша карточка + фраза) для очереди мониторинга'
              : 'Поставить нашу карточку и фразу в очередь «SEO мониторинг» — сбор идёт фоном'"
            @click="collectInExtension"
          >
            <i class="bi" :class="collectDone ? 'bi-check2' : collectErr ? 'bi-arrow-repeat' : 'bi-search'"></i>
            {{ collectDone ? 'В мониторинге' : 'Поставить фразу в мониторинг' }}
          </button>
          <span v-if="collectErr" class="text-danger small">{{ collectErr }}</span>
          <span v-else-if="monitorNm && monitorPhrase" class="text-muted small">
            карточка {{ monitorNm }} + фраза «{{ monitorPhrase }}»
          </span>
        </div>

        <div class="comp-details__top">
          <div class="comp-details__gallery">
            <div class="comp-details__main">
              <CardPhoto :src="activeImage" :alt="item.title || ''" fit="contain" />
            </div>
            <div v-if="item.images.length > 1" class="comp-details__thumbs">
              <button
                v-for="(img, i) in item.images"
                :key="img"
                type="button"
                class="comp-details__thumb"
                :class="{ 'is-active': i === imageIdx }"
                @click="imageIdx = i"
              >
                <CardPhoto :src="img" alt="" fit="cover" />
              </button>
            </div>
            <div v-if="!item.images.length && item.preview_image" class="comp-details__preview-note">
              превью из выдачи — галерея ещё не собрана
            </div>
          </div>

          <div class="comp-details__info">
            <div class="comp-details__name">{{ item.title || '—' }}</div>
            <div class="comp-details__meta">
              <span v-if="item.brand">бренд: {{ item.brand }}</span>
              <span v-if="item.seller && item.seller !== item.brand">продавец: {{ item.seller }}</span>
              <span v-if="item.subject_name">предмет: {{ item.subject_name }}</span>
            </div>

            <div class="comp-details__price">
              <template v-if="item.sold_out">
                <span class="badge bg-dark comp-details__sold-out">Нет в наличии</span>
                <span
                  v-if="item.old_price"
                  class="comp-details__price-old"
                  :title="'Последняя собранная цена: ' + money(item.old_price)"
                >{{ money(item.old_price) }}</span>
              </template>
              <template v-else>
                <span class="comp-details__price-now">{{ money(item.price) }}</span>
                <span v-if="item.old_price" class="comp-details__price-old">{{ money(item.old_price) }}</span>
              </template>
            </div>

            <div v-if="badgesList.length" class="comp-details__badges">
              <span
                v-for="(b, i) in badgesList"
                :key="i"
                class="badge"
                :class="badgeClass(b)"
                :title="'Признак из выдачи/карточки WB: ' + b"
              >{{ b }}</span>
            </div>

            <div class="comp-details__meta">
              <span v-if="item.rating">рейтинг: {{ item.rating }}</span>
              <span v-if="item.feedbacks">оценок: {{ item.feedbacks }}</span>
              <span v-if="item.questions">вопросов: {{ item.questions }}</span>
            </div>

            <!-- Описание и характеристики — в шапке, сразу после рейтинга -->
            <div v-if="item.description" class="comp-details__brief">
              <div class="comp-details__brief-head">
                <span>Описание</span>
                <span class="badge bg-light text-dark">{{ descLen }}</span>
              </div>
              <div class="comp-details__brief-text" :class="{ 'is-clamp': !descOpen }">{{ item.description }}</div>
              <button v-if="descLen > 220" class="comp-details__brief-more" @click="descOpen = !descOpen">
                {{ descOpen ? 'свернуть' : 'развернуть' }}
              </button>
            </div>

            <div v-if="item.characteristics.length" class="comp-details__brief">
              <div class="comp-details__brief-head">
                <span>Характеристики</span>
                <span class="badge bg-light text-dark">{{ item.characteristics.length }}</span>
              </div>
              <table class="comp-details__chars">
                <tbody>
                  <tr v-for="(c, i) in shownChars" :key="i">
                    <th>{{ c.name || '—' }}</th>
                    <td>{{ charValue(c.value) }}</td>
                  </tr>
                </tbody>
              </table>
              <button
                v-if="item.characteristics.length > CHAR_PREVIEW"
                class="comp-details__brief-more"
                @click="charsOpen = !charsOpen"
              >{{ charsOpen ? 'свернуть' : `показать все ${item.characteristics.length}` }}</button>
            </div>

            <div v-if="recommendations.length" class="comp-details__brief">
              <div class="comp-details__brief-head">
                <span>Рекомендации WB</span>
                <span class="badge bg-light text-dark">{{ recommendations.length }}</span>
              </div>
              <div class="comp-details__recs">
                <a
                  v-for="r in shownRecs"
                  :key="r.nm_id"
                  :href="`https://www.wildberries.ru/catalog/${r.nm_id}/detail.aspx`"
                  target="_blank"
                  rel="noopener"
                  class="comp-details__rec"
                >
                  <span class="comp-details__rec-photo">
                    <CardPhoto :src="r.photo" :alt="r.title || ''" fit="cover" />
                  </span>
                  <span class="comp-details__rec-body">
                    <span class="comp-details__rec-title">{{ r.title || `Карточка ${r.nm_id}` }}</span>
                    <span class="comp-details__rec-meta">
                      <template v-if="r.price">{{ money(r.price) }} · </template>
                      <span class="comp-details__rec-nm">{{ r.nm_id }}</span>
                    </span>
                  </span>
                </a>
              </div>
              <button
                v-if="recommendations.length > REC_PREVIEW"
                class="comp-details__brief-more"
                @click="recsOpen = !recsOpen"
              >{{ recsOpen ? 'свернуть' : `показать все ${recommendations.length}` }}</button>
            </div>

            <div class="comp-details__dates">
              <span v-if="item.collected_at">собрано: {{ fmt(item.collected_at) }}</span>
              <span v-if="item.first_collected_at">в базе с: {{ fmt(item.first_collected_at) }}</span>
              <span v-if="lastActivity">активен: {{ daysAgo(lastActivity) }}</span>
            </div>
          </div>
        </div>

        <!-- §13.2: быстрые чипы поведения -->
        <div class="comp-details__chips">
          <button type="button" class="comp-details__chip" @click="tab = 'behavior'">
            <i class="bi bi-grid-3x3-gap"></i>
            Полки: <b>{{ shelfCounts.shelves_cnt }}</b>
            <span v-if="shelfCounts.avg_pos != null" class="comp-details__chip-muted">· ср. {{ shelfCounts.avg_pos }}</span>
          </button>
          <button type="button" class="comp-details__chip" @click="tab = 'clips'">
            <i class="bi bi-camera-video"></i>
            Клипы: <b>{{ clipsCount }}</b>
            <span v-if="clipsAuthors" class="comp-details__chip-muted">· {{ clipsAuthors }} авт.</span>
          </button>
          <button type="button" class="comp-details__chip" @click="tab = 'behavior'">
            <i class="bi bi-search"></i>
            Топ-10: <b>{{ top10Count }}</b>
          </button>
          <button
            v-if="duplicates"
            type="button"
            class="comp-details__chip"
            @click="tab = 'behavior'"
          >
            <i class="bi bi-copy"></i>
            Дубликаты: <b>{{ money(duplicates.min_price) }}</b>
            <span v-if="duplicates.price_gap_pct != null" class="comp-details__chip-muted">
              · {{ duplicates.price_gap_pct > 0 ? '+' : '' }}{{ duplicates.price_gap_pct }}%
            </span>
          </button>
        </div>

        <ul class="nav nav-tabs comp-details__tabs">
          <li class="nav-item">
            <button type="button" class="nav-link" :class="{ active: tab === 'card' }" @click="tab = 'card'">
              История
            </button>
          </li>
          <li class="nav-item">
            <button type="button" class="nav-link" :class="{ active: tab === 'behavior' }" @click="tab = 'behavior'">
              Поведение
            </button>
          </li>
          <li class="nav-item">
            <button type="button" class="nav-link" :class="{ active: tab === 'clips' }" @click="tab = 'clips'">
              Клипы <span v-if="clipsCount" class="badge bg-light text-dark">{{ clipsCount }}</span>
            </button>
          </li>
          <li class="nav-item">
            <button type="button" class="nav-link" :class="{ active: tab === 'phrases' }" @click="tab = 'phrases'">
              Фразы <span v-if="phraseRows.length" class="badge bg-light text-dark">{{ phraseRows.length }}</span>
            </button>
          </li>
        </ul>

        <!-- История -->
        <template v-if="tab === 'card'">
          <section class="comp-details__section">
            <h6 class="comp-details__section-title">Изменение цены</h6>
            <div v-if="priceChanges.length > 1" class="comp-details__price-hist">
              <table class="comp-details__price-table">
                <thead>
                  <tr>
                    <th>Когда</th>
                    <th>Цена</th>
                    <th>Было</th>
                    <th>Изменение</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(p, i) in priceChanges" :key="i">
                    <td>{{ fmt(p.at) }}</td>
                    <td class="comp-details__num">{{ money(p.price) }}</td>
                    <td class="comp-details__num text-muted">{{ p.old_price ? money(p.old_price) : '—' }}</td>
                    <td class="comp-details__num">
                      <span v-if="i === 0" class="text-muted">—</span>
                      <span v-else :class="priceDiff(p, i) > 0 ? 'text-danger' : 'text-success'">{{ diffLabel(p, i) }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else-if="!priceChanges.length" class="text-muted small">
              Истории цены ещё нет — карточка не пересобиралась.
            </div>
            <div v-else class="text-muted small">
              Цена не менялась<template v-if="item.price">: {{ money(item.price) }}</template>.
            </div>
          </section>

          <section class="comp-details__section">
            <h6 class="comp-details__section-title">
              Привязка
              <span class="badge bg-light text-dark">{{ attachedRows.length }}</span>
            </h6>
            <table v-if="attachedRows.length" class="comp-details__attach-table">
              <thead>
                <tr>
                  <th>Наша карточка</th>
                  <th class="comp-details__num">Источник</th>
                  <th class="comp-details__num">Фраз в выдаче</th>
                  <th class="comp-details__num">Лучшая позиция</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="a in attachedRows" :key="a.nm_id">
                  <td>
                    <div class="comp-details__attach-card">
                      <a :href="`/wb/detail?nm_id=${a.nm_id}`" target="_blank" rel="noopener" class="comp-details__attach-nm">
                        {{ a.nm_id }}
                      </a>
                      <span class="comp-details__attach-title">{{ a.title || '—' }}</span>
                    </div>
                  </td>
                  <td class="comp-details__num">
                    <span class="badge" :class="sourceBadge(a.source)">{{ sourceLabel(a.source) }}</span>
                  </td>
                  <td class="comp-details__num">{{ a.phrases_cnt || '—' }}</td>
                  <td class="comp-details__num">{{ a.best_pos ?? '—' }}</td>
                </tr>
              </tbody>
            </table>
            <div v-else class="text-muted small">
              Не привязан ни к одной нашей карточке.
            </div>
            <div class="comp-details__note">
              <b>Источник</b> — как привязали: карточка — добавили руками в рабочем месте карточки,
              аналог — скопировали с другой нашей карточки, сбор — привязали в «Собранных карточках»
              или в пуле подбора, поиск — расширение нашло в выдаче по нашей фразе (или привязку отвязали).
            </div>
          </section>

          <section class="comp-details__section">
            <h6 class="comp-details__section-title">Сбор</h6>
            <div class="comp-details__capture">
              <span class="comp-details__capture-row">
                <i class="bi" :class="capture.captured_by_us ? 'bi-check2' : 'bi-dash'"></i>
                собрали мы: {{ capture.captured_by_us ? fmt(capture.last_seen_at) : 'нет' }}
              </span>
              <span v-if="capture.first_seen_at" class="comp-details__capture-row">
                <i class="bi bi-clock-history"></i> впервые увидели: {{ fmt(capture.first_seen_at) }}
              </span>
              <span class="comp-details__capture-row">
                <i class="bi bi-people"></i> собрали компании: {{ capture.companies_cnt || 0 }}
              </span>
              <span v-if="capture.is_hidden" class="comp-details__capture-row comp-details__capture-warn">
                <i class="bi bi-exclamation-triangle"></i> исключено из сбора — расширение больше не обновляет
              </span>
            </div>
          </section>
        </template>

        <!-- Поведение -->
        <template v-else-if="tab === 'behavior'">
          <section class="comp-details__section">
            <h6 class="comp-details__section-title">
              Полки WB
              <span class="badge bg-light text-dark">{{ shelfCounts.shelves_cnt }}</span>
            </h6>
            <div class="comp-details__stats">
              <span>полок: <b>{{ shelfCounts.shelves_cnt }}</b></span>
              <span>якорей: <b>{{ shelfCounts.anchors_cnt }}</b></span>
              <span v-if="shelfCounts.avg_pos != null">средняя поз.: <b>{{ shelfCounts.avg_pos }}</b></span>
              <span v-if="shelfCounts.best_pos != null">лучшая: <b>{{ shelfCounts.best_pos }}</b></span>
            </div>

            <h6 class="comp-details__subtitle">Где стоит он — в полках наших карточек</h6>
            <table v-if="shelvesAsItem.length" class="comp-details__chars comp-details__grid">
              <thead>
                <tr>
                  <th>Наша карточка (якорь)</th>
                  <th>Полка</th>
                  <th class="text-center">Поз.</th>
                  <th class="text-center">Цена</th>
                  <th class="text-center">Дата</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(s, i) in shelvesAsItem" :key="i">
                  <td :title="s.anchor_title || ''">
                    <a :href="`https://www.wildberries.ru/catalog/${s.anchor_nm}/detail.aspx`" target="_blank" rel="noopener">
                      {{ s.anchor_nm }}
                    </a>
                    <div class="comp-details__cell-sub">{{ s.anchor_title || '—' }}</div>
                  </td>
                  <td>{{ s.shelf_title || '#' + s.preset_id }}</td>
                  <td class="text-center">{{ s.position ?? '—' }}</td>
                  <td class="text-center">{{ s.price ? money(s.price) : '—' }}</td>
                  <td class="text-center">{{ fmtD(s.snapshot_date) }}</td>
                </tr>
              </tbody>
            </table>
            <div v-else class="text-muted small">В полках наших карточек не встречался.</div>

            <h6 class="comp-details__subtitle">Его полки — что WB рекомендует рядом с ним</h6>
            <table v-if="shelvesAsAnchor.length" class="comp-details__chars comp-details__grid">
              <thead>
                <tr>
                  <th>Полка</th>
                  <th class="text-center">Позиций</th>
                  <th class="text-center">Ср. цена</th>
                  <th class="text-center">Обновлено</th>
                  <th>Мы в полке</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(s, i) in shelvesAsAnchor" :key="i">
                  <td>
                    {{ s.shelf_title || '#' + s.preset_id }}
                    <span v-if="s.is_partial" class="badge bg-warning text-dark" title="Полка снята не целиком">частично</span>
                  </td>
                  <td class="text-center">{{ s.items_cnt ?? '—' }}</td>
                  <td class="text-center">{{ s.avg_price ? money(s.avg_price) : '—' }}</td>
                  <td class="text-center">{{ fmtD(s.last_seen_at) }}</td>
                  <td>
                    <template v-if="s.our_cards?.length">
                      <span class="badge badge--ok">мы</span>
                      <a :href="`/wb/detail?nm_id=${s.our_cards[0].nm_id}`" target="_blank" rel="noopener">
                        {{ s.our_cards[0].nm_id }}
                      </a>
                      <span v-if="s.our_cards[0].position != null" class="text-muted small">поз. {{ s.our_cards[0].position }}</span>
                    </template>
                    <span v-else class="text-muted">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-else class="text-muted small">Полки его карточки ещё не сняты.</div>
          </section>

          <section v-if="positionsList.length" class="comp-details__section">
            <h6 class="comp-details__section-title">
              В выдаче по нашим фразам
              <span class="badge bg-light text-dark">{{ positionsList.length }}</span>
            </h6>
            <div class="comp-details__stats">
              <span>топ-3: <b>{{ top3Count }}</b></span>
              <span>топ-10: <b>{{ top10Count }}</b></span>
            </div>
            <table class="comp-details__chars comp-details__grid">
              <thead>
                <tr>
                  <th>Фраза</th>
                  <th>Наша карточка</th>
                  <th class="text-center">Позиция</th>
                  <th class="text-center">Лучшая</th>
                  <th class="text-center">Δ7д</th>
                  <th class="text-center">Цена</th>
                  <th class="text-center">Дней</th>
                  <th class="text-center">Дата</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(p, i) in positionsList" :key="i">
                  <td :title="p.phrase">
                    {{ p.phrase }}
                    <span v-if="p.last_position && p.last_position <= 10" class="badge bg-success">топ-10</span>
                  </td>
                  <td>
                    <span v-if="p.source_nm_id">
                      {{ p.source_nm_id }}<span v-if="p.source_title"> — {{ p.source_title }}</span>
                    </span>
                    <span v-else class="text-muted">—</span>
                  </td>
                  <td class="text-center">{{ p.last_position ?? '—' }}</td>
                  <td class="text-center">{{ posBest(p) ?? '—' }}</td>
                  <td class="text-center" :class="posDelta(p).cls">{{ posDelta(p).text }}</td>
                  <td class="text-center">
                    <template v-if="p.last_sold_out">Нет в наличии</template>
                    <template v-else>{{ p.last_price ? p.last_price + ' ₽' : '—' }}</template>
                  </td>
                  <td class="text-center">{{ p.days ?? '—' }}</td>
                  <td class="text-center">{{ fmt(p.at) }}</td>
                </tr>
              </tbody>
            </table>
          </section>

          <section v-if="duplicates" class="comp-details__section">
            <h6 class="comp-details__section-title">
              Дубликаты
              <span class="badge bg-light text-dark">match {{ duplicates.match_id }}</span>
            </h6>
            <div class="comp-details__stats">
              <span>его цена: <b>{{ money(duplicates.my_price) }}</b></span>
              <span>минимум: <b>{{ money(duplicates.min_price) }}</b></span>
              <span v-if="duplicates.price_gap_pct != null">
                разрыв: <b :class="duplicates.price_gap_pct < 0 ? 'text-danger' : 'text-success'">
                  {{ duplicates.price_gap_pct > 0 ? '+' : '' }}{{ duplicates.price_gap_pct }}%
                </b>
              </span>
              <span>предложений: <b>{{ duplicates.offers_total }}</b></span>
            </div>
            <table v-if="duplicates.offers.length" class="comp-details__chars comp-details__grid">
              <thead>
                <tr>
                  <th>Товар</th>
                  <th class="text-center">Цена</th>
                  <th>Продавец</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(o, i) in duplicates.offers" :key="i">
                  <td>
                    <a :href="`https://www.wildberries.ru/catalog/${o.nm_id}/detail.aspx`" target="_blank" rel="noopener">{{ o.nm_id }}</a>
                    <span v-if="o.is_min_price" class="badge bg-success">минимум</span>
                    <span v-if="o.is_anchor" class="badge bg-secondary">якорь</span>
                    <div class="comp-details__cell-sub">{{ o.name || '—' }}</div>
                  </td>
                  <td class="text-center">{{ money(o.price) }}</td>
                  <td>{{ o.seller || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </section>

          <section v-if="compareRows.length" class="comp-details__section">
            <h6 class="comp-details__section-title">
              Сравнение с нашей карточкой
              <span class="badge bg-light text-dark">{{ item.compare?.nm_id }}</span>
            </h6>
            <table class="comp-details__chars comp-details__grid">
              <thead>
                <tr>
                  <th>Параметр</th>
                  <th class="text-center">Он</th>
                  <th class="text-center">Мы</th>
                  <th class="text-center">Разница</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in compareRows" :key="r.label">
                  <th>{{ r.label }}</th>
                  <td class="text-center">{{ r.his }}</td>
                  <td class="text-center">{{ r.ours }}</td>
                  <td class="text-center" :class="r.cls">{{ r.diff }}</td>
                </tr>
              </tbody>
            </table>
          </section>
        </template>

        <!-- Клипы -->
        <template v-else-if="tab === 'clips'">
          <section class="comp-details__section">
            <h6 class="comp-details__section-title">
              Клипы карточки
              <span class="badge bg-light text-dark">{{ clipsCount }}</span>
              <span v-if="clipsAuthors" class="comp-details__note-inline">{{ clipsAuthors }} авторов</span>
            </h6>
            <div v-if="clips.length" class="comp-details__clips">
              <div v-for="c in clips" :key="c.clip_id" class="comp-details__clip">
                <a :href="clipUrl(c)" target="_blank" rel="noopener" class="comp-details__clip-thumb">
                  <CardPhoto :src="c.preview_url" :alt="c.description || c.name || ''" fit="cover" />
                </a>
                <div class="comp-details__clip-body">
                  <a :href="clipUrl(c)" target="_blank" rel="noopener" class="comp-details__clip-title">
                    {{ c.description || c.name || 'Клип ' + c.clip_id }}
                  </a>
                  <div class="comp-details__clip-meta">
                    <a
                      v-if="c.author_url"
                      :href="c.author_url"
                      target="_blank"
                      rel="noopener"
                      class="comp-details__clip-author"
                    >{{ c.author_name || 'автор' }}</a>
                    <span v-else-if="c.author_name">{{ c.author_name }}</span>
                    <span v-if="c.author_verified" class="badge bg-success">✓</span>
                    <span v-if="c.publication_date">{{ fmtD(c.publication_date) }}</span>
                    <span v-if="dur(c.duration_s)">{{ dur(c.duration_s) }}</span>
                  </div>
                  <div class="comp-details__clip-meta">
                    <span>товаров: {{ c.nm_count ?? '—' }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="text-muted small">Клипов по этой карточке пока нет.</div>
          </section>
        </template>

        <!-- Фразы -->
        <template v-else>
          <section class="comp-details__section">
            <h6 class="comp-details__section-title">
              Фразы из описания конкурента (ИИ-разбор)
              <span class="badge bg-light text-dark">{{ phraseRows.length }}</span>
              <span class="comp-details__note-inline">
                сведено в группы: {{ mergedCount }} · не сведено: {{ phraseRows.length - mergedCount }}
              </span>
            </h6>

            <table v-if="phraseRows.length" class="comp-details__phrase-table">
              <thead>
                <tr>
                  <th>Фраза конкурента</th>
                  <th v-if="phraseSources.length > 1">Наша карточка</th>
                  <th>Группа</th>
                  <th class="comp-details__num">У конкурентов</th>
                  <th class="comp-details__num">Заказы</th>
                  <th class="comp-details__num">Источник</th>
                  <th class="comp-details__num">Выбрана</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="r in phraseRows"
                  :key="r.key"
                  :class="{ 'is-selected': r.is_selected, 'is-in-db': r.in_db }"
                  :title="r.canon && r.canon !== r.phrase ? `в группе с «${r.canon}»` : ''"
                >
                  <td>
                    {{ r.phrase }}
                    <span v-if="!r.merged" class="badge badge--warn">не сведено</span>
                  </td>
                  <td v-if="phraseSources.length > 1">{{ r.source_nm_id }}</td>
                  <td class="comp-details__canon">{{ r.canon || '—' }}</td>
                  <td class="comp-details__num">{{ r.merged ? (r.hit_cnt || '—') : '—' }}</td>
                  <td class="comp-details__num">{{ r.orders || '—' }}</td>
                  <td class="comp-details__num">
                    <span v-if="r.in_db" class="badge bg-success" title="Такая фраза есть в нашей базе — WB её отдаёт">в базе</span>
                    <span v-else class="badge bg-warning text-dark" title="Нет в нашей базе — новая">новая</span>
                  </td>
                  <td class="comp-details__num">
                    <i v-if="r.is_selected" class="bi bi-check-circle-fill comp-details__ok"></i>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-else class="text-muted small">
              Фразы ещё не разобраны — запустите разбор на карточке или в разделе «Разбор фраз (фон)».
            </div>
          </section>
        </template>
      </template>

      <div class="wb-modal-actions">
        <button class="btn btn-sm btn-secondary" @click="$emit('close')">Закрыть</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  competitorsNewcardApi,
  type CompetitorClip,
  type CompetitorDetail,
  type CompetitorPosition,
} from '../../api/competitorsNewcard'
import { seoApi } from '../../api/seo'
import { copyText } from '../../utils/clipboard'
import CardPhoto from '../common/CardPhoto.vue'

const props = defineProps<{
  open: boolean
  nmId: number | string | null | undefined
  /** Если задан — карточка открыта из /competitor/new-cards/:sourceNmId. */
  sourceNmId?: number | string | null
  /** Откуда грузить: captured (по умолчанию) или pick (пул §16). */
  scope?: 'captured' | 'pick'
  /** Для «Поставить фразу в мониторинг»: наша карточка + фраза выдачи (контекст страницы). */
  ourNmId?: number | string | null
  phrase?: string | null
}>()
defineEmits<{ (e: 'close'): void }>()

type Tab = 'card' | 'behavior' | 'clips' | 'phrases'

/** Сколько характеристик показываем до «показать все». */
const CHAR_PREVIEW = 6
/** Сколько рекомендаций показываем до «показать все». */
const REC_PREVIEW = 4

const item = ref<CompetitorDetail | null>(null)
const loading = ref(false)
const error = ref('')
const copyError = ref('')
const imageIdx = ref(0)
const tab = ref<Tab>('card')
const descOpen = ref(false)
const charsOpen = ref(false)
const recsOpen = ref(false)

const activeImage = computed(() => item.value?.images?.[imageIdx.value] || item.value?.photo || '')
const descLen = computed(() => (item.value?.description || '').length)
const priceChanges = computed(() => (item.value?.price_history || []).filter((p) => !!p.price))
const badgesList = computed(() => (item.value?.badges || []).filter((b) => !!String(b).trim()))
const positionsList = computed(() => item.value?.positions || [])
const shelvesAsItem = computed(() => item.value?.shelves?.as_item || [])
const shelvesAsAnchor = computed(() => item.value?.shelves?.as_anchor || [])
const shelfCounts = computed(() => item.value?.shelves?.counts || {
  shelves_cnt: 0, anchors_cnt: 0, avg_pos: null, best_pos: null,
})
const clips = computed(() => item.value?.clips || [])
const clipsCount = computed(() => item.value?.clips_cnt || 0)
const clipsAuthors = computed(() => item.value?.clips_authors_cnt || 0)
const duplicates = computed(() => item.value?.duplicates || null)
const top3Count = computed(() => positionsList.value.filter((p) => (p.last_position ?? 99) <= 3).length)
const top10Count = computed(() => positionsList.value.filter((p) => (p.last_position ?? 99) <= 10).length)
const wbUrl = computed(() => item.value?.url || `https://www.wildberries.ru/catalog/${props.nmId}/detail.aspx`)

/** Привязки к нашим карточкам (единый источник — `wb_competitor_cards`). */
const attachedRows = computed(() => item.value?.attached_to || [])
/** Реестр сбора (`wb_competitor_capture`) — видимость, не привязка. */
const capture = computed(() => item.value?.capture || {
  captured_by_us: false, is_own: false, is_hidden: false,
  first_seen_at: null, last_seen_at: null, companies_cnt: 0,
})
/** Рекомендации WB (что модель предлагает рядом с карточкой). */
const recommendations = computed(() => item.value?.recommendations || [])
const shownRecs = computed(() =>
  (recsOpen.value ? recommendations.value : recommendations.value.slice(0, REC_PREVIEW)))
/** Характеристики: первые CHAR_PREVIEW, дальше — по кнопке «показать все». */
const shownChars = computed(() => {
  const list = item.value?.characteristics || []
  return charsOpen.value ? list : list.slice(0, CHAR_PREVIEW)
})

/** Частичные данные (нет полного сбор): найдено в wb_competitor_cards/position. */
const isPartial = computed(() => item.value?.found === 'cards' || item.value?.found === 'position')

const collectBusy = ref(false)
const collectDone = ref(false)
const collectErr = ref('')

/** Контекст для очереди мониторинга: наша карточка + фраза выдачи.
 *  Если страница контекст не передала — берём из данных досье. */
const monitorNm = computed(() => {
  const fromPage = Number(props.ourNmId || 0)
  if (fromPage) return fromPage
  return Number(attachedRows.value[0]?.nm_id || 0)
})
const monitorPhrase = computed(() => {
  const fromPage = String(props.phrase || '').trim()
  if (fromPage) return fromPage
  return String(positionsList.value[0]?.phrase || '').trim()
})

/** Фразу в очередь «SEO мониторинг»: сбор фоном расширением обновит выдачу и карточку. */
async function collectInExtension() {
  const ours = Number(monitorNm.value || 0)
  const ph = String(monitorPhrase.value || '')
  if (!ours || !ph) return
  collectBusy.value = true
  collectErr.value = ''
  try {
    await seoApi.addTarget(ours, ph)
    collectDone.value = true
  } catch (e: any) {
    const msg = String(e?.response?.data?.detail || e?.response?.data?.error || '')
    collectErr.value = msg.includes('Уже добавлена') ? 'Эта фраза уже в мониторинге' : (msg || 'Не удалось добавить в мониторинг')
  } finally {
    collectBusy.value = false
  }
}

const copiedNm = ref(false)
const copiedUrl = ref(false)

async function copyNm() {
  if (!props.nmId) return
  if (await copyText(String(props.nmId))) {
    copiedNm.value = true
    setTimeout(() => { copiedNm.value = false }, 1500)
  } else {
    copyError.value = 'Не удалось скопировать nmID'
  }
}

async function copyUrl() {
  if (await copyText(wbUrl.value)) {
    copiedUrl.value = true
    setTimeout(() => { copiedUrl.value = false }, 1500)
  } else {
    copyError.value = 'Не удалось скопировать ссылку'
  }
}

const lastActivity = computed(() => {
  const stamps = [
    item.value?.collected_at,
    item.value?.clips_last_at,
    ...shelvesAsItem.value.map((s) => s.snapshot_date),
    ...positionsList.value.map((p) => p.at),
    duplicates.value?.snapshot_date,
  ].filter(Boolean) as string[]
  if (!stamps.length) return ''
  return stamps.reduce((a, b) => (dateMs(b) > dateMs(a) ? b : a), stamps[0])
})

interface CompareRow { label: string; his: string; ours: string; diff: string; cls: string }

const compareRows = computed<CompareRow[]>(() => {
  const his = item.value
  const ours = his?.compare
  if (!his || !ours) return []
  const rows: CompareRow[] = []
  const push = (label: string, a: number | null | undefined, b: number | null | undefined,
                fmtFn: (v: number) => string, pct = false) => {
    if (a == null && b == null) return
    let diff = '—'
    let cls = 'text-muted'
    if (a != null && b != null) {
      if (pct && a) {
        const d = Math.round(((b - a) / a) * 1000) / 10
        diff = `${d > 0 ? '+' : ''}${d}%`
        cls = d > 0 ? 'text-danger' : d < 0 ? 'text-success' : 'text-muted'
      } else {
        const d = Math.round((b - a) * 100) / 100
        diff = d > 0 ? `+${d}` : String(d)
        cls = d > 0 ? 'text-success' : d < 0 ? 'text-danger' : 'text-muted'
      }
    }
    rows.push({
      label,
      his: a == null ? '—' : fmtFn(a),
      ours: b == null ? '—' : fmtFn(b),
      diff,
      cls,
    })
  }
  const intFmt = (v: number) => v.toLocaleString('ru-RU')
  push('Цена', num(his.price), num(ours.price), money, true)
  push('Описание, симв.', his.description?.length || 0, ours.desc_len, intFmt)
  push('Характеристик', his.characteristics.length, ours.chars_cnt, intFmt)
  push('Рейтинг', his.rating, ours.rating, (v) => String(v))
  push('Оценок', his.feedbacks, ours.feedbacks, intFmt)
  push('Клипов', his.clips_cnt || 0, ours.clips_cnt, intFmt)
  return rows
})

/** Бейдж акции — подсветить скидку/распродажу, остальное нейтрально.
 *  «ресейл» (товар от частного лица) — мятный, как в карточке выдачи. */
function badgeClass(b: string): string {
  const t = String(b).toLowerCase()
  if (/ресейл|resale/.test(t)) return 'comp-details__badge--resale'
  if (/распродаж|скидк|−/.test(t)) return 'bg-danger'
  if (/хорошая цена|кешбэк|выгодн/.test(t)) return 'bg-success'
  return 'bg-light text-dark'
}

/** Подписи источника привязки — «как привязали». */
const SOURCE_LABELS: Record<string, string> = {
  manual: 'карточка',
  sibling: 'аналог',
  capture: 'сбор',
  search: 'поиск',
}

/** Класс бейджа источника (палитра Д — тон темы). */
const SOURCE_BADGES: Record<string, string> = {
  manual: 'badge--info',
  sibling: 'badge--neutral',
  capture: 'badge--ok',
  search: 'badge--warn',
}

function sourceLabel(source?: string | null): string {
  const s = String(source || '')
  return SOURCE_LABELS[s] || s || '—'
}

function sourceBadge(source?: string | null): string {
  return SOURCE_BADGES[String(source || '')] || 'badge--neutral'
}

interface PhraseRow {
  key: string
  phrase: string
  canon?: string | null
  merged: boolean
  source_nm_id: number
  source_title?: string | null
  is_selected: boolean
  hit_cnt: number
  in_db: boolean
  orders: number
}

/** Одна строка = одна исходная формулировка конкурента (в т.ч. несведённая). */
const phraseRows = computed<PhraseRow[]>(() =>
  (item.value?.phrases || []).map((p, i) => ({
    key: `${p.source_nm_id}:${p.phrase_id ?? `raw:${p.phrase}`}:${i}`,
    phrase: p.phrase,
    canon: p.canon || null,
    merged: p.merged !== false && !!p.phrase_id,
    source_nm_id: p.source_nm_id,
    source_title: p.source_title || null,
    is_selected: !!p.is_selected,
    hit_cnt: Number(p.hit_cnt || 0),
    in_db: !!p.in_db,
    orders: Number(p.orders || 0),
  })),
)

const mergedCount = computed(() => phraseRows.value.filter((r) => r.merged).length)

/** Наши карточки, к которым привязан конкурент (для шапки/колонки). */
const phraseSources = computed<Array<{ nm_id: number; title?: string | null }>>(() => {
  const map = new Map<number, { nm_id: number; title?: string | null }>()
  for (const p of item.value?.phrases || []) {
    if (!map.has(p.source_nm_id)) {
      map.set(p.source_nm_id, { nm_id: p.source_nm_id, title: p.source_title || null })
    }
  }
  return [...map.values()]
})

function charValue(v: any): string {
  if (Array.isArray(v)) return v.join('; ')
  return v == null ? '' : String(v)
}

function dateMs(v?: string | null): number {
  if (!v) return 0
  const t = new Date(v).getTime()
  return isFinite(t) ? t : 0
}

function daysAgo(v?: string | null): string {
  const t = dateMs(v)
  if (!t) return ''
  const d = Math.max(0, Math.round((Date.now() - t) / 86400000))
  if (d === 0) return 'сегодня'
  if (d === 1) return 'вчера'
  return `${d} дн. назад`
}

function fmt(v?: string | null): string {
  if (!v) return '—'
  const d = new Date(v)
  return isFinite(d.getTime()) ? d.toLocaleString('ru-RU') : String(v)
}

function fmtD(v?: string | null): string {
  if (!v) return '—'
  const d = new Date(v)
  return isFinite(d.getTime()) ? d.toLocaleDateString('ru-RU') : String(v)
}

function money(v?: string | number | null): string {
  if (v === null || v === undefined || v === '') return '—'
  const s = String(v)
  return s.includes('₽') ? s : `${s} ₽`
}

function num(v?: string | number | null): number | null {
  if (v === null || v === undefined || v === '') return null
  const raw = String(v).trim()
  const n = Number(raw.replace(/[^\d,.-]/g, '').replace(',', '.'))
  return isFinite(n) ? n : null
}

function priceDiff(p: { price?: string | null }, i: number): number {
  const cur = num(p.price)
  const prev = num(priceChanges.value[i - 1]?.price)
  if (cur === null || prev === null) return 0
  return cur - prev
}

function diffLabel(p: { price?: string | null }, i: number): string {
  const d = priceDiff(p, i)
  if (!d) return '0 ₽'
  return `${d > 0 ? '+' : '−'}${Math.abs(d).toLocaleString('ru-RU')} ₽`
}

function posBest(p: CompetitorPosition): number | null {
  const vals = (p.positions || [])
    .map((x) => x.position)
    .filter((v): v is number => v != null)
  return vals.length ? Math.min(...vals) : null
}

/** Δ за 7 дней: плюс = поднялся выше (позиция уменьшилась). */
function posDelta(p: CompetitorPosition): { text: string; cls: string } {
  const h = (p.positions || []).filter((x) => x.position != null)
  if (h.length < 2) return { text: '—', cls: 'text-muted' }
  const last = h[h.length - 1]
  const cutoff = dateMs(last.at) - 7 * 86400000
  let base = h[0]
  for (const x of h) {
    if (dateMs(x.at) && dateMs(x.at) <= cutoff) base = x
  }
  if (base.position == null || last.position == null) return { text: '—', cls: 'text-muted' }
  const d = Number(base.position) - Number(last.position)
  if (!d) return { text: '0', cls: 'text-muted' }
  return { text: d > 0 ? `+${d}` : `−${Math.abs(d)}`, cls: d > 0 ? 'text-success' : 'text-danger' }
}

function clipUrl(c: CompetitorClip): string {
  return c.public_url || `https://wibes.ru/clips/${c.clip_id}`
}

function dur(v?: number | string | null): string {
  const n = Number(v)
  if (!isFinite(n) || n <= 0) return ''
  const s = Math.round(n)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

async function load() {
  const id = Number(props.nmId || 0)
  if (!id) return
  loading.value = true
  error.value = ''
  copyError.value = ''
  item.value = null
  imageIdx.value = 0
  copiedNm.value = false
  copiedUrl.value = false
  collectBusy.value = false
  collectDone.value = false
  collectErr.value = ''
  descOpen.value = false
  charsOpen.value = false
  recsOpen.value = false
  tab.value = 'card'
  try {
    if (props.scope === 'pick') {
      item.value = await competitorsNewcardApi.pickDetails(id)
    } else {
      const source = Number(props.sourceNmId || 0)
      item.value = source
        ? await competitorsNewcardApi.competitorDetails(source, id)
        : await competitorsNewcardApi.capturedDetails(id, Number(props.ourNmId || 0) || null)
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail === 'details not collected'
      ? 'Контент ещё не собран — откройте карточку на WB с расширением.'
      : (e?.response?.data?.detail || 'Не удалось загрузить карточку конкурента')
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.open, props.nmId, props.sourceNmId, props.scope] as const,
  ([isOpen]) => {
    if (isOpen) load()
  },
)
</script>

<style scoped>
/* Выше .page-wb-detail__modal-backdrop (z-index: 1080): досье открывается поверх списка конкурентов. */
.comp-details-backdrop { z-index: 1090; }
.comp-details { width: 980px; max-width: 96vw; max-height: 92vh; overflow: auto; }
.comp-details__head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.comp-details__copy-btn {
  border: none; background: none; padding: 0 3px; color: #6c757d;
  font-size: 13px; cursor: pointer; line-height: 1;
}
.comp-details__copy-btn:hover { color: #0d6efd; }
.comp-details__partial {
  display: flex; flex-wrap: wrap; align-items: center; gap: 10px;
  border: 1px solid #fff3cd; background: #fffdf5; border-radius: 8px;
  padding: 8px 12px; margin-bottom: 14px;
}
.comp-details__partial-note { flex: 1; min-width: 240px; font-size: 13px; color: #664d03; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.comp-details__partial-phrase { color: #8a6d3b; }
.comp-details__title { margin: 0; font-size: 15px; display: flex; align-items: center; gap: 8px; }
.comp-details__top { display: flex; gap: 18px; align-items: flex-start; flex-wrap: wrap; }
.comp-details__gallery { flex: 0 0 240px; width: 240px; }
/* Фото — через CardPhoto (локальный кэш /api/img, заглушка сама). */
.comp-details__main {
  width: 100%; height: 210px; border: 1px solid #e5e7eb; border-radius: 8px;
  background: #f8f9fa; overflow: hidden;
}
.comp-details__thumbs { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.comp-details__thumb {
  width: 40px; height: 52px; padding: 0; border: 2px solid transparent; border-radius: 4px;
  cursor: pointer; background: #f8f9fa; overflow: hidden; line-height: 0;
}
.comp-details__thumb.is-active { border-color: #0d6efd; }
.comp-details__preview-note { margin-top: 6px; font-size: 12px; color: #8a6d3b; }
.comp-details__info { flex: 1; min-width: 300px; }
.comp-details__name { font-size: 18px; font-weight: 600; line-height: 1.3; }
.comp-details__meta { display: flex; flex-wrap: wrap; gap: 4px 14px; margin-top: 8px; font-size: 13px; color: #555; }
.comp-details__price { margin-top: 12px; display: flex; align-items: baseline; gap: 10px; }
.comp-details__price-now { font-size: 24px; font-weight: 700; color: #2c3e50; }
.comp-details__price-old { font-size: 15px; color: #999; text-decoration: line-through; }
.comp-details__badges { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
.comp-details__dates { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 10px; font-size: 12px; color: #777; }

/* Описание/характеристики/рекомендации — блоки в шапке */
.comp-details__brief { margin-top: 12px; border: 1px solid #eceef0; border-radius: 8px; padding: 8px 10px; background: #fcfcfd; }
.comp-details__brief-head { display: flex; align-items: center; gap: 8px; font-size: 11px; text-transform: uppercase; letter-spacing: .03em; color: #888; font-weight: 600; margin-bottom: 4px; }
.comp-details__brief-text { font-size: 12.5px; line-height: 1.5; color: #333; white-space: pre-wrap; }
.comp-details__brief-text.is-clamp { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.comp-details__brief-more { border: none; background: none; padding: 2px 0; font-size: 11.5px; color: #0d6efd; cursor: pointer; }
.comp-details__chars { width: 100%; font-size: 12px; border-collapse: collapse; }
.comp-details__chars th, .comp-details__chars td { padding: 3px 6px; border-bottom: 1px solid #f1f1f1; vertical-align: top; text-align: left; }
.comp-details__chars th { width: 45%; color: #555; font-weight: 600; }
.comp-details__recs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 6px; }
.comp-details__rec { display: flex; gap: 8px; align-items: center; padding: 6px 8px; border: 1px solid #e5e7eb; border-radius: 6px; color: inherit; text-decoration: none; background: #fff; }
.comp-details__rec:hover { border-color: #0d6efd; background: #f8fbff; }
.comp-details__rec-photo { flex: 0 0 34px; width: 34px; height: 44px; border-radius: 4px; background: #f1f3f5; overflow: hidden; }
.comp-details__rec-body { min-width: 0; }
.comp-details__rec-title { font-size: 12px; line-height: 1.3; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.comp-details__rec-meta { font-size: 11px; color: #888; margin-top: 3px; }
.comp-details__rec-nm { font-family: monospace; font-size: 11px; color: #0d6efd; }

/* §13.2 */
.comp-details__chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0 4px; }
.comp-details__chip {
  display: inline-flex; align-items: center; gap: 5px; padding: 6px 10px;
  font-size: 12px; border: 1px solid #e5e7eb; border-radius: 999px;
  background: #fafbfc; color: #374151; cursor: pointer;
}
.comp-details__chip:hover { border-color: #0d6efd; color: #0d6efd; }
.comp-details__chip b { font-weight: 700; }
.comp-details__chip-muted { color: #9ca3af; }
.comp-details__tabs { margin-top: 12px; }
.comp-details__tabs .nav-link { font-size: 13px; padding: 6px 12px; color: #4b5563; }
.comp-details__tabs .nav-link.active { font-weight: 600; }
.comp-details__clips { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.comp-details__clip {
  display: flex; gap: 10px; padding: 8px; border: 1px solid #e5e7eb;
  border-radius: 8px; color: inherit; text-decoration: none; background: #fff;
}
.comp-details__clip:hover { border-color: #0d6efd; background: #f8fbff; }
.comp-details__clip-thumb { flex: 0 0 64px; width: 64px; height: 84px; border-radius: 6px; overflow: hidden; background: #f3f4f6; display: block; }
.comp-details__clip-body { min-width: 0; }
.comp-details__clip-title {
  font-size: 12px; line-height: 1.35; max-height: 48px; overflow: hidden;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  color: #1f2937; text-decoration: none;
}
.comp-details__clip-title:hover { color: #0d6efd; text-decoration: underline; }
.comp-details__clip-meta { display: flex; flex-wrap: wrap; gap: 4px 8px; font-size: 11px; color: #6b7280; margin-top: 4px; }
.comp-details__clip-author { color: #0d6efd; text-decoration: none; }
.comp-details__clip-author:hover { text-decoration: underline; }
.comp-details__section { border-top: 1px solid #eee; margin-top: 16px; padding-top: 12px; }
.comp-details__section-title { font-size: 13px; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
.comp-details__subtitle { font-size: 12px; font-weight: 600; color: #555; margin: 12px 0 6px; }
.comp-details__stats { display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: 12px; color: #555; margin-bottom: 8px; }
.comp-details__grid { width: 100%; font-size: 13px; border-collapse: collapse; }
.comp-details__grid th, .comp-details__grid td { padding: 4px 8px; border-bottom: 1px solid #f1f1f1; vertical-align: top; }
.comp-details__grid th { width: 35%; text-align: left; color: #555; font-weight: 600; }
.comp-details__grid td.text-center, .comp-details__grid th.text-center { text-align: center; white-space: nowrap; }
.comp-details__cell-sub { font-size: 11px; color: #888; max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.comp-details__price-table { width: 100%; font-size: 13px; border-collapse: collapse; }
.comp-details__price-table th, .comp-details__price-table td { padding: 5px 8px; border-bottom: 1px solid #f1f1f1; text-align: left; }
.comp-details__price-table th { font-size: 11px; text-transform: uppercase; letter-spacing: .03em; color: #888; font-weight: 600; }
.comp-details__num { white-space: nowrap; }
.comp-details__num.text-center { text-align: center; }

/* Привязка */
.comp-details__attach-table { width: 100%; font-size: 13px; border-collapse: collapse; }
.comp-details__attach-table th, .comp-details__attach-table td { padding: 5px 8px; border-bottom: 1px solid #f1f1f1; vertical-align: top; }
.comp-details__attach-table th { font-size: 11px; text-transform: uppercase; letter-spacing: .03em; color: #888; font-weight: 600; text-align: left; }
.comp-details__attach-table td.comp-details__num { text-align: center; white-space: nowrap; }
.comp-details__attach-card { display: flex; align-items: baseline; gap: 8px; }
.comp-details__attach-nm { font-family: monospace; font-size: 12px; color: #0d6efd; white-space: nowrap; }
.comp-details__attach-title { color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 420px; }
.comp-details__note { font-size: 11.5px; color: #6b7280; margin-top: 6px; }
.comp-details__note-inline { font-size: 12px; font-weight: 400; color: #6b7280; }

/* Сбор */
.comp-details__capture { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 12.5px; color: #555; }
.comp-details__capture-row { display: flex; align-items: center; gap: 6px; }
.comp-details__capture-warn { color: #c2830b; }

/* Фразы */
.comp-details__phrase-table { width: 100%; font-size: 13px; border-collapse: collapse; }
.comp-details__phrase-table th, .comp-details__phrase-table td { padding: 4px 8px; border-bottom: 1px solid #f1f1f1; vertical-align: top; }
.comp-details__phrase-table th { font-size: 11px; text-transform: uppercase; letter-spacing: .03em; color: #888; font-weight: 600; text-align: left; }
.comp-details__phrase-table td.comp-details__num { text-align: center; white-space: nowrap; }
.comp-details__phrase-table tbody tr.is-selected { background: #f2fbf6; }
.comp-details__phrase-table tbody tr.is-in-db td:first-child { box-shadow: inset 3px 0 0 #2e7d32; }
.comp-details__canon { color: #6b7280; font-size: 12px; }
.comp-details__ok { color: #2e7d32; }
/* Ресейл (товар от частного лица) — мятный, как бейдж в карточке выдачи. */
.comp-details__badge--resale {
  background: #8bf7d0;
  color: #063d2c;
}
</style>
