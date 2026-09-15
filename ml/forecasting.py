"""Per-product price forecasting on top of PriceLog history.

Plain Python module (not a Django app) called directly from Celery
tasks and views -- no separate service needed since it's all one
Python process anyway.
"""
import base64
import itertools
import json
import pickle
from io import BytesIO

import matplotlib
matplotlib.use('Agg')  # headless: no display available in the web/worker process

import numpy as np
import pandas as pd
from django.conf import settings
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics
from statsmodels.tsa.holtwinters import ExponentialSmoothing


def _model_path(product_id):
    settings.ML_MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return settings.ML_MODEL_CACHE_DIR / f'product_{product_id}.pkl'


def _cv_path(product_id):
    settings.ML_MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return settings.ML_MODEL_CACHE_DIR / f'product_{product_id}_cv.json'


def _eval_path(product_id):
    settings.ML_MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return settings.ML_MODEL_CACHE_DIR / f'product_{product_id}_eval.json'


def _plot_path(product_id):
    settings.ML_MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return settings.ML_MODEL_CACHE_DIR / f'product_{product_id}_plot.txt'


def price_history_df(product_id):
    """PriceLog rows for a product as a Prophet-ready (ds, y) frame,
    collapsed to one row per day (update_prices logs every 15 min).
    """
    from catalog.models import PriceLog

    qs = PriceLog.objects.filter(product_id=product_id).order_by('timestamp').values('timestamp', 'price')
    df = pd.DataFrame(list(qs))
    if df.empty:
        return pd.DataFrame(columns=['ds', 'y'])

    df['ds'] = pd.to_datetime(df['timestamp']).dt.tz_localize(None)
    df['y'] = df['price'].astype(float)
    daily = df.groupby(df['ds'].dt.date)['y'].mean().reset_index()
    daily['ds'] = pd.to_datetime(daily['ds'])
    return daily[['ds', 'y']]


def train_model(df, changepoint_prior_scale=0.05, seasonality_prior_scale=10.0):
    """changepoint_prior_scale/seasonality_prior_scale default to
    Prophet's own defaults (i.e. "we didn't touch them"). See
    tune_hyperparameters() below for picking better values via
    cross-validation rather than guessing.
    """
    model = Prophet(
        weekly_seasonality=True, yearly_seasonality=False, daily_seasonality=False,
        changepoint_prior_scale=changepoint_prior_scale, seasonality_prior_scale=seasonality_prior_scale,
    )
    model.fit(df)
    return model


def train_and_cache_model(product_id):
    """Called by catalog.tasks.retrain_forecast_models (nightly)."""
    df = price_history_df(product_id)
    model = train_model(df)
    with open(_model_path(product_id), 'wb') as f:
        pickle.dump(model, f)
    return model


def load_cached_model(product_id):
    path = _model_path(product_id)
    if path.exists():
        with open(path, 'rb') as f:
            return pickle.load(f)
    return train_and_cache_model(product_id)


def forecast_product(product_id, periods=14):
    """Forecast the next `periods` days of price for a product."""
    model = load_cached_model(product_id)
    future = model.make_future_dataframe(periods=periods)
    forecast = model.predict(future)
    return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]


def trigger_fire_probability(product_id, target_price, horizon_days=14):
    """Probability that price reaches target_price within horizon_days,
    estimated via Monte Carlo from Prophet's own posterior
    (predictive_samples) -- hundreds of simulated future price
    trajectories, each incorporating the model's trend and seasonality
    uncertainty. The fraction of trajectories that dip to or below
    target_price on any day within the window IS the probability
    estimate: a direct read of the fitted model's own uncertainty, not
    a heuristic or a separately trained classifier (which would need
    historical trigger-outcome labels that don't exist).
    """
    model = load_cached_model(product_id)
    future = model.make_future_dataframe(periods=horizon_days)
    samples = model.predictive_samples(future)['yhat']  # shape (n_rows, n_samples)
    horizon_samples = samples[-horizon_days:]

    target = float(target_price)
    hits = (horizon_samples <= target).any(axis=0)
    return round(float(hits.mean()) * 100, 1)


def estimated_days_to_target(product_id, target_price, max_horizon_days=60):
    """The typical (median) day, across the same Monte Carlo simulated
    trajectories used by trigger_fire_probability, that price first
    reaches target_price -- deliberately sample-based rather than
    reading the mean forecast line (yhat), which can understate how
    soon a noisy target is reached: yhat can stay above a target that
    most individual simulated trajectories still dip below, which
    previously made this function claim "not expected soon" for a
    target trigger_fire_probability scored at ~70% within 14 days --
    a direct contradiction from mixing two different statistics.

    Returns a dict {'days': int, 'date': 'YYYY-MM-DD'}, or None if the
    target isn't already met and no simulated trajectory reaches it
    within max_horizon_days.
    """
    from catalog.models import Product

    product = Product.objects.get(pk=product_id)
    target = float(target_price)
    if target >= float(product.current_price):
        return {'days': 0, 'date': pd.Timestamp.now().strftime('%Y-%m-%d')}

    model = load_cached_model(product_id)
    future = model.make_future_dataframe(periods=max_horizon_days)
    samples = model.predictive_samples(future)['yhat']  # shape (n_rows, n_samples)
    horizon_samples = samples[-max_horizon_days:]
    future_dates = future['ds'].tail(max_horizon_days).reset_index(drop=True)

    below_target = horizon_samples <= target  # (max_horizon_days, n_samples)
    ever_crosses = below_target.any(axis=0)
    if not ever_crosses.any():
        return None

    first_cross_idx = np.argmax(below_target, axis=0)  # first True per column
    median_day_idx = int(np.median(first_cross_idx[ever_crosses]))

    return {
        'days': median_day_idx + 1,
        'date': future_dates.iloc[median_day_idx].strftime('%Y-%m-%d'),
    }


_DARK_BG = '#1b1530'
_DARK_TEXT = '#9b91b8'
_DARK_LINE = '#a78bfa'
_DARK_GRID = '#2d2650'


def component_plot_base64(product_id):
    """Prophet's trend + weekly-seasonality decomposition
    (model.plot_components), rendered dark-themed to match the site and
    returned as a base64 PNG data URI for direct <img src="..."> use.
    """
    model = load_cached_model(product_id)
    future = model.make_future_dataframe(periods=14)
    forecast = model.predict(future)

    fig = model.plot_components(forecast, figsize=(7, 4.5))
    fig.patch.set_facecolor(_DARK_BG)
    for ax in fig.axes:
        ax.set_facecolor(_DARK_BG)
        ax.tick_params(colors=_DARK_TEXT)
        ax.xaxis.label.set_color(_DARK_TEXT)
        ax.yaxis.label.set_color(_DARK_TEXT)
        ax.title.set_color(_DARK_TEXT)
        for spine in ax.spines.values():
            spine.set_color(_DARK_GRID)
        for line in ax.get_lines():
            line.set_color(_DARK_LINE)
        for collection in ax.collections:
            collection.set_facecolor(_DARK_LINE)
            collection.set_alpha(0.25)
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format='png', facecolor=_DARK_BG, dpi=110)
    matplotlib.pyplot.close(fig)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode('ascii')
    return f'data:image/png;base64,{encoded}'


def render_and_cache_component_plot(product_id):
    """component_plot_base64 takes ~1s (matplotlib rendering + base64
    encoding), which doesn't scale to computing it live for every
    product on every /ml-insights/ view -- cache it once here instead."""
    data_uri = component_plot_base64(product_id)
    _plot_path(product_id).write_text(data_uri)
    return data_uri


def load_cached_component_plot(product_id):
    path = _plot_path(product_id)
    if not path.exists():
        return None
    return path.read_text()


def cross_validate_and_cache(product_id, initial_days=90, period_days=15, horizon_days=14):
    """Rolling-origin backtest via Prophet's cross_validation: refits the
    model at several cutoff points and scores forecasts at each, which is
    a more rigorous accuracy estimate than a single train/holdout split.
    Expensive (multiple refits), so this runs during the nightly retrain
    task and caches its result -- ml-insights reads the cached summary
    rather than recomputing it per request. Needs at least
    initial_days + horizon_days of history; silently no-ops otherwise.
    """
    full_df = price_history_df(product_id)
    if len(full_df) < initial_days + horizon_days:
        return None

    model = train_model(full_df)
    cv_results = cross_validation(
        model,
        initial=f'{initial_days} days',
        period=f'{period_days} days',
        horizon=f'{horizon_days} days',
        disable_tqdm=True,
    )
    metrics = performance_metrics(cv_results, rolling_window=1)

    summary = {
        'num_cutoffs': int(cv_results['cutoff'].nunique()),
        'by_horizon': [
            {
                'horizon_days': int(row.horizon.days),
                'rmse': round(float(row.rmse), 2),
                'mae': round(float(row.mae), 2),
                'mape_pct': round(float(row.mape) * 100, 1) if 'mape' in metrics.columns else None,
            }
            for row in metrics.itertuples()
        ],
    }
    with open(_cv_path(product_id), 'w') as f:
        json.dump(summary, f)
    return summary


def load_cv_summary(product_id):
    path = _cv_path(product_id)
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def tune_hyperparameters(product_id, initial_days=90, period_days=15, horizon_days=14):
    """Grid search over Prophet's two main regularization hyperparameters
    (changepoint_prior_scale controls trend flexibility, seasonality_
    prior_scale controls how strongly the weekly pattern is fit), each
    combination scored by cross-validation -- Prophet's own recommended
    tuning recipe, rather than assuming its defaults are already optimal
    for this data.

    Deliberately NOT run as part of the regular retrain pipeline: it
    fits len(grid) x len(cv cutoffs) models (dozens of fits), useful as
    an offline analysis for a handful of products, not a per-request or
    even per-night operation for the whole catalog. See the
    `tune_forecast_model` management command.
    """
    full_df = price_history_df(product_id)
    if len(full_df) < initial_days + horizon_days:
        return None

    param_grid = {
        'changepoint_prior_scale': [0.01, 0.05, 0.1, 0.5],
        'seasonality_prior_scale': [1.0, 10.0],
    }
    combos = [
        dict(zip(param_grid.keys(), values))
        for values in itertools.product(*param_grid.values())
    ]

    all_results = []
    for params in combos:
        model = train_model(full_df, **params)
        cv_results = cross_validation(
            model, initial=f'{initial_days} days', period=f'{period_days} days',
            horizon=f'{horizon_days} days', disable_tqdm=True,
        )
        metrics = performance_metrics(cv_results, rolling_window=1)
        all_results.append({
            **params,
            'rmse': round(float(metrics['rmse'].mean()), 2),
            'mae': round(float(metrics['mae'].mean()), 2),
        })

    all_results.sort(key=lambda r: r['mae'])
    default_mae = next(
        (r['mae'] for r in all_results
         if r['changepoint_prior_scale'] == 0.05 and r['seasonality_prior_scale'] == 10.0),
        None,
    )
    best = all_results[0]
    return {
        'all_results': all_results,
        'best': best,
        'improvement_vs_default_pct': (
            round((1 - best['mae'] / default_mae) * 100, 1) if default_mae else None
        ),
    }


def _rmse_mae(actual, predicted):
    errors = actual - predicted
    rmse = float((errors ** 2).mean() ** 0.5)
    mae = float(abs(errors).mean())
    return round(rmse, 2), round(mae, 2)


def _holt_winters_forecast(train_df, holdout_dates):
    """Classical statistical alternative to Prophet: additive trend +
    additive weekly seasonality via Holt-Winters exponential smoothing.
    Deliberately the same trend + weekly-seasonality structure as our
    Prophet config (see train_model), so comparing the two is a fair
    head-to-head rather than a strawman baseline.
    """
    series = train_df.set_index('ds')['y'].asfreq('D')
    series = series.interpolate().bfill()
    model = ExponentialSmoothing(
        series, trend='add', seasonal='add', seasonal_periods=7,
        initialization_method='estimated',
    ).fit(optimized=True)
    forecast = model.forecast(len(holdout_dates))
    forecast.index = holdout_dates
    return forecast


def evaluate_model(product_id=None, holdout_days=14, price_df=None):
    """Train on all-but-the-last `holdout_days`, predict over that
    window, and compare against actuals. Powers the /ml-insights/
    dashboard's predicted-vs-actual chart and RMSE/MAE figures.

    Scores two things alongside Prophet for comparison: a naive
    "persistence" baseline (tomorrow = last known price), and Holt-
    Winters exponential smoothing -- a classical statistical model with
    the same trend + weekly-seasonality assumption as Prophet, so their
    accuracy numbers are directly comparable rather than Prophet sitting
    in isolation against only a strawman.

    Pass `price_df` (a (ds, y) DataFrame, same shape as
    price_history_df's output) to evaluate this exact pipeline against
    data that didn't come from PriceLog at all -- e.g. a real public
    dataset -- without needing a Product row. `product_id` is then only
    used to label results, not to query the DB.
    """
    full_df = price_df if price_df is not None else price_history_df(product_id)
    if len(full_df) < 21:
        raise ValueError(f'Not enough price history for product {product_id} to evaluate')

    holdout_days = min(holdout_days, max(1, len(full_df) // 4))
    train_df = full_df.iloc[:-holdout_days]
    holdout_df = full_df.iloc[-holdout_days:]

    model = train_model(train_df)
    # Predict on the holdout's *actual* dates rather than
    # make_future_dataframe(periods=holdout_days), which assumes N
    # consecutive calendar days from the training cutoff -- true for
    # our gap-free synthetic backfill, but not for real transaction
    # data (e.g. a product with no sales on some days), where the
    # holdout's real dates can fall outside that consecutive window
    # entirely and this used to raise a KeyError.
    forecast = model.predict(pd.DataFrame({'ds': holdout_df['ds'].values})).set_index('ds')
    predicted = forecast.loc[holdout_df['ds'], 'yhat']

    actual = holdout_df.set_index('ds')['y']
    rmse, mae = _rmse_mae(actual.values, predicted.values)

    naive_value = train_df['y'].iloc[-1]
    naive_predicted = pd.Series(naive_value, index=actual.index)
    baseline_rmse, baseline_mae = _rmse_mae(actual.values, naive_predicted.values)

    try:
        hw_predicted = _holt_winters_forecast(train_df, holdout_df['ds'])
        hw_rmse, hw_mae = _rmse_mae(actual.values, hw_predicted.values)
        hw_predicted_list = [round(v, 2) for v in hw_predicted.tolist()]
    except Exception:
        hw_rmse = hw_mae = hw_predicted_list = None

    return {
        'rmse': rmse,
        'mae': mae,
        'baseline_rmse': baseline_rmse,
        'baseline_mae': baseline_mae,
        'improvement_pct': round((1 - mae / baseline_mae) * 100, 1) if baseline_mae else None,
        'hw_rmse': hw_rmse,
        'hw_mae': hw_mae,
        'hw_predicted': hw_predicted_list,
        'improvement_vs_hw_pct': round((1 - mae / hw_mae) * 100, 1) if hw_mae else None,
        'dates': [d.strftime('%Y-%m-%d') for d in holdout_df['ds']],
        'actual': [round(v, 2) for v in actual.tolist()],
        'predicted': [round(v, 2) for v in predicted.tolist()],
        'baseline_predicted': [round(v, 2) for v in naive_predicted.tolist()],
    }


def evaluate_and_cache(product_id, holdout_days=14):
    """Runs evaluate_model and caches its result to disk. evaluate_model
    fits two real models (Prophet + Holt-Winters) from scratch, so
    computing it live on every /ml-insights/ page view doesn't scale
    past a handful of products -- this lets the nightly retrain do that
    work once, and the view just reads the cached result.
    """
    result = evaluate_model(product_id, holdout_days=holdout_days)
    with open(_eval_path(product_id), 'w') as f:
        json.dump(result, f)
    return result


def load_cached_evaluation(product_id):
    path = _eval_path(product_id)
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)
