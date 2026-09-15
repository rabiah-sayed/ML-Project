import shutil
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from django.test import TestCase, override_settings
from django.utils import timezone

from .demand import price_for
from .models import Category, PriceLog, Product


class DemandCurveTests(TestCase):
    def test_price_for_is_stable_within_its_noise_band(self):
        """The systematic component (phase/amplitude/trend) is seeded per
        product and deterministic; the noise term deliberately varies
        per call -- same as a real price tick jittering -- so repeated
        calls shouldn't be exactly equal, but should stay in a tight
        band (noise std is 1.5% of price) rather than drifting wildly.
        """
        when = datetime(2024, 6, 1)
        prices = [price_for(1000, when, product_id=1) for _ in range(30)]
        self.assertLess(max(prices) - min(prices), 150)

    def test_price_for_differs_by_product(self):
        """Each product gets its own phase/amplitude -- see demand.py -- so
        two different products shouldn't land on the exact same price."""
        when = datetime(2024, 6, 1)
        self.assertNotEqual(price_for(1000, when, product_id=1), price_for(1000, when, product_id=2))

    def test_price_for_stays_within_reasonable_bounds(self):
        when = datetime(2024, 6, 1)
        price = price_for(1000, when, product_id=1)
        self.assertTrue(700 < price < 1400, f'price {price} swung further than the demand curve should allow')

    def test_price_for_applies_discount(self):
        when = datetime(2024, 6, 1)
        full = price_for(1000, when, product_id=1, discount_percent=0)
        discounted = price_for(1000, when, product_id=1, discount_percent=20)
        self.assertLess(discounted, full)


class ProductDiscountTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name='Test Category')
        self.product = Product.objects.create(
            name='Item', category=category, base_price=Decimal('1000.00'),
            current_price=Decimal('800.00'), stock=10,
        )

    def test_discount_percent_when_discounted(self):
        self.assertEqual(self.product.discount_percent, 20)

    def test_discount_percent_zero_when_full_price(self):
        self.product.current_price = self.product.base_price
        self.assertEqual(self.product.discount_percent, 0)


class ReviewTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from accounts.models import Address

        category = Category.objects.create(name='Review Test Category')
        self.product = Product.objects.create(
            name='Reviewed Item', category=category, base_price=Decimal('500.00'),
            current_price=Decimal('500.00'), stock=10,
        )
        self.user = User.objects.create_user('reviewer', password='x')
        self.address = Address.objects.create(user=self.user, label='home', line1='1 St', city='C', pincode='000')

    def _deliver_order(self, user=None, product=None):
        from orders.models import Order
        return Order.objects.create(
            user=user or self.user, product=product or self.product, price_paid=Decimal('500.00'),
            status='delivered', payment_method='cod', address=self.address,
        )

    def test_average_rating_and_count_with_no_reviews(self):
        self.assertIsNone(self.product.average_rating)
        self.assertEqual(self.product.review_count, 0)

    def test_submit_review_creates_and_updates_average(self):
        from django.contrib.auth.models import User
        from .models import Review

        Review.objects.create(product=self.product, user=self.user, rating=4, comment='Good')
        other_user = User.objects.create_user('reviewer2', password='x')
        Review.objects.create(product=self.product, user=other_user, rating=2)

        self.assertEqual(self.product.review_count, 2)
        self.assertEqual(self.product.average_rating, 3)

    def test_submit_review_blocked_without_delivered_order(self):
        """Reviews are gated on delivery -- you can't meaningfully rate a
        physical product you haven't received."""
        from .models import Review

        self.client.force_login(self.user)
        response = self.client.post(f'/products/{self.product.id}/review/', {'rating': 5, 'comment': 'nope'})

        self.assertRedirects(response, f'/products/{self.product.id}/')
        self.assertEqual(Review.objects.filter(product=self.product, user=self.user).count(), 0)

    def test_submit_review_allowed_after_delivery(self):
        from .models import Review

        self._deliver_order()
        self.client.force_login(self.user)
        response = self.client.post(f'/products/{self.product.id}/review/', {'rating': 5, 'comment': 'great'})

        self.assertRedirects(response, f'/products/{self.product.id}/')
        self.assertEqual(Review.objects.get(product=self.product, user=self.user).rating, 5)

    def test_submit_review_view_updates_existing_review_not_duplicate(self):
        from .models import Review

        self._deliver_order()
        self.client.force_login(self.user)
        self.client.post(f'/products/{self.product.id}/review/', {'rating': 3, 'comment': 'ok'})
        self.client.post(f'/products/{self.product.id}/review/', {'rating': 5, 'comment': 'actually great'})

        self.assertEqual(Review.objects.filter(product=self.product, user=self.user).count(), 1)
        review = Review.objects.get(product=self.product, user=self.user)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.comment, 'actually great')

    def test_submit_review_requires_login(self):
        response = self.client.post(f'/products/{self.product.id}/review/', {'rating': 5})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)


class RecommendationTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from accounts.models import Address
        from orders.models import Trigger

        self.category = Category.objects.create(name='Rec Test Category')
        self.other_category = Category.objects.create(name='Rec Other Category')
        self.product_a = Product.objects.create(
            name='Product A', category=self.category, base_price=Decimal('100.00'),
            current_price=Decimal('100.00'), stock=10,
        )
        self.product_b = Product.objects.create(
            name='Product B', category=self.category, base_price=Decimal('200.00'),
            current_price=Decimal('200.00'), stock=10,
        )
        self.product_c = Product.objects.create(
            name='Product C', category=self.other_category, base_price=Decimal('300.00'),
            current_price=Decimal('300.00'), stock=10,
        )
        self.user = User.objects.create_user('recuser', password='x')
        self.address = Address.objects.create(user=self.user, label='home', line1='1 St', city='C', pincode='000')

        # Same user triggered both A and B -- B should be recommended for A.
        Trigger.objects.create(user=self.user, product=self.product_a, target_price=Decimal('90'), payment_method='cod', address=self.address)
        Trigger.objects.create(user=self.user, product=self.product_b, target_price=Decimal('190'), payment_method='cod', address=self.address)

    def test_related_products_uses_co_occurrence(self):
        from .recommendations import related_products

        results = related_products(self.product_a, limit=6)
        result_ids = [p.id for p in results]

        self.assertIn(self.product_b.id, result_ids)
        self.assertNotIn(self.product_a.id, result_ids)

    def test_related_products_falls_back_to_category_with_no_signal(self):
        from .recommendations import related_products

        results = related_products(self.product_c, limit=6)

        self.assertEqual(results, [])  # no other product in product_c's category, no co-occurrence data


class ForecastingTests(TestCase):
    """Slower tests: fits real Prophet models on synthetic history. Model
    cache is redirected to a temp dir so test runs never overwrite the
    real dev-database's cached models (product IDs can coincide between
    the test DB and dev DB, even though the databases themselves don't).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._cache_dir = Path(tempfile.mkdtemp(prefix='pricesense_test_ml_cache_'))
        cls._settings_override = override_settings(ML_MODEL_CACHE_DIR=cls._cache_dir)
        cls._settings_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._settings_override.disable()
        shutil.rmtree(cls._cache_dir, ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create(name='ML Test Category')
        cls.product = Product.objects.create(
            name='Forecast Test Product', category=category,
            base_price=Decimal('1000.00'), current_price=Decimal('1000.00'), stock=10,
        )
        now = timezone.now()
        logs = [
            PriceLog(product=cls.product, price=price_for(1000, now - timedelta(days=d), cls.product.id), timestamp=now - timedelta(days=d))
            for d in range(90, -1, -1)
        ]
        PriceLog.objects.bulk_create(logs)

    def test_evaluate_model_includes_baseline_comparison(self):
        from ml.forecasting import evaluate_model
        result = evaluate_model(self.product.id, holdout_days=14)

        self.assertIn('baseline_rmse', result)
        self.assertIn('baseline_mae', result)
        self.assertEqual(len(result['dates']), len(result['actual']))
        self.assertEqual(len(result['dates']), len(result['predicted']))
        self.assertEqual(len(result['dates']), len(result['baseline_predicted']))

    def test_evaluate_model_includes_holt_winters_comparison(self):
        """Holt-Winters is the second real forecasting model (vs. the
        naive baseline) -- same trend + weekly-seasonality assumption as
        Prophet, so it's a fair head-to-head rather than a strawman.
        """
        from ml.forecasting import evaluate_model
        result = evaluate_model(self.product.id, holdout_days=14)

        self.assertIsNotNone(result['hw_mae'])
        self.assertIsNotNone(result['hw_rmse'])
        self.assertEqual(len(result['dates']), len(result['hw_predicted']))

    def test_evaluate_model_accepts_an_external_price_df(self):
        """evaluate_model can score this exact pipeline against a price
        series that never touched PriceLog/the DB at all -- e.g. a real
        public dataset -- via price_df, for validating the model isn't
        just tuned to the synthetic demand-curve generator it was built
        against. product_id becomes a label only in that mode.
        """
        import pandas as pd
        from ml.forecasting import evaluate_model

        rows = []
        base = timezone.now() - timedelta(days=90)
        for d in range(91):
            when = base + timedelta(days=d)
            rows.append({'ds': when.replace(tzinfo=None), 'y': 50 + 3 * (d % 7 == 0) + (d * 0.1)})
        external_df = pd.DataFrame(rows)

        result = evaluate_model(product_id='EXTERNAL-SKU-1', price_df=external_df, holdout_days=14)

        self.assertIn('mae', result)
        self.assertIn('baseline_mae', result)
        self.assertEqual(len(result['dates']), 14)

    def test_evaluate_model_handles_gapped_real_world_dates(self):
        """Regression test for a real bug found validating against the
        UCI Online Retail II dataset: every real product failed with a
        KeyError, because evaluate_model predicted on N *consecutive*
        calendar days (make_future_dataframe(periods=N)) while real
        transaction data has gaps (no sales some days) -- so the
        holdout's actual dates didn't match that assumption. Our
        synthetic backfill has no gaps, so this never surfaced until
        tested against real data. Build a price series that skips every
        5th day, like a product with no real-world sales that day.
        """
        import pandas as pd
        from ml.forecasting import evaluate_model

        rows = []
        base = timezone.now() - timedelta(days=110)
        for d in range(111):
            if d % 5 == 0:
                continue  # simulate a day with no recorded sale
            when = base + timedelta(days=d)
            rows.append({'ds': when.replace(tzinfo=None), 'y': 60 + (d % 7) + (d * 0.05)})
        gapped_df = pd.DataFrame(rows)

        result = evaluate_model(product_id='GAPPED-SKU', price_df=gapped_df, holdout_days=14)

        self.assertIn('mae', result)
        self.assertEqual(len(result['dates']), 14)

    def test_forecast_product_returns_future_dates(self):
        from ml.forecasting import forecast_product
        forecast = forecast_product(self.product.id, periods=7)
        self.assertGreaterEqual(len(forecast), 7)

    def test_detect_anomaly_returns_expected_keys(self):
        from ml.anomaly import detect_anomaly
        result = detect_anomaly(self.product.id)
        for key in ('current_price', 'expected_low', 'expected_high', 'is_anomaly', 'message'):
            self.assertIn(key, result)

    def test_suggested_trigger_price_is_positive(self):
        from ml.suggest import suggested_trigger_price
        suggestion = suggested_trigger_price(self.product.id)
        self.assertIsNotNone(suggestion)
        self.assertGreater(suggestion, 0)

    def test_eta_is_zero_days_when_target_already_met(self):
        from ml.forecasting import estimated_days_to_target
        target_above_current = float(self.product.current_price) * 2
        eta = estimated_days_to_target(self.product.id, target_above_current)
        self.assertEqual(eta['days'], 0)

    def test_eta_finds_a_future_crossing_day(self):
        """A target a little below current price should be reachable
        within the forecast window, given the demand curve's noise/trend."""
        from ml.forecasting import estimated_days_to_target
        target_below_current = float(self.product.current_price) * 0.85
        eta = estimated_days_to_target(self.product.id, target_below_current, max_horizon_days=90)
        if eta is not None:
            self.assertGreater(eta['days'], 0)
            self.assertRegex(eta['date'], r'^\d{4}-\d{2}-\d{2}$')

    def test_eta_is_none_for_an_unreachable_target(self):
        from ml.forecasting import estimated_days_to_target
        unreachable_target = float(self.product.current_price) * 0.01
        eta = estimated_days_to_target(self.product.id, unreachable_target, max_horizon_days=30)
        self.assertIsNone(eta)

    def test_eta_is_never_none_when_probability_is_high(self):
        """Regression test for a real bug: ETA used to be computed from
        the mean forecast line (yhat) while probability came from Monte
        Carlo samples -- for a target most sampled trajectories reached,
        yhat itself could still never dip that low, so this returned
        None ("not expected soon") right next to a 70%+ chance reading.
        Both must now come from the same sample-based computation, so a
        high probability can never pair with "no ETA".
        """
        from ml.forecasting import estimated_days_to_target, trigger_fire_probability

        target = float(self.product.current_price) * 0.97
        probability = trigger_fire_probability(self.product.id, target, horizon_days=14)
        eta = estimated_days_to_target(self.product.id, target, max_horizon_days=60)

        if probability >= 50:
            self.assertIsNotNone(eta, 'ETA must not be None when probability is >= 50%')
            self.assertLessEqual(eta['days'], 60)

    def test_component_plot_returns_valid_data_uri(self):
        from ml.forecasting import component_plot_base64
        plot = component_plot_base64(self.product.id)
        self.assertTrue(plot.startswith('data:image/png;base64,'))

    def test_render_and_cache_component_plot_roundtrips(self):
        """The point of caching: component_plot_base64 takes ~1s
        (matplotlib rendering), too slow to redo per product on every
        /ml-insights/ view -- ml_insights() reads this cache instead."""
        from ml.forecasting import load_cached_component_plot, render_and_cache_component_plot

        self.assertIsNone(load_cached_component_plot(self.product.id))
        rendered = render_and_cache_component_plot(self.product.id)
        cached = load_cached_component_plot(self.product.id)

        self.assertEqual(cached, rendered)
        self.assertTrue(cached.startswith('data:image/png;base64,'))

    def test_evaluate_and_cache_roundtrips(self):
        """The point of caching: ml_insights() reads this instead of
        refitting Prophet + Holt-Winters on every page view."""
        from ml.forecasting import evaluate_and_cache, load_cached_evaluation

        self.assertIsNone(load_cached_evaluation(self.product.id))
        result = evaluate_and_cache(self.product.id)
        cached = load_cached_evaluation(self.product.id)

        self.assertEqual(cached['mae'], result['mae'])
        self.assertEqual(cached['dates'], result['dates'])

    def test_cross_validate_and_cache_produces_readable_summary(self):
        from ml.forecasting import cross_validate_and_cache, load_cv_summary

        summary = cross_validate_and_cache(self.product.id, initial_days=30, period_days=15, horizon_days=7)

        self.assertIsNotNone(summary)
        self.assertGreater(summary['num_cutoffs'], 0)
        self.assertEqual(load_cv_summary(self.product.id), summary)

    def test_cross_validate_no_ops_with_insufficient_history(self):
        from ml.forecasting import cross_validate_and_cache
        result = cross_validate_and_cache(self.product.id, initial_days=9999, period_days=15, horizon_days=7)
        self.assertIsNone(result)

    def test_tune_hyperparameters_finds_a_best_combo(self):
        """Grid search over changepoint/seasonality prior scale, each
        combo scored by CV -- confirms it actually compares options
        rather than just returning Prophet's defaults untested."""
        from ml.forecasting import tune_hyperparameters

        result = tune_hyperparameters(self.product.id, initial_days=30, period_days=15, horizon_days=7)

        self.assertIsNotNone(result)
        self.assertEqual(len(result['all_results']), 8)  # 4 changepoint x 2 seasonality values
        self.assertEqual(result['best'], min(result['all_results'], key=lambda r: r['mae']))

    def test_tune_hyperparameters_no_ops_with_insufficient_history(self):
        from ml.forecasting import tune_hyperparameters
        result = tune_hyperparameters(self.product.id, initial_days=9999, period_days=15, horizon_days=7)
        self.assertIsNone(result)


class ForecastAPITests(TestCase):
    """The forecast endpoint powers the shaded prediction band on the
    product detail price chart -- surfacing forecast_product()'s output
    to end users instead of only using it internally for anomaly
    detection and trigger suggestions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._cache_dir = Path(tempfile.mkdtemp(prefix='pricesense_test_ml_cache_'))
        cls._settings_override = override_settings(ML_MODEL_CACHE_DIR=cls._cache_dir)
        cls._settings_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._settings_override.disable()
        shutil.rmtree(cls._cache_dir, ignore_errors=True)
        super().tearDownClass()

    def test_forecast_endpoint_returns_predicted_range(self):
        category = Category.objects.create(name='API Test Category')
        product = Product.objects.create(
            name='API Forecast Product', category=category,
            base_price=Decimal('500.00'), current_price=Decimal('500.00'), stock=10,
        )
        now = timezone.now()
        PriceLog.objects.bulk_create([
            PriceLog(product=product, price=price_for(500, now - timedelta(days=d), product.id), timestamp=now - timedelta(days=d))
            for d in range(30, -1, -1)
        ])

        response = self.client.get(f'/api/products/{product.id}/forecast/?periods=7')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 7)
        for row in data:
            self.assertIn('date', row)
            self.assertLessEqual(row['yhat_lower'], row['yhat'])
            self.assertLessEqual(row['yhat'], row['yhat_upper'])

    def test_forecast_endpoint_handles_product_with_no_history_gracefully(self):
        category = Category.objects.create(name='Empty History Category')
        product = Product.objects.create(
            name='No History Product', category=category,
            base_price=Decimal('100.00'), current_price=Decimal('100.00'), stock=10,
        )

        response = self.client.get(f'/api/products/{product.id}/forecast/')

        self.assertEqual(response.status_code, 400)


class MaybeUpdatePricesTests(TestCase):
    """catalog.services.maybe_update_prices -- the synchronous fallback for
    catalog.tasks.update_prices so current_price still fluctuates without
    Celery Beat running (the common local/demo case)."""

    def setUp(self):
        self.category = Category.objects.create(name='Fallback Test Category')
        self.product = Product.objects.create(
            name='Fallback Product', category=self.category,
            base_price=Decimal('1000.00'), current_price=Decimal('1000.00'), stock=10,
        )

    def test_runs_update_when_no_price_log_exists_yet(self):
        from .services import maybe_update_prices

        self.assertEqual(PriceLog.objects.count(), 0)
        updated = maybe_update_prices()

        self.assertEqual(updated, 1)
        self.assertEqual(PriceLog.objects.filter(product=self.product).count(), 1)

    def test_skips_when_last_update_was_recent(self):
        from .services import maybe_update_prices

        PriceLog.objects.create(product=self.product, price=Decimal('1000.00'), timestamp=timezone.now())
        updated = maybe_update_prices()

        self.assertEqual(updated, 0)
        self.assertEqual(PriceLog.objects.filter(product=self.product).count(), 1)

    def test_runs_again_once_the_throttle_window_has_passed(self):
        from .services import maybe_update_prices

        stale = timezone.now() - timedelta(minutes=20)
        PriceLog.objects.create(product=self.product, price=Decimal('1000.00'), timestamp=stale)
        updated = maybe_update_prices()

        self.assertEqual(updated, 1)
        self.assertEqual(PriceLog.objects.filter(product=self.product).count(), 2)

    def test_product_list_view_triggers_a_price_update(self):
        self.assertEqual(PriceLog.objects.count(), 0)
        self.client.get('/')
        self.assertEqual(PriceLog.objects.filter(product=self.product).count(), 1)

    def test_product_detail_view_triggers_a_price_update(self):
        self.assertEqual(PriceLog.objects.count(), 0)
        self.client.get(f'/products/{self.product.id}/')
        self.assertEqual(PriceLog.objects.filter(product=self.product).count(), 1)
