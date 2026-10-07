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
        related_name="nav_records"
    )
    nav_date = models.DateField()
    nav = models.DecimalField(max_digits=12, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["scheme", "nav_date"],
                name="unique_scheme_nav_date"
            )
        ]
        ordering = ["-nav_date"]

    def __str__(self):
        return f"{self.scheme.name} - {self.nav_date} - {self.nav}"