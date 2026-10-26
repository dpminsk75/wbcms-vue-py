-- Теги per-company (как wb_reply_rules/capture). В tag_card_links company не нужна — следует из тега.
ALTER TABLE tags ADD COLUMN company_id INT NOT NULL AFTER priority;

-- в базе одна компания (id=1) — бэкфилл на неё
UPDATE tags SET company_id = 1;

ALTER TABLE tags ADD KEY idx_tags_company (company_id);
ALTER TABLE tags ADD CONSTRAINT fk_tags_company
  FOREIGN KEY (company_id) REFERENCES companies (id) ON DELETE CASCADE;
