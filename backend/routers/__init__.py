from .auth import router as auth_router
from .companies import router as companies_router
from .dashboard import router as dashboard_router
from .admin import router as admin_router
from .tags import router as tags_router
from .wb_search import router as wb_search_router
from .cost import router as cost_router
from .wb_orders import router as wb_orders_router
from .fbs import router as fbs_router
from .fbs_orders import router as fbs_orders_router
from .fbs_cancels import router as fbs_cancels_router
from .fbs_commission import router as fbs_commission_router
from .fbs_pvz import router as fbs_pvz_router
from .wb_sales import router as wb_sales_router
from .feedback import router as feedback_router
from .reply_rules import router as reply_rules_router
from .wb_tokens import router as wb_tokens_router, expiring_router as wb_tokens_expiring_router
from .competitor import router as competitor_router
from .ai_jobs import router as ai_jobs_router
from .seo import router as seo_router
from .seo_models import router as seo_models_router
from .cms import router as cms_router
from .ext import router as ext_router, admin_router as ext_tokens_admin_router, diag_admin_router as ext_diag_admin_router, dl_router as ext_download_router, cat_router as ext_filters_router
