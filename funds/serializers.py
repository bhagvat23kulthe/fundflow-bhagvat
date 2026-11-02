
from decimal import Decimal

from rest_framework import serializers

from funds.models import Portfolio, Scheme, Transaction


class SchemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scheme
        fields = [
            "id",
            "name",
            "category",
            "fund_house",
            "risk_level",
            "expense_ratio",
            "created_at",
        ]


class PortfolioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Portfolio
        fields = [
            "id",
            "name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]


class TransactionSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(
        max_digits=30,
        decimal_places=8,
        read_only=True,
    )

    portfolio = serializers.PrimaryKeyRelatedField(
        queryset=Portfolio.objects.all(),
    )

    units = serializers.DecimalField(
        max_digits=18,
        decimal_places=4,
        min_value=Decimal("0.0001"),
    )

    nav_at_transaction = serializers.DecimalField(
        max_digits=12,
        decimal_places=4,
        min_value=Decimal("0.0001"),
    )

    class Meta:
        model = Transaction
        fields = [
            "id",
            "portfolio",
            "scheme",
            "transaction_type",
            "transaction_date",
            "units",
            "nav_at_transaction",
            "amount",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "amount",
            "created_at",
        ]

    def validate_portfolio(self, portfolio):
        request = self.context.get("request")

        if request is None or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Authentication is required."
            )

        if portfolio.user_id != request.user.id:
            raise serializers.ValidationError(
                "You cannot add transactions to another user's portfolio."
            )

        return portfolio
