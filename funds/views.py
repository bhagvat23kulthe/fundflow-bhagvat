
from decimal import Decimal

from django.shortcuts import get_object_or_404

from rest_framework import generics, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema

from funds.models import Scheme, NavRecord, Portfolio, Transaction
from funds.serializers import (
    SchemeSerializer,
    PortfolioSerializer,
    TransactionSerializer,
)


# ============================================================
# Response serializers for Swagger documentation
# ============================================================

class CurrentUserSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField(allow_blank=True)
    is_authenticated = serializers.BooleanField()


class NavHistoryRecordSerializer(serializers.Serializer):
    nav_date = serializers.DateField()
    nav = serializers.DecimalField(
        max_digits=12,
        decimal_places=4,
    )


class NavHistoryResponseSerializer(serializers.Serializer):
    scheme_id = serializers.IntegerField()
    scheme_name = serializers.CharField()
    nav_history = NavHistoryRecordSerializer(many=True)


class PortfolioAnalyticsHoldingSerializer(serializers.Serializer):
    scheme_id = serializers.IntegerField()
    scheme_name = serializers.CharField()
    units_held = serializers.DecimalField(
        max_digits=18,
        decimal_places=4,
    )
    invested_amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
    )
    latest_nav = serializers.DecimalField(
        max_digits=12,
        decimal_places=4,
        allow_null=True,
    )
    current_value = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
    )
    profit_loss = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
    )


class PortfolioAnalyticsResponseSerializer(serializers.Serializer):
    portfolio_id = serializers.IntegerField()
    portfolio_name = serializers.CharField()
    total_invested = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
    )
    current_value = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
    )
    profit_loss = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
    )
    holdings = PortfolioAnalyticsHoldingSerializer(many=True)


# ============================================================
# GET /api/me/
# Return details of the logged-in user
# ============================================================

@extend_schema(
    responses=CurrentUserSerializer,
    tags=["Authentication"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def current_user(request):
    return Response({
        "username": request.user.username,
        "email": request.user.email,
        "is_authenticated": request.user.is_authenticated,
    })


# ============================================================
# GET /api/schemes/
# Return all mutual fund schemes
# ============================================================

@extend_schema(
    responses=SchemeSerializer(many=True),
    tags=["Schemes"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def scheme_list(request):
    schemes = Scheme.objects.all().order_by("name")
    serializer = SchemeSerializer(schemes, many=True)
    return Response(serializer.data)


# ============================================================
# GET /api/schemes/<scheme_id>/nav/
# Return historical NAV records for a scheme
# ============================================================

@extend_schema(
    responses=NavHistoryResponseSerializer,
    tags=["NAV History"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def nav_history(request, scheme_id):
    scheme = get_object_or_404(Scheme, id=scheme_id)

    records = NavRecord.objects.filter(
        scheme=scheme
    ).order_by("nav_date")

    data = [
        {
            "nav_date": record.nav_date,
            "nav": record.nav,
        }
        for record in records
    ]

    return Response({
        "scheme_id": scheme.id,
        "scheme_name": scheme.name,
        "nav_history": data,
    })


# ============================================================
# GET, POST /api/portfolios/
# List only the logged-in user's portfolios or create one
# ============================================================

class PortfolioListCreateView(generics.ListCreateAPIView):
    serializer_class = PortfolioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Portfolio.objects.filter(
            user=self.request.user
        ).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ============================================================
# GET, POST /api/transactions/
# List or create transactions belonging to the logged-in user
# ============================================================

class TransactionListCreateView(generics.ListCreateAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(
            portfolio__user=self.request.user
        ).select_related(
            "portfolio",
            "scheme",
        ).order_by(
            "-transaction_date",
            "-id",
        )

    def perform_create(self, serializer):
        # TransactionSerializer validates portfolio ownership.
        serializer.save()


# ============================================================
# GET /api/portfolios/<portfolio_id>/analytics/
# Calculate holdings, current value and profit/loss
# ============================================================

@extend_schema(
    responses=PortfolioAnalyticsResponseSerializer,
    tags=["Portfolio Analytics"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def portfolio_analytics(request, portfolio_id):
    # Users can access only their own portfolios.
    portfolio = get_object_or_404(
        Portfolio,
        id=portfolio_id,
        user=request.user,
    )

    transactions = Transaction.objects.filter(
        portfolio=portfolio
    ).select_related(
        "scheme"
    ).order_by(
        "transaction_date",
        "id",
    )

    # Track holdings separately for each scheme.
    scheme_state = {}

    for tx in transactions:
        scheme_id = tx.scheme_id

        if scheme_id not in scheme_state:
            scheme_state[scheme_id] = {
                "scheme": tx.scheme,
                "units": Decimal("0"),
                "cost": Decimal("0"),
            }

        state = scheme_state[scheme_id]
        units = tx.units
        price = tx.nav_at_transaction

        if tx.transaction_type == "BUY":
            state["units"] += units
            state["cost"] += units * price

        elif tx.transaction_type == "SELL":
            current_units = state["units"]

            # Do not allow calculations to create negative holdings.
            # Transaction validation should also reject overselling.
            if units > current_units:
                return Response(
                    {
                        "detail": (
                            "Invalid transaction history: "
                            "SELL units exceed available units."
                        )
                    },
                    status=400,
                )

            if current_units > 0:
                average_cost = state["cost"] / current_units

                state["cost"] -= average_cost * units
                state["units"] -= units

    holdings = []
    total_invested = Decimal("0")
    total_current_value = Decimal("0")

    for state in scheme_state.values():
        scheme = state["scheme"]
        units = state["units"]
        cost = state["cost"]

        # Latest NAV record available in the database.
        latest_record = NavRecord.objects.filter(
            scheme=scheme
        ).order_by(
            "-nav_date"
        ).first()

        latest_nav = (
            latest_record.nav
            if latest_record is not None
            else None
        )

        # Without a NAV record, current value cannot be determined.
        current_value = (
            units * latest_nav
            if latest_nav is not None
            else Decimal("0")
        )

        profit_loss = current_value - cost

        total_invested += cost
        total_current_value += current_value

        holdings.append({
            "scheme_id": scheme.id,
            "scheme_name": scheme.name,
            "units_held": units,
            "invested_amount": cost.quantize(Decimal("0.01")),
            "latest_nav": latest_nav,
            "current_value": current_value.quantize(Decimal("0.01")),
            "profit_loss": profit_loss.quantize(Decimal("0.01")),
        })

    return Response({
        "portfolio_id": portfolio.id,
        "portfolio_name": portfolio.name,
        "total_invested": total_invested.quantize(Decimal("0.01")),
        "current_value": total_current_value.quantize(Decimal("0.01")),
        "profit_loss": (
            total_current_value - total_invested
        ).quantize(Decimal("0.01")),
        "holdings": holdings,
    })


# ============================================================
# POST /api/nav/ingest/
# Trigger NAV ingestion in the background using Celery
# ============================================================

from funds.tasks import ingest_nav_task


@extend_schema(
    responses={
        202: {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "task_id": {"type": "string"},
            },
        }
    },
    tags=["NAV Ingestion"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def trigger_nav_ingestion(request):
    task = ingest_nav_task.delay()

    return Response(
        {
            "message": "NAV ingestion queued successfully",
            "task_id": task.id,
        },
        status=202,
    )
