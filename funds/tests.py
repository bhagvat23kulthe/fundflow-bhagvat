from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from funds.models import Scheme, NavRecord, Portfolio, Transaction


User = get_user_model()


class NavRecordModelTests(TestCase):
    def setUp(self):
        self.scheme = Scheme.objects.create(
            name="Test Fund",
            category="Equity",
            fund_house="Test House",
            risk_level="Moderate",
            expense_ratio="0.50",
        )

    def test_scheme_is_saved(self):
        self.assertEqual(Scheme.objects.count(), 1)
        self.assertEqual(self.scheme.name, "Test Fund")

    def test_nav_record_is_saved(self):
        record = NavRecord.objects.create(
            scheme=self.scheme,
            nav_date="2026-10-08",
            nav="125.4500",
        )

        self.assertEqual(NavRecord.objects.count(), 1)
        self.assertEqual(
            Decimal(str(record.nav)),
            Decimal("125.4500"),
        )


class SchemeListAPITests(APITestCase):
    def setUp(self):
        Scheme.objects.create(
            name="Alpha Equity Fund",
            category="Equity",
            fund_house="Alpha AMC",
            risk_level="High",
            expense_ratio="0.50",
        )

    def test_scheme_list_returns_200(self):
        response = self.client.get("/api/schemes/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["name"],
            "Alpha Equity Fund",
        )


class NavHistoryAPITests(APITestCase):
    def setUp(self):
        self.scheme = Scheme.objects.create(
            name="FundFlow Test Fund",
            category="Equity",
            fund_house="Test AMC",
            risk_level="Moderate",
            expense_ratio="0.50",
        )

        NavRecord.objects.create(
            scheme=self.scheme,
            nav_date="2026-10-08",
            nav="125.4500",
        )
        NavRecord.objects.create(
            scheme=self.scheme,
            nav_date="2026-10-09",
            nav="126.1200",
        )
        NavRecord.objects.create(
            scheme=self.scheme,
            nav_date="2026-10-10",
            nav="125.9800",
        )

    def test_nav_history_returns_200(self):
        response = self.client.get(
            f"/api/schemes/{self.scheme.id}/nav/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_nav_history_returns_correct_scheme_and_records(self):
        response = self.client.get(
            f"/api/schemes/{self.scheme.id}/nav/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["scheme_id"], self.scheme.id)
        self.assertEqual(
            response.data["scheme_name"],
            "FundFlow Test Fund",
        )
        self.assertEqual(len(response.data["nav_history"]), 3)

    def test_nav_history_is_ordered_by_date(self):
        response = self.client.get(
            f"/api/schemes/{self.scheme.id}/nav/"
        )

        dates = [
            str(record["nav_date"])
            for record in response.data["nav_history"]
        ]

        self.assertEqual(
            dates,
            ["2026-10-08", "2026-10-09", "2026-10-10"],
        )

    def test_nav_history_returns_404_for_unknown_scheme(self):
        response = self.client.get("/api/schemes/999999/nav/")

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )


class PortfolioAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="bhagvat_test",
            password="TestPass123!",
        )
        self.other_user = User.objects.create_user(
            username="other_test",
            password="OtherPass123!",
        )

        self.client.force_authenticate(user=self.user)
        self.url = "/api/portfolios/"

    def test_portfolio_api_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_authenticated_user_can_create_portfolio(self):
        response = self.client.post(
            self.url,
            {"name": "My Mutual Fund Portfolio"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            response.data["name"],
            "My Mutual Fund Portfolio",
        )
        self.assertEqual(Portfolio.objects.count(), 1)

        portfolio = Portfolio.objects.get()
        self.assertEqual(portfolio.user, self.user)

    def test_user_can_only_see_own_portfolios(self):
        Portfolio.objects.create(
            user=self.user,
            name="My Portfolio",
        )
        Portfolio.objects.create(
            user=self.other_user,
            name="Other User Portfolio",
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "My Portfolio")

    def test_portfolio_owner_is_authenticated_user(self):
        response = self.client.post(
            self.url,
            {
                "name": "Secure Portfolio",
                "user": self.other_user.id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        portfolio = Portfolio.objects.get(name="Secure Portfolio")
        self.assertEqual(portfolio.user, self.user)
        self.assertNotEqual(portfolio.user, self.other_user)


class TransactionAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="transaction_user",
            password="TestPass123!",
        )
        self.other_user = User.objects.create_user(
            username="transaction_other",
            password="OtherPass123!",
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="My Portfolio",
        )
        self.other_portfolio = Portfolio.objects.create(
            user=self.other_user,
            name="Other Portfolio",
        )

        self.scheme = Scheme.objects.create(
            name="Transaction Test Fund",
            category="Equity",
            fund_house="Test AMC",
            risk_level="Moderate",
            expense_ratio="0.50",
        )

        self.url = "/api/transactions/"
        self.client.force_authenticate(user=self.user)

    def valid_payload(self, **overrides):
        payload = {
            "portfolio": self.portfolio.id,
            "scheme": self.scheme.id,
            "transaction_type": "BUY",
            "transaction_date": "2026-10-12",
            "units": "10.0000",
            "nav_at_transaction": "125.4500",
        }
        payload.update(overrides)
        return payload

    def test_transactions_require_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_user_can_create_buy_transaction(self):
        response = self.client.post(
            self.url,
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(response.data["transaction_type"], "BUY")
        self.assertEqual(
            Decimal(response.data["amount"]),
            Decimal("1254.50000000"),
        )

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.portfolio.user, self.user)

    def test_user_can_create_sell_transaction(self):
        response = self.client.post(
            self.url,
            self.valid_payload(transaction_type="SELL"),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(response.data["transaction_type"], "SELL")

    def test_zero_units_are_rejected(self):
        response = self.client.post(
            self.url,
            self.valid_payload(units="0"),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(Transaction.objects.count(), 0)

    def test_negative_units_are_rejected(self):
        response = self.client.post(
            self.url,
            self.valid_payload(units="-2"),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_zero_nav_is_rejected(self):
        response = self.client.post(
            self.url,
            self.valid_payload(nav_at_transaction="0"),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(Transaction.objects.count(), 0)

    def test_invalid_transaction_type_is_rejected(self):
        response = self.client.post(
            self.url,
            self.valid_payload(transaction_type="HOLD"),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_cannot_create_transaction_in_another_users_portfolio(self):
        response = self.client.post(
            self.url,
            self.valid_payload(portfolio=self.other_portfolio.id),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(Transaction.objects.count(), 0)

    def test_user_only_sees_own_transactions(self):
        Transaction.objects.create(
            portfolio=self.portfolio,
            scheme=self.scheme,
            transaction_type="BUY",
            transaction_date="2026-10-12",
            units="10.0000",
            nav_at_transaction="125.4500",
        )
        Transaction.objects.create(
            portfolio=self.other_portfolio,
            scheme=self.scheme,
            transaction_type="BUY",
            transaction_date="2026-10-12",
            units="5.0000",
            nav_at_transaction="100.0000",
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["portfolio"],
            self.portfolio.id,
        )


class PortfolioAnalyticsAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="analytics_user",
            password="TestPass123!",
        )
        self.other_user = User.objects.create_user(
            username="analytics_other",
            password="OtherPass123!",
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="Analytics Test Portfolio",
        )

        self.other_portfolio = Portfolio.objects.create(
            user=self.other_user,
            name="Other Portfolio",
        )

        self.scheme = Scheme.objects.create(
            name="Analytics Test Fund",
            category="Equity",
            fund_house="Test AMC",
            risk_level="Moderate",
            expense_ratio="0.50",
        )

        NavRecord.objects.create(
            scheme=self.scheme,
            nav_date="2026-10-10",
            nav="110.0000",
        )

        Transaction.objects.create(
            portfolio=self.portfolio,
            scheme=self.scheme,
            transaction_type="BUY",
            transaction_date="2026-10-09",
            units="10.0000",
            nav_at_transaction="100.0000",
        )

        self.url = (
            f"/api/portfolios/{self.portfolio.id}/analytics/"
        )
        self.client.force_authenticate(user=self.user)

    def test_analytics_returns_correct_calculations(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["portfolio_id"], self.portfolio.id)

        self.assertEqual(
            Decimal(str(response.data["total_invested"])),
            Decimal("1000.00"),
        )
        self.assertEqual(
            Decimal(str(response.data["current_value"])),
            Decimal("1100.00"),
        )
        self.assertEqual(
            Decimal(str(response.data["profit_loss"])),
            Decimal("100.00"),
        )

    def test_analytics_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_user_cannot_access_another_users_analytics(self):
        response = self.client.get(
            f"/api/portfolios/{self.other_portfolio.id}/analytics/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_analytics_returns_404_for_unknown_portfolio(self):
        response = self.client.get(
            "/api/portfolios/999999/analytics/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )
