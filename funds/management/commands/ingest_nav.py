
from decimal import Decimal, InvalidOperation

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from funds.models import Scheme, NavRecord


class Command(BaseCommand):
    help = "Import mutual fund NAV records from a CSV file"

    def handle(self, *args, **options):
        csv_path = settings.BASE_DIR / "data" / "mutual_fund_nav.csv"

        try:
            df = pd.read_csv(csv_path)
        except FileNotFoundError:
            raise CommandError(f"CSV file not found: {csv_path}")
        except Exception as exc:
            raise CommandError(f"Could not read CSV: {exc}")

        required_columns = {"scheme_name", "nav_date", "nav"}

        if not required_columns.issubset(df.columns):
            raise CommandError(
                "CSV must contain: scheme_name, nav_date, nav"
            )

        df["scheme_name"] = df["scheme_name"].astype("string").str.strip()
        df["nav_date"] = pd.to_datetime(
            df["nav_date"], errors="coerce"
        ).dt.date
        df["nav"] = pd.to_numeric(df["nav"], errors="coerce")

        invalid_rows = (
            df["scheme_name"].isna()
            | df["scheme_name"].eq("")
            | df["nav_date"].isna()
            | df["nav"].isna()
            | (df["nav"] <= 0)
        )

        if invalid_rows.any():
            bad_rows = df.index[invalid_rows].tolist()
            raise CommandError(
                f"Invalid data found at CSV row numbers: "
                f"{[row + 2 for row in bad_rows]}"
            )

        if df.duplicated(
            subset=["scheme_name", "nav_date"]
        ).any():
            raise CommandError(
                "Duplicate scheme_name + nav_date entries found in CSV."
            )

        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for row in df.itertuples(index=False):
                scheme, _ = Scheme.objects.get_or_create(
                    name=row.scheme_name,
                    defaults={
                        "category": "Unknown",
                        "fund_house": "Unknown",
                        "risk_level": "Unknown",
                        "expense_ratio": Decimal("0.00"),
                    },
                )

                try:
                    nav_value = Decimal(str(row.nav))
                except InvalidOperation:
                    raise CommandError(
                        f"Invalid NAV for {row.scheme_name}"
                    )

                _, created = NavRecord.objects.update_or_create(
                    scheme=scheme,
                    nav_date=row.nav_date,
                    defaults={"nav": nav_value},
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete! Created: {created_count}, "
                f"Updated: {updated_count}"
            )
        )
