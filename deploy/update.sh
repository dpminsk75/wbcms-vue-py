#!/bin/bash
# update.sh — штатное обновление wbcms-py + wbcms-web одной командой (dev-wb).
# Лежит в /var/www/wb/deploy/update.sh. Раскладка сервера (трёхкорневая):
#   бэк    /var/www/wb/wbcms-py   (backend/, .venv, .env)
#   фронт  /var/www/wb/wbcms-web  (src/, package.json)
#   деплой /var/www/wb/deploy    (этот скрипт, *.service, *.timer, *.sudoers)
# Запуск:  bash /var/www/wb/deploy/update.sh
# Делает: py_compile → юниты в /etc/systemd/system → sudoers → daemon-reload →
# enable таймеров → restart сервисов → health-check. Миграции БД — отдельно
# руками (mysql yii2basic < .../backend/migrations/<новая>.sql) ДО рестарта.
set -u
PY=/var/www/wb/wbcms-py
WEB=/var/www/wb/wbcms-web
DEPLOY=/var/www/wb/deploy

echo "== 1. синтаксис (ловит недокопированные файлы)"
python3 -m py_compile "$PY/backend/main.py" "$PY"/backend/routers/*.py "$PY"/backend/services/*.py "$PY"/backend/workers/*.py || exit 1

echo "== 2. юниты systemd"
sudo cp "$DEPLOY"/wbcms-py.service "$DEPLOY"/wbcms-web.service \
  "$DEPLOY"/wbcms-py-healthcheck.service "$DEPLOY"/wbcms-py-healthcheck.timer \
  "$DEPLOY"/wbcms-wb-tokens.service "$DEPLOY"/wbcms-wb-tokens.timer \
  "$DEPLOY"/wbcms-commission-tariffs.service "$DEPLOY"/wbcms-commission-tariffs.timer \
  "$DEPLOY"/wbcms-fbs-supplies.service "$DEPLOY"/wbcms-fbs-supplies.timer \
  "$DEPLOY"/wbcms-finance-balance.service "$DEPLOY"/wbcms-finance-balance.timer \
  "$DEPLOY"/wbcms-funnel-sync.service "$DEPLOY"/wbcms-funnel-sync.timer \
  "$DEPLOY"/wbcms-funnel-missing.service "$DEPLOY"/wbcms-funnel-missing.timer \
  "$DEPLOY"/wbcms-adv-queries.service "$DEPLOY"/wbcms-adv-queries.timer \
  "$DEPLOY"/wbcms-adv-index.service "$DEPLOY"/wbcms-adv-index.timer \
  /etc/systemd/system/

if [ -f "$DEPLOY/wbcms-timers.sudoers" ]; then
  echo "== 3. sudoers для админки таймеров"
  sudo cp "$DEPLOY/wbcms-timers.sudoers" /etc/sudoers.d/wbcms-timers
  sudo chmod 440 /etc/sudoers.d/wbcms-timers
  sudo visudo -c || exit 1
fi

echo "== 4. reload + таймеры"
sudo systemctl daemon-reload
sudo systemctl enable --now \
  wbcms-py-healthcheck.timer wbcms-wb-tokens.timer \
  wbcms-commission-tariffs.timer wbcms-fbs-supplies.timer wbcms-finance-balance.timer \
  wbcms-funnel-sync.timer wbcms-funnel-missing.timer wbcms-adv-queries.timer \
  wbcms-adv-index.timer
systemctl list-timers 'wbcms-*' --no-pager

echo "== 5. рестарт сервисов + health"
sudo systemctl restart wbcms-py wbcms-web
sleep 3
curl -sf --max-time 15 http://127.0.0.1:8000/health && echo " HEALTH OK"
echo "Фронт: Ctrl+F5 в браузере. Если менялся frontend/package.json: cd $WEB && npm install + restart wbcms-web."
