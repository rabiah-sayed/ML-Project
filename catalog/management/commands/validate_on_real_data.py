import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        'Runs the exact same evaluation pipeline used on /ml-insights/ '
        '(Prophet vs. Holt-Winters vs. naive baseline, via ml.forecasting.'
        'evaluate_model) against real historical price data instead of '
        'the synthetic demand-curve catalog -- so the model comparison '
        'is not just validated against data generated to fit it. Uses '
        'the UCI "Online Retail II" dataset (real UK online retailer '
        'transactions, 2009-2011): see README for how to fetch it.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--file', type=str, default=None,
            help='Path to online_retail_II.xlsx (default: real_data_validation/online_retail_II.xlsx)',
        )
        parser.add_argument('--top-n', type=int, default=10, help='How many products to evaluate')
        parser.add_argument('--min-days', type=int, default=120, help='Minimum distinct days of price history required')

    def handle(self, *args, **options):
        import pandas as pd

        from ml.forecasting import evaluate_model

        xlsx_path = Path(options['file']) if options['file'] else (
            settings.BASE_DIR / 'real_data_validation' / 'online_retail_II.xlsx'
        )
        if not xlsx_path.exists():
            raise CommandError(
                f'{xlsx_path} not found. Download it from the UCI Machine Learning '
                'Repository ("Online Retail II" dataset) and place the .xlsx there.'
            )

        self.stdout.write(f'Loading {xlsx_path} (this is a large file, may take a minute)...')
        sheets = pd.read_excel(xlsx_path, sheet_name=None)
        raw = pd.concat(sheets.values(), ignore_index=True)
        raw.columns = [str(c).strip() for c in raw.columns]

        # Column names differ slightly between mirrors of this dataset.
        price_col = next(c for c in raw.columns if c.lower() in ('price', 'unitprice'))
        qty_col = next(c for c in raw.columns if c.lower() in ('quantity',))
        date_col = next(c for c in raw.columns if c.lower() in ('invoicedate',))
        code_col = next(c for c in raw.columns if c.lower() in ('stockcode',))
        desc_col = next((c for c in raw.columns if c.lower() in ('description',)), None)
        invoice_col = next((c for c in raw.columns if c.lower() in ('invoice', 'invoiceno')), None)

        df = raw[[code_col, desc_col, date_col, qty_col, price_col] + ([invoice_col] if invoice_col else [])].copy()
        df = df.rename(columns={code_col: 'code', date_col: 'date', qty_col: 'qty', price_col: 'price'})
        if desc_col:
            df = df.rename(columns={desc_col: 'description'})
        if invoice_col:
            df = df.rename(columns={invoice_col: 'invoice'})
            df = df[~df['invoice'].astype(str).str.startswith('C')]  # drop cancellations

        df = df[(df['qty'] > 0) & (df['price'] > 0)]
        df['date'] = pd.to_datetime(df['date']).dt.date

        # Quantity-weighted average price per product per day -- a fairer
        # daily price than a plain mean when order sizes vary a lot.
        df['spend'] = df['qty'] * df['price']
        daily = df.groupby(['code', 'date']).agg(spend=('spend', 'sum'), qty=('qty', 'sum')).reset_index()
        daily['y'] = daily['spend'] / daily['qty']
        daily['ds'] = pd.to_datetime(daily['date'])

        coverage = daily.groupby('code')['ds'].nunique().sort_values(ascending=False)
        candidates = coverage[coverage >= options['min_days']]
        if candidates.empty:
            raise CommandError(
                f"No product has {options['min_days']}+ distinct days of price data. Try a lower --min-days."
            )

        names = df.drop_duplicates('code').set_index('code')[['description']] if desc_col else None
        results = []
        self.stdout.write(f'{len(candidates)} products qualify; evaluating top {options["top_n"]} by coverage...\n')

        for code in candidates.index[:options['top_n']]:
            product_df = daily[daily['code'] == code][['ds', 'y']].sort_values('ds').reset_index(drop=True)
            label = names.loc[code, 'description'] if names is not None and code in names.index else code
            try:
                evaluation = evaluate_model(product_id=code, price_df=product_df, holdout_days=14)
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f'  {code} ({label}): skipped -- {exc}'))
                continue

            results.append({'code': str(code), 'label': str(label), **{
                k: v for k, v in evaluation.items() if k in (
                    'rmse', 'mae', 'baseline_rmse', 'baseline_mae', 'improvement_pct',
                    'hw_rmse', 'hw_mae', 'improvement_vs_hw_pct',
                )
            }})
            self.stdout.write(
                f'  {code:>10} ({str(label)[:32]:<32}) days={len(product_df):>4}  '
                f'Prophet MAE={evaluation["mae"]:>8.2f}  Baseline MAE={evaluation["baseline_mae"]:>8.2f}  '
                f'vs baseline={evaluation["improvement_pct"]:>6}%  vs HW={evaluation["improvement_vs_hw_pct"]}%'
            )

        if not results:
            raise CommandError('No product could be evaluated.')

        avg_vs_baseline = sum(r['improvement_pct'] for r in results if r['improvement_pct'] is not None) / len(results)
        beats_hw = sum(1 for r in results if r['improvement_vs_hw_pct'] and r['improvement_vs_hw_pct'] > 0)

        self.stdout.write('\n' + self.style.SUCCESS(
            f'Evaluated {len(results)} real products. '
            f'Avg improvement vs. naive baseline: {avg_vs_baseline:.1f}%. '
            f'Prophet beat Holt-Winters on {beats_hw}/{len(results)}.'
        ))

        out_path = settings.BASE_DIR / 'real_data_validation' / 'results.json'
        with open(out_path, 'w') as f:
            json.dump({'results': results, 'avg_improvement_vs_baseline_pct': round(avg_vs_baseline, 1),
                       'prophet_beats_holt_winters': f'{beats_hw}/{len(results)}'}, f, indent=2)
        self.stdout.write(f'Saved: {out_path}')
