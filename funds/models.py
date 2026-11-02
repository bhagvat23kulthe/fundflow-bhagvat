from django.conf import settings
from django.db import models


class Scheme(models.Model):
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100)
    fund_house = models.CharField(max_length=100)
    risk_level = models.CharField(max_length=50)
    expense_ratio = models.DecimalField(max_digits=5, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class NavRecord(models.Model):
    scheme = models.ForeignKey(
        Scheme,
        on_delete=models.CASCADE,
        related_name="nav_records",
    )
    nav_date = models.DateField()
    nav = models.DecimalField(max_digits=12, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["scheme", "nav_date"],
                name="unique_scheme_nav_date",
            )
        ]
        ordering = ["-nav_date"]

    def __str__(self):
        return f"{self.scheme.name} - {self.nav_date} - {self.nav}"


class Portfolio(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portfolios",
    )
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.user}"


class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        BUY = "BUY", "Buy"
        SELL = "SELL", "Sell"

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    scheme = models.ForeignKey(
        Scheme,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    transaction_type = models.CharField(
        max_length=4,
        choices=TransactionType.choices,
    )
    transaction_date = models.DateField()
    units = models.DecimalField(max_digits=18, decimal_places=4)
    nav_at_transaction = models.DecimalField(
        max_digits=12,
        decimal_places=4,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-transaction_date", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(units__gt=0),
                name="transaction_units_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(nav_at_transaction__gt=0),
                name="transaction_nav_positive",
            ),
        ]

    @property
    def amount(self):
        return self.units * self.nav_at_transaction

    def __str__(self):
        return (
            f"{self.transaction_type} - "
            f"{self.scheme.name} - "
            f"{self.transaction_date}"
        )