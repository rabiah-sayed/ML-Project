from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from catalog.demand import price_for
from catalog.models import PriceLog, Product

BATCH_SIZE = 2000


class Command(BaseCommand):
    help = (
        'Generate synthetic PriceLog history for every product using the '
        'same demand-curve formula as the live update_prices task, so the '
        'forecasting model has real signal to learn from day one.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=180, help='Days of daily history to backfill per product')
        parser.add_argument('--clear', action='store_true', help='Delete existing PriceLog rows first')

    def handle(self, *args, **options):
        days = options['days']
        now = timezone.now()

        if options['clear']:
            deleted, _ = PriceLog.objects.all().delete()
            self.stdout.write(f'Cleared {deleted} existing price logs.')

        products = list(Product.objects.all())
        total_created = 0
        batch = []

        for product in products:
            sale = product.active_sale()
            discount = sale.discount_percent if sale else 0
            last_price = product.base_price

            for day_offset in range(days, -1, -1):
                when = now - timezone.timedelta(days=day_offset)
                last_price = price_for(product.base_price, when, product.id, discount)
                batch.append(PriceLog(product=product, price=last_price, timestamp=when))

                if len(batch) >= BATCH_SIZE:
                    with transaction.atomic():
                        PriceLog.objects.bulk_create(batch)
                    total_created += len(batch)
                    batch = []

            product.current_price = last_price

        if batch:
            with transaction.atomic():
                PriceLog.objects.bulk_create(batch)
            total_created += len(batch)

        Product.objects.bulk_update(products, ['current_price'], batch_size=BATCH_SIZE)

        self.stdout.write(self.style.SUCCESS(
            f'Backfilled {total_created} price log entries across {len(products)} products.'
        ))
