
from celery import shared_task
from django.core.management import call_command


@shared_task
def add_numbers(a, b):
    """Add two numbers asynchronously using Celery."""
    return a + b


@shared_task
def ingest_nav_task():
    """Run the NAV ingestion management command asynchronously."""
    call_command("ingest_nav")
    return "NAV ingestion completed successfully"
