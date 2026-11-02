
from django.contrib import admin
from django.urls import path
from django.http import JsonResponse

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

from funds.views import (
    current_user,
    scheme_list,
    nav_history,
    PortfolioListCreateView,
    TransactionListCreateView,
    portfolio_analytics,
    trigger_nav_ingestion,
)


# Home API
def home(request):
    return JsonResponse({
        "project": "FundFlow",
        "message": "FundFlow API is running successfully!",
        "docs": "/api/docs/",
        "endpoints": {
            "token": "/api/token/",
            "refresh_token": "/api/token/refresh/",
            "current_user": "/api/me/",
            "schemes": "/api/schemes/",
            "nav": "/api/nav/ingest/",
            "portfolios": "/api/portfolios/",
            "transactions": "/api/transactions/",
            "schema": "/api/schema/",
            "documentation": "/api/docs/",
            "admin": "/admin/",
        },
    })


urlpatterns = [
    # Home
    path("", home, name="home"),

    # Django Admin
    path("admin/", admin.site.urls),

    # JWT Authentication
    path(
        "api/token/",
        TokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),
    path(
        "api/token/refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),

    # Current User
    path(
        "api/me/",
        current_user,
        name="current_user",
    ),

    # Mutual Fund Schemes and NAV
    path(
        "api/schemes/",
        scheme_list,
        name="scheme-list",
    ),
    path(
        "api/schemes/<int:scheme_id>/nav/",
        nav_history,
        name="nav-history",
    ),

    # Background NAV Ingestion using Celery
    path(
        "api/nav/ingest/",
        trigger_nav_ingestion,
        name="trigger-nav-ingestion",
    ),

    # Portfolios
    path(
        "api/portfolios/",
        PortfolioListCreateView.as_view(),
        name="portfolio-list-create",
    ),

    # Transactions
    path(
        "api/transactions/",
        TransactionListCreateView.as_view(),
        name="transaction-list-create",
    ),

    # Portfolio Analytics
    path(
        "api/portfolios/<int:portfolio_id>/analytics/",
        portfolio_analytics,
        name="portfolio-analytics",
    ),

    # OpenAPI Schema
    path(
        "api/schema/",
        SpectacularAPIView.as_view(),
        name="schema",
    ),

    # Swagger Documentation
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]
