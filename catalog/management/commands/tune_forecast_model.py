from django.core.management.base import BaseCommand, CommandError

from catalog.models import Product


class Command(BaseCommand):
    help = (
        'Grid-search Prophet\'s changepoint_prior_scale / '
        'seasonality_prior_scale for one product, each combination '
        'scored via cross-validation, and report the best. This is an '
        'offline tuning analysis (dozens of model fits) -- not part of '
        'the regular retrain pipeline, which uses Prophet\'s defaults '
        'unless you update train_model() with the values this finds.'
    )

    def add_arguments(self, parser):
        parser.add_argument('product_id', type=int)

    def handle(self, *args, **options):
        from ml.forecasting import tune_hyperparameters

        product_id = options['product_id']
        if not Product.objects.filter(pk=product_id).exists():
            raise CommandError(f'No product with id {product_id}')

        self.stdout.write(f'Tuning product {product_id} (this fits several models, may take a minute)...')
        result = tune_hyperparameters(product_id)

        if result is None:
            self.stdout.write(self.style.ERROR(
                'Not enough price history for this product (need 90+ days).'
            ))
            return

        self.stdout.write('\nAll combinations, sorted by MAE:')
        self.stdout.write(f"{'changepoint_prior_scale':>26} {'seasonality_prior_scale':>26} {'RMSE':>10} {'MAE':>10}")
        for r in result['all_results']:
            self.stdout.write(
                f"{r['changepoint_prior_scale']:>26} {r['seasonality_prior_scale']:>26} "
                f"{r['rmse']:>10} {r['mae']:>10}"
            )

        best = result['best']
        self.stdout.write(self.style.SUCCESS(
            f"\nBest: changepoint_prior_scale={best['changepoint_prior_scale']}, "
            f"seasonality_prior_scale={best['seasonality_prior_scale']} "
            f"(RMSE={best['rmse']}, MAE={best['mae']})"
        ))
        if result['improvement_vs_default_pct'] is not None:
            self.stdout.write(
                f"Improvement over Prophet's defaults (0.05, 10.0): "
                f"{result['improvement_vs_default_pct']}%"
            )
