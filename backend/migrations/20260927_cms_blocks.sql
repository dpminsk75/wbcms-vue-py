-- CMS-блоки: мелкие тексты страниц в БД (Markdown), правит только global_admin.
-- Пилот: два блока гайда расширения. Пусто/нет строки — фронт показывает вшитый fallback.
CREATE TABLE IF NOT EXISTS `cms_blocks` (
  `key` VARCHAR(100) NOT NULL COMMENT 'ext-install-sources, ...',
  `title` VARCHAR(200) NOT NULL DEFAULT '',
  `body_md` MEDIUMTEXT NOT NULL,
  `updated_by` INT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`key`),
  CONSTRAINT `fk_cms_blocks_user` FOREIGN KEY (`updated_by`) REFERENCES `user` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO `cms_blocks` (`key`, `title`, `body_md`) VALUES
('ext-install-sources', 'Откуда берутся фразы',
'**Откуда берутся фразы** (выбор в popup):\n\n- **По фразам из карточки** — SEO-цели товара: ведутся в [SEO-рекомендациях](/seo/index) (открыть рекомендацию → блок целей, фразы с приоритетом).\n- **ТОП-20 поисковых фраз** — фразы с заказами из отчётов WB: посмотреть можно в [«Карточка → фразы»](/wb-search/card) (ввести nmID товара).\n- **Оба вместе** — сначала цели, потом добор из ТОП-20.'),
('ext-install-filters', 'Фильтр категорий',
'**Фильтр категорий** — дропдаун в popup ограничивает выдачу WB выбранными subject-id (`&xsubject=`). Наборы заводятся [здесь, в блоке «Фильтры категорий»](/ext/install?block=filters) (например «Книги и журналы», «Канцтовары»); «Без фильтра» — вся выдача. Расширение подтягивает список само при открытии popup.');
