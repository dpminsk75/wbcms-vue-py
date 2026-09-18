from .auth import router as auth_router
from .companies import router as companies_router
from .dashboard import router as dashboard_router
from .admin import router as admin_router
from .tags import router as tags_router
from .wb_search import router as wb_search_router
from .cost import router as cost_router
from .wb_orders import router as wb_orders_router
from .wb_sales import router as wb_sales_router
from .feedback import router as feedback_router
from .reply_rules import router as reply_rules_router
from .wb_tokens import router as wb_tokens_router, expiring_router as wb_tokens_expiring_router
from .competitor import router as competitor_router
from .ai_jobs import router as ai_jobs_router
from .seo import router as seo_router
