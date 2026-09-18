from fastapi import FastAPI, Depends, Query, Body, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.deps import get_current_user, get_optional_user, require_admin, get_current_company
from backend.routers import auth_router, companies_router, dashboard_router, admin_router, tags_router, wb_search_router, cost_router, wb_orders_router, wb_sales_router, feedback_router, reply_rules_router, wb_tokens_router, wb_tokens_expiring_router
from backend.services import auth_service as AuthService
from backend.services.orders_service import OrdersService
from backend.services.orders_aggregated_service import OrdersAggregatedService
from backend.services.unclaimed_orders_service import UnclaimedOrdersService
from backend.services.heatmap_service import HeatmapService
from backend.services.sales_analysis_service import SalesAnalysisService
from backend.services.wb_card_service import WbCardService
from backend.services.wb_detail_service import WbDetailService
from backend.services.sales_funnel_service import SalesFunnelService
from backend.services.adv_report_service import AdvReportService
from backend.services.top_products_service import TopProductsService

app = FastAPI(title="wbcms-py dashboard proto")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://31.130.204.146:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
app.include_router(auth_router)
app.include_router(companies_router)
app.include_router(dashboard_router)
app.include_router(admin_router)
app.include_router(tags_router)
app.include_router(wb_search_router)
app.include_router(cost_router)
app.include_router(wb_orders_router)
app.include_router(wb_sales_router)
app.include_router(feedback_router)
app.include_router(reply_rules_router)
app.include_router(wb_tokens_router)
app.include_router(wb_tokens_expiring_router)

class QuickButton(BaseModel):
    icon: str
    label: str
    nm_id: int

class LoginIn(BaseModel):
    username: str
    password: str

@app.post("/api/auth/login")
async def login(payload: LoginIn, request: Request, db: AsyncSession = Depends(get_db)):
    """Замена SiteController login + LoginForm — проверяет bcrypt-хэш из таблицы `user`.
    Принимает username ИЛИ email (как yii2 LoginForm)."""
    login = payload.username.strip()
    user = await AuthService.get_user_by_username(db, login)
    if not user and "@" in login:
        user = await AuthService.get_user_by_email(db, login)
    if not user or not AuthService.verify_password(payload.password, user.get("password_hash") or ""):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    if user.get("blocked_at") is not None:
        raise HTTPException(status_code=403, detail="Пользователь заблокирован")
    pp = await AuthService.get_user_perms(db, int(user["id"]))
    token = AuthService.create_token(int(user["id"]), user["username"])
    ip = request.client.host if request.client else None
    await AuthService.touch_login(db, int(user["id"]), ip)
    return {
        "token": token,
        "user": {"id": user["id"], "username": user["username"], "email": user.get("email")},
        "roles": pp["roles"],
        "perms": pp["all"],
    }


@app.get("/health")
def health():
    return {"ok": True}

@app.get("/api/orders/feed")
async def orders_feed(
    nm_id: int | None = Query(default=None),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    status: str | None = Query(default=None),
    warehouse_name: str | None = Query(default=None),
    region_name: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    from datetime import date as _date
    df = date_from or _date.today().isoformat()
    dt = date_to or _date.today().isoformat()
    svc = OrdersService(db, company_id=company_id)
    return await svc.feed(nm_id, df, dt, status, warehouse_name, region_name, page, 50)


@app.get("/api/unclaimed-orders")
async def unclaimed_orders(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    nm_id: int | None = Query(default=None, ge=1),
    percent: float | None = Query(default=None),
    min_orders: int | None = Query(default=None),
    sort: str = Query(default="rate"),
    sort_dir: str = Query(default="DESC", alias="dir"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = UnclaimedOrdersService(db, company_id=company_id)
    return await svc.search(date_from, date_to, nm_id, percent, min_orders, sort, sort_dir, page, page_size)


@app.get("/api/orders/feed/options")
async def orders_feed_options(
    nm_id: int | None = Query(default=None),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    status: str | None = Query(default=None),
    warehouse_name: str | None = Query(default=None),
    region_name: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    from datetime import date as _date
    df = date_from or _date.today().isoformat()
    dt = date_to or _date.today().isoformat()
    svc = OrdersService(db, company_id=company_id)
    return await svc.feed_options(nm_id, df, dt, status, warehouse_name, region_name)

@app.get("/api/orders/feed-aggregated")
async def orders_feed_aggregated(
    nm_id: int | None = Query(default=None),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    sort_by: str = Query(default="count"),
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    from datetime import date as _date, timedelta
    df = date_from or (_date.today() - timedelta(days=13)).isoformat()  # 14д включительно = 2 недели, было 6д как в WbOrderController.php:103
    dt = date_to or _date.today().isoformat()
    svc = OrdersAggregatedService(db, company_id=company_id)
    return await svc.feed_aggregated(nm_id, df, dt, sort_by, page, 50)

@app.get("/api/orders/heatmap")
async def orders_heatmap(
    nm_id: int | None = Query(default=None),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    from datetime import date as _date, timedelta
    df = date_from or (_date.today() - timedelta(days=14)).isoformat()  # getDPWidget::getParams(14) в WbOrderController.php:136
    dt = date_to or (_date.today() - timedelta(days=1)).isoformat()
    svc = HeatmapService(db, company_id=company_id)
    return await svc.get_heatmap(nm_id, df, dt)

@app.get("/api/adv-report/campaigns")
async def adv_campaigns(db: AsyncSession = Depends(get_db), company_id: int | None = Depends(get_current_company)):
    svc = AdvReportService(db, company_id=company_id)
    return await svc.get_campaign_list()

@app.get("/api/adv-report")
async def adv_report(
    id: int | None = Query(default=None, alias="id"),
    date_from: str = Query(default=None, alias="date_from"),
    date_to: str = Query(default=None, alias="date_to"),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    from datetime import date as _date, timedelta
    df = date_from or (_date.today() - timedelta(days=14)).isoformat()  # WbAdvReportController.php:23
    dt = date_to or _date.today().isoformat()
    svc = AdvReportService(db, company_id=company_id)
    if id is None:
        return {"campaignList": await svc.get_campaign_list(), "date_from": df, "date_to": dt}
    data = await svc.get_detail(id, df, dt)
    if data is None:
        return {"detail": "campaign not found", "id": id}
    data["campaignList"] = await svc.get_campaign_list()
    data["date_from"] = df
    data["date_to"] = dt
    return data


@app.get("/api/sales-analysis/top")
async def sales_analysis_top(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    report_type: str = Query(default="revenue"),
    top_limit: int = Query(default=20),
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    type: str | None = Query(default=None, alias="type"),
    country: str | None = Query(default=None),
    region: str | None = Query(default=None),
    oblast: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = SalesAnalysisService(db, company_id=company_id)
    return await svc.get_top(date_from, date_to, report_type, top_limit, brand, category, type, country, region, oblast)

@app.get("/api/sales-analysis/filters")
async def sales_analysis_filters(db: AsyncSession = Depends(get_db), company_id: int | None = Depends(get_current_company)):
    svc = SalesAnalysisService(db, company_id=company_id)
    return await svc.get_filter_data()

@app.get("/api/sales-analysis/districts")
async def sales_analysis_districts(country: str = Query(default=""), db: AsyncSession = Depends(get_db), company_id: int | None = Depends(get_current_company)):
    svc = SalesAnalysisService(db, company_id=company_id)
    return await svc.get_districts(country)

@app.get("/api/sales-analysis/regions")
async def sales_analysis_regions(country: str = Query(default=""), oblast: str | None = Query(default=None), db: AsyncSession = Depends(get_db), company_id: int | None = Depends(get_current_company)):
    svc = SalesAnalysisService(db, company_id=company_id)
    return await svc.get_regions(country, oblast)

@app.get("/api/sales-analysis/types")
async def sales_analysis_types(category: str = Query(default=""), db: AsyncSession = Depends(get_db), company_id: int | None = Depends(get_current_company)):
    svc = SalesAnalysisService(db, company_id=company_id)
    return await svc.get_types(category)

@app.get("/api/wb/cards")
async def wb_cards(q: str | None = Query(default=None), limit: int = Query(default=50, ge=1, le=200), db: AsyncSession = Depends(get_db), company_id: int | None = Depends(get_current_company)):
    svc = WbCardService(db, company_id=company_id)
    return await svc.list_cards(q, limit)

@app.get("/api/wb/detail/stocks")
async def wb_detail_stocks(nm_id: int = Query(..., ge=1), db: AsyncSession = Depends(get_db), company_id: int | None = Depends(get_current_company)):
    svc = WbDetailService(db, company_id=company_id)
    wh = await svc.get_warehouse_stocks(nm_id)
    way = await svc.get_in_way_stocks(nm_id)
    return {"warehouse": wh, "inWay": way}

@app.get("/api/wb/detail/paid-storage")
async def wb_detail_paid_storage(nm_id: int = Query(..., ge=1), date_from: str = Query(...), date_to: str = Query(...), db: AsyncSession = Depends(get_db), company_id: int | None = Depends(get_current_company)):
    svc = WbDetailService(db, company_id=company_id)
    return await svc.get_paid_storage(nm_id, date_from, date_to)

@app.get("/api/wb/detail/adv")
async def wb_detail_adv(nm_id: int = Query(..., ge=1), date_from: str = Query(...), date_to: str = Query(...), db: AsyncSession = Depends(get_db), company_id: int | None = Depends(get_current_company)):
    svc = WbDetailService(db, company_id=company_id)
    return await svc.get_adv(nm_id, date_from, date_to)

@app.get("/api/wb/detail/funnel")
async def wb_detail_funnel(nm_id: int = Query(..., ge=1), date_from: str = Query(...), date_to: str = Query(...), db: AsyncSession = Depends(get_db), company_id: int | None = Depends(get_current_company)):
    svc = WbDetailService(db, company_id=company_id)
    return await svc.get_funnel(nm_id, date_from, date_to)

@app.get("/api/wb/detail/order-stats")
async def wb_detail_order_stats(nm_id: int = Query(..., ge=1), date_from: str = Query(...), date_to: str = Query(...), db: AsyncSession = Depends(get_db), company_id: int | None = Depends(get_current_company)):
    svc = WbDetailService(db, company_id=company_id)
    return await svc.get_order_stats(nm_id, date_from, date_to)

@app.get("/api/wb/detail/orders-daily")
async def wb_detail_orders_daily(nm_id: int = Query(..., ge=1), date_from: str = Query(...), date_to: str = Query(...), db: AsyncSession = Depends(get_db), company_id: int | None = Depends(get_current_company)):
    svc = WbDetailService(db, company_id=company_id)
    return await svc.get_daily_orders(nm_id, date_from, date_to)

@app.get("/api/wb/detail/sales-daily")
async def wb_detail_sales_daily(nm_id: int = Query(..., ge=1), date_from: str = Query(...), date_to: str = Query(...), db: AsyncSession = Depends(get_db), company_id: int | None = Depends(get_current_company)):
    svc = WbDetailService(db, company_id=company_id)
    return await svc.get_daily_sales(nm_id, date_from, date_to)

@app.get("/api/wb/detail/weekly")
async def wb_detail_weekly(nm_id: int = Query(..., ge=1), date_from: str = Query(...), date_to: str = Query(...), db: AsyncSession = Depends(get_db), company_id: int | None = Depends(get_current_company)):
    svc = WbDetailService(db, company_id=company_id)
    return await svc.get_weekly_finance(nm_id, date_from, date_to)

@app.get("/api/wb/detail/phrases")
async def wb_detail_phrases(nm_id: int = Query(..., ge=1), date_from: str = Query(...), date_to: str = Query(...), db: AsyncSession = Depends(get_db), company_id: int | None = Depends(get_current_company)):
    svc = WbDetailService(db, company_id=company_id)
    return await svc.get_phrases(nm_id, date_from, date_to)

@app.get("/api/wb/card/{nm_id}")
async def wb_card(nm_id: int, db: AsyncSession = Depends(get_db), company_id: int | None = Depends(get_current_company)):
    svc = WbCardService(db, company_id=company_id)
    data = await svc.get_card(nm_id)
    if not data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="card not found")
    return data

@app.get("/api/wb-sales-funnel/wbcard")
async def wb_sales_funnel_wbcard(
    nm_id: int = Query(..., ge=1),
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = SalesFunnelService(db, company_id=company_id)
    return await svc.get_card_funnel(nm_id, date_from, date_to)

@app.get("/api/wb-sales-funnel/wbcard/export")
async def wb_sales_funnel_wbcard_export(
    nm_id: int = Query(..., ge=1),
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = SalesFunnelService(db, company_id=company_id)
    rows = await svc.export_rows(nm_id, date_from, date_to)
    return svc.build_xlsx_response(rows, nm_id, date_from, date_to)

@app.get("/api/wb-profit/top-products")
async def wb_profit_top_products(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    sort_by: str = Query(default="qnt"),
    limit: int = Query(default=20),
    db: AsyncSession = Depends(get_db),
    company_id: int | None = Depends(get_current_company),
):
    svc = TopProductsService(db, company_id=company_id)
    return await svc.get_top_products(date_from, date_to, sort_by, limit)

@app.get("/api/config/quick-buttons")
def get_quick_buttons():
    """Отдает backend/config/quick_buttons.json — замена AdminQuickButtons.php:46 (было только admin, теперь один пользователь=админ)"""
    import json, pathlib
    p = pathlib.Path(__file__).parent / "config" / "quick_buttons.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []

@app.put("/api/config/quick-buttons")
def put_quick_buttons(payload: list[QuickButton], _admin: dict = Depends(require_admin)):
    """Сохраняет backend/config/quick_buttons.json — только admin (было открыто всем)"""
    import json, pathlib
    # валидация
    for i, b in enumerate(payload):
        if not b.label.strip():
            raise HTTPException(status_code=400, detail=f"row {i}: label пуст")
        if not b.icon.strip():
            raise HTTPException(status_code=400, detail=f"row {i}: icon пуст")
        if b.nm_id <= 0:
            raise HTTPException(status_code=400, detail=f"row {i}: nm_id некорректен")
    p = pathlib.Path(__file__).parent / "config" / "quick_buttons.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    data = [b.model_dump() for b in payload]
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "count": len(data)}

@app.get("/api/config/icons")
def get_icons():
    """Списки иконок для пикера — 2 шрифта: bootstrap-icons (bi) и font-awesome (fas/fa-solid)"""
    bi = [
        "bi bi-journal-text","bi bi-journal","bi bi-book","bi bi-bookmark","bi bi-bookmark-star","bi bi-newspaper",
        "bi bi-grid-3x3-gap","bi bi-grid","bi bi-palette","bi bi-palette2","bi bi-brush","bi bi-paint-bucket",
        "bi bi-scissors","bi bi-cut","bi bi-rulers","bi bi-pencil","bi bi-pen","bi bi-vector-pen",
        "bi bi-box","bi bi-box-seam","bi bi-bag","bi bi-bag-check","bi bi-bag-plus","bi bi-basket","bi bi-cart","bi bi-cart-check","bi bi-cart-plus",
        "bi bi-heart","bi bi-heart-fill","bi bi-star","bi bi-star-fill","bi bi-gem","bi bi-gift","bi bi-award",
        "bi bi-tag","bi bi-tags","bi bi-bookmarks","bi bi-collection","bi bi-layers","bi bi-stack",
        "bi bi-camera","bi bi-image","bi bi-images","bi bi-eye","bi bi-eye-fill","bi bi-lightbulb","bi bi-magic",
        "bi bi-fire","bi bi-droplet","bi bi-flower1","bi bi-flower2","bi bi-flower3","bi bi-emoji-smile","bi bi-snow","bi bi-sun","bi bi-moon",
        "bi bi-house","bi bi-shop","bi bi-building","bi bi-cup-hot","bi bi-bucket","bi bi-puzzle","bi bi-hexagon","bi bi-diamonds",
        "bi bi-clock","bi bi-calendar","bi bi-calendar-check","bi bi-alarm","bi bi-bell","bi bi-flag","bi bi-pin","bi bi-geo-alt",
        "bi bi-shield","bi bi-patch-check","bi bi-info-circle","bi bi-question-circle","bi bi-exclamation-triangle",
        "bi bi-graph-up","bi bi-bar-chart","bi bi-pie-chart","bi bi-clipboard","bi bi-clipboard-check","bi bi-file-text","bi bi-folder",
        "bi bi-gear","bi bi-tools","bi bi-wrench","bi bi-plug","bi bi-lightning","bi bi-person","bi bi-people",
    ]
    fa = [
        "fas fa-book","fas fa-book-open","fas fa-bookmark","fas fa-newspaper","fas fa-scroll","fas fa-ruler-combined","fas fa-ruler","fas fa-pencil-ruler",
        "fas fa-cut","fas fa-palette","fas fa-paint-brush","fas fa-brush","fas fa-th","fas fa-th-large","fas fa-layer-group","fas fa-cubes",
        "fas fa-box","fas fa-box-open","fas fa-shopping-bag","fas fa-shopping-cart","fas fa-gift","fas fa-heart","fas fa-star","fas fa-gem",
        "fas fa-tag","fas fa-tags","fas fa-camera","fas fa-image","fas fa-eye","fas fa-lightbulb","fas fa-magic","fas fa-fire","fas fa-tint",
        "fas fa-leaf","fas fa-seedling","fas fa-snowflake","fas fa-sun","fas fa-moon","fas fa-home","fas fa-store","fas fa-building",
        "fas fa-coffee","fas fa-utensils","fas fa-puzzle-piece","fas fa-shapes","fas fa-grip","fas fa-clock","fas fa-calendar","fas fa-calendar-check",
        "fas fa-bell","fas fa-flag","fas fa-map-marker-alt","fas fa-map-pin","fas fa-shield-alt","fas fa-check-circle","fas fa-info-circle",
        "fas fa-chart-line","fas fa-chart-bar","fas fa-chart-pie","fas fa-clipboard","fas fa-clipboard-check","fas fa-file-alt","fas fa-folder",
        "fas fa-cog","fas fa-tools","fas fa-wrench","fas fa-plug","fas fa-bolt","fas fa-user","fas fa-users","fas fa-mitten","fas fa-socks","fas fa-hat-wizard",
        "fas fa-tshirt","fas fa-vest","fas fa-sync-alt","fas fa-calendar-alt","fas fa-th-list","fas fa-border-all",
    ]
    return {"bi": bi, "fa": fa}

@app.get("/api/config/menu")
def get_menu_raw():
    """Отдает raw backend/config/menu.json для визуального редактора AdminMenu.vue"""
    import json, pathlib
    p = pathlib.Path(__file__).parent / "config" / "menu.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/config/menu")
def put_menu_raw(payload: list[dict] = Body(...), _admin: dict = Depends(require_admin)):
    """Сохраняет backend/config/menu.json — только admin"""
    import json, pathlib
    # легкая валидация структуры как в MenuHelper.php:40 + TopNavbar.vue icons
    if not isinstance(payload, list):
        raise HTTPException(status_code=400, detail="menu must be list")
    for si, sec in enumerate(payload):
        if not isinstance(sec, dict):
            raise HTTPException(status_code=400, detail=f"section {si}: must be object")
        if not sec.get("label") or not str(sec["label"]).strip():
            raise HTTPException(status_code=400, detail=f"section {si}: label пуст")
        if "items" not in sec or not isinstance(sec["items"], list):
            raise HTTPException(status_code=400, detail=f"section {si}: items must be list")
        # visibleIn опционально, но если есть — проверяем
        vi = sec.get("visibleIn")
        if vi is not None and not isinstance(vi, list):
            raise HTTPException(status_code=400, detail=f"section {si}: visibleIn must be list")
        for ii, it in enumerate(sec["items"]):
            if not isinstance(it, dict):
                raise HTTPException(status_code=400, detail=f"section {si} item {ii}: must be object")
            if it.get("divider"):
                continue
            if not it.get("label") or not str(it["label"]).strip():
                raise HTTPException(status_code=400, detail=f"section {si} item {ii}: label пуст (или поставьте divider)")
    p = pathlib.Path(__file__).parent / "config" / "menu.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "count": len(payload)}

@app.get("/api/menu")
def get_menu(
    menu_type: str = Query(default="top", alias="type"),
    role: str | None = Query(default=None),
    user: dict | None = Depends(get_optional_user),
):
    """Отдает menu.json с фильтрами visibleIn и roles — замена MenuHelper.php:40.
    Если есть JWT — фильтрует по perms из токена; ?role= оставлен для обратной совместимости."""
    import json, pathlib
    p = pathlib.Path(__file__).parent / "config" / "menu.json"
    if not p.exists():
        return {"detail": f"menu.json not found: {p}", "hint": "scp backend/config/menu.json to backend/config/menu.json"}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"menu.json read error: {e}")
    user_perms: set[str] | None = set(user.get("perms", [])) if user else None
    if user_perms is not None and "admin" in user_perms:
        user_perms = None  # admin видит всё, как Yii can('admin')
    def visible(item):
        vi = item.get("visibleIn")
        if vi and menu_type not in vi:
            return False
        roles = item.get("roles")
        if not roles:
            return True
        if user_perms is not None:
            return bool(user_perms & set(roles))
        if role:
            if role == "admin":
                return True
            return role in roles
        return True  # без auth отдаём всё (старое поведение до логина)
    out = []
    for sec in data:
        if not visible(sec):
            continue
        sec2 = dict(sec)
        items = []
        for it in sec.get("items", []):
            if not visible(it):
                continue
            # divider всегда видим если прошел visibleIn
            items.append(it)
        sec2["items"] = items
        out.append(sec2)
    return out
