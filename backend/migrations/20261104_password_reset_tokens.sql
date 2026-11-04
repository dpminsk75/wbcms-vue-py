-- Одноразовые ссылки для смены пароля: новый тип токена в auth_invite_tokens.
-- company/user — регистрация, password_reset — сброс пароля (3 дня, одноразовый).
-- Таблица переносится дампом БД целиком; миграция локальна, в git не коммитится.
ALTER TABLE `auth_invite_tokens`
  MODIFY COLUMN `token_type` ENUM('company', 'user', 'password_reset') NOT NULL;
