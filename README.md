# PriceSense

ML-driven predictive shopping platform. Users set a target price on a
product; a Prophet forecasting pipeline predicts and detects the right
moment to auto-execute the order. See `PriceSense_Project_Spec_Django.md`
for the full project spec this build implements.

## Stack

Django 6 + Django REST Framework (chart/AJAX endpoints) + Celery + Redis
(celery-beat for scheduling) + Prophet (forecasting). Runs on **SQLite by
default** with zero external services -- flip `USE_POSTGRES=True` in
`.env` for Postgres, matching the `docker-compose.yml` services. Celery
tasks need Redis running to actually dispatch (the web app and admin work
fine without it).

## Project layout

```
accounts/   Address, Wallet models + signup/onboarding/wallet views
catalog/    Category, Product, PriceLog, Sale, Review models + shop
            views/admin + recommendations.py (co-occurrence "related
            products") + Celery tasks: update_prices,
            retrain_forecast_models + management commands:
            seed_products, backfill_price_history, retrain_models,
            tune_forecast_model
orders/     Order, Trigger, WishlistItem models + cart/checkout/
            trigger/wishlist views + services.py (trigger firing +
            order status progression, shared with the Celery tasks)
            + Celery tasks: check_triggers, confirm_pending_orders,
            progress_orders
ml/         Plain Python module (not a Django app): forecasting.py,
            anomaly.py, suggest.py -- imported directly by Celery tasks
            and views, no service boundary needed.
pricesense/ Django project settings + celery.py (app + beat schedule)
```

## First-time setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env      # defaults work as-is for local SQLite dev

python manage.py migrate
python manage.py createsuperuser

# ~650 products across 5 categories (matches the spec's "5 x 120-150")
python manage.py seed_products --per-category 130

# 6 months of synthetic daily price history per product, using the same
# demand-curve formula as the live update_prices task, so the forecasting
# model has real signal from day one.
python manage.py backfill_price_history --days 180

python manage.py runserver
```

Visit `http://127.0.0.1:8000/` for the shop, `/ml-insights/` for the
forecast-accuracy dashboard, and `/admin/` to manage Sales/Products/
Categories (full CRUD, no custom UI needed) and view Orders/Triggers
read-only.

`seed_products` also accepts `--csv path/to/products.csv` (columns:
`name,category,price[,description]`) to import from a real dataset (e.g.
a Kaggle Flipkart/Amazon export) instead of the built-in Faker-based
generator.

## Running the background pipeline (Celery)

Requires Redis. Easiest path is `docker-compose up -d redis` (add
`postgres` too if `USE_POSTGRES=True`), then in separate terminals:

```powershell
celery -A pricesense worker -l info --pool=solo   # --pool=solo needed on Windows
celery -A pricesense beat -l info
```

Beat schedule (`pricesense/celery.py`):

| Task | Schedule | What it does |
|---|---|---|
| `catalog.tasks.update_prices` | every 15 min | Demand-curve price recompute + active Sale discount, logs to `PriceLog` |
| `orders.tasks.check_triggers` | every 15 min, after prices update | Fires triggers whose target price has been reached, creates a `pending_cancellation` Order |
| `orders.tasks.confirm_pending_orders` | hourly | Flips orders past the 48h cancellation window to `confirmed` |
| `orders.tasks.progress_orders` | hourly | Simulates fulfillment: `confirmed` -> `shipped` (+72h from order creation) -> `delivered` (+120h) |
| `catalog.tasks.retrain_forecast_models` | nightly, 3am | Retrains and re-caches the per-product Prophet model |

Without Celery running, everything above still works -- none of it
actually needs a worker: **price ticks, trigger firing, and order
fulfillment all have synchronous fallbacks.** `catalog.services.
maybe_update_prices` runs `update_prices` in-process (throttled to the
same 15-minute cadence as Celery Beat, so it can't run more often than
the "real" task would) whenever the shop or a product page is loaded;
`orders.services.check_and_fire_triggers` and `progress_order_statuses`
(also what the Celery tasks call) run synchronously against the current
user's data whenever the shop, a product page, My Triggers, or My Orders
is loaded. So prices drift, a trigger fires, or an order ships/delivers
the moment you view a relevant page after its condition is met -- no
worker required for local dev or a demo. `python manage.py
retrain_models` runs the nightly Prophet retrain/cross-validation
synchronously too.

## Shopping features beyond the core trigger flow

- **Reviews & ratings** (`catalog.Review`) -- one review per user per
  product (editable, not duplicated -- `submit_review` updates an
  existing review rather than creating a second one). `Product.
  average_rating`/`review_count` are simple aggregates, shown on the
  product detail page. Deliberately real: an earlier UI pass explicitly
  avoided showing fabricated star ratings when no review data backed
  them -- this closes that gap with an actual model instead of fake
  numbers. **Gated on delivery**: matching real e-commerce practice
  (Amazon, Flipkart), you can only review a product once you have a
  `delivered` Order for it -- enforced server-side in `submit_review`,
  not just hidden in the template, so posting directly to the endpoint
  doesn't bypass it. Reviews from a verified purchase show a "Verified
  Purchase" badge.
- **Wishlist** (`orders.WishlistItem`) -- a heart toggle on both product
  cards and the detail page; `/orders/wishlist/` lists saved products.
  Unique per (user, product) at the database level.
- **Order status progression & tracking** (`orders.services.
  progress_order_statuses` + `order_tracking_stages`) -- every order
  moves `placed -> confirmed -> shipped -> delivered` over time (a
  directly-checked-out order confirms after a short processing delay;
  a trigger-fired order instead waits out the 48h cancellation window
  via `confirm_pending_orders`, then joins the same ship/deliver
  timeline). `/orders/my-orders/<id>/` is a per-order tracking page with
  a visual stepper, not just a status badge in a table. This closes a
  real gap found while building it: originally only trigger-fired
  orders ever progressed past their first status -- a normal checkout
  order sat at "placed" forever since nothing ever touched it.
  **Admin control**: staff (e.g. the superuser from `createsuperuser`)
  can select orders in Django Admin and run "Advance to next status" to
  push fulfillment forward immediately -- bypassing the normal
  timeline, e.g. for a support request or a demo -- via
  `orders.services.advance_order_status`. The Order change form itself
  is entirely read-only (no hand-editing arbitrary fields); this action
  is the only way staff can change a status.

## One shared login (`accounts.views.SiteLoginView`)

There's a single login form (`/login/`) for both customers and staff --
no separate admin login page. Sign in there with any account: a regular
customer lands on the shop, a staff account (`is_staff`, e.g. any Django
Admin user) lands on the Admin dashboard instead. A logged-out visit to
any `/admin/...` page redirects here too (`pricesense/urls.py`
intercepts `/admin/login/` before Django Admin registers its own), so
there's exactly one login page for the whole site rather than two. An
explicit `?next=` (Django Admin's own, or a customer's original
protected destination) still wins over both defaults. This doesn't
grant any extra access beyond what a staff account already had --
Django Admin already trusted the same session either way, it previously
just asked staff to log in a second time on its own separate form.
- **"You might also like"** (`catalog/recommendations.py`) -- a second,
  genuinely different ML technique from the forecasting pipeline:
  co-occurrence-based collaborative filtering, not time-series. For a
  given product, it finds users who ordered/triggered/wishlisted it,
  then counts what else those same users acted on, ranked by frequency.
  Computed live (a cheap set/count operation, not a trained model that
  needs retraining) with a same-category fallback when there's not yet
  enough co-occurrence data -- expected on a fresh install with little
  real user activity.

## Deployment (`Dockerfile`, `docker-compose.yml`, CI)

`docker-compose.yml` runs the full stack -- Postgres, Redis, the Django
app (gunicorn), a Celery worker, and Celery beat -- via `docker compose
up --build`. The `Dockerfile` bakes Prophet's CmdStan backend in at
*build* time (`RUN python -c "import cmdstanpy; cmdstanpy.
install_cmdstan()"`) so the first real request isn't stuck behind a
multi-minute compile. **Not verified in this environment** (no Docker
available here) -- written from documented best practice, so treat the
first `docker compose up --build` as the real test and expect to debug.

`.github/workflows/tests.yml` runs the test suite on every push/PR via
GitHub Actions. It won't execute anywhere until this project is an
actual git repo pushed to GitHub (`git init` first -- see note below).

## Product imagery (`catalog/icons.py`)

Every product renders a hand-mapped line icon (e.g. a "Cricket Bat" always
shows a bat icon) on an animated, category-colored tile, instead of a
photo. This was a deliberate choice: an earlier version fetched photos
from a free tag-based photo API (loremflickr), but a keyword match can't
guarantee the returned photo actually depicts the product, and it
sometimes didn't. `TYPE_TO_ICON` in `catalog/icons.py` maps all 100
product types from `seed_products.py` to one of 65 icons, so correctness
is guaranteed rather than best-effort. A real photo uploaded via Django
Admin (`Product.image`) still takes priority over the icon when present.

## The ML component (`ml/`)

- **`forecasting.py`** -- per-product Prophet model (weekly seasonality,
  no yearly/daily since history is only ~6-12mo), cached to
  `ml/model_cache/*.pkl`.
  - `evaluate_model()` holds out the last N days, retrains, and reports
    RMSE/MAE against two comparisons over the same window: a naive
    "persistence" baseline (tomorrow = last known price), and **Holt-
    Winters exponential smoothing** (`statsmodels`) -- a classical
    statistical model given the same trend + weekly-seasonality
    assumption as Prophet, so it's a fair head-to-head rather than
    Prophet only beating a strawman. On the seeded dataset Prophet wins
    on some products and loses narrowly on others -- an honest result,
    not "our model always wins," which is the point of comparing against
    a real second model rather than just a baseline.
  - `cross_validate_and_cache()` runs Prophet's rolling-origin backtest
    (`prophet.diagnostics.cross_validation` + `performance_metrics`):
    refits at several cutoff points and scores forecasts at multiple
    horizons -- more rigorous than a single train/holdout split. This is
    expensive (several refits per product), so it only runs during the
    nightly retrain (bounded to 8 products) and its result is cached to
    disk, not recomputed per request.
  - `component_plot_base64()` renders Prophet's trend + weekly-seasonality
    decomposition (dark-themed to match the site) as an inline image on
    `/ml-insights/` -- shows *what* the model learned, not just its error.
  - `forecast_product()` powers a forward-looking, shaded confidence band
    on the product detail page's price chart (`/api/products/<id>/forecast/`)
    -- previously this output was only used *internally* to drive the
    anomaly badge and trigger suggestion; now the platform's core "we
    forecast where this is headed" pitch is directly visible to users,
    not just implied.
  - `tune_hyperparameters()` grid-searches Prophet's
    `changepoint_prior_scale` / `seasonality_prior_scale` (its own
    recommended tuning recipe), each combination scored via
    cross-validation, rather than assuming the untouched defaults are
    already optimal. Deliberately **not** part of the regular retrain
    pipeline (dozens of model fits per product) -- run it as a one-off
    analysis: `python manage.py tune_forecast_model <product_id>`. On the
    seeded data the best combo only beat Prophet's defaults by ~1% MAE --
    an honest result showing the defaults were already close to optimal,
    which is itself a legitimate finding, not a failed experiment.
  - `trigger_fire_probability()` and `estimated_days_to_target()` answer
    "how likely, and how soon" for a candidate trigger price, both via
    Monte Carlo simulation over Prophet's own posterior
    (`predictive_samples()` -- hundreds of simulated future price
    trajectories) rather than reading the mean forecast line: e.g. for a
    product at 500 with a 400 trigger, the Set Trigger modal shows both
    "~X% chance within 14 days" and "expected in ~N days (around
    <date>)", live, as the target price is typed. **Both intentionally
    read the same simulated trajectories** -- an earlier version derived
    the ETA from the mean forecast (`yhat`) instead, which could say "not
    expected soon" right next to a 70%+ probability reading, since
    individual noisy trajectories dip below a target the *mean* line
    never reaches. Fixed by putting both metrics on the same statistical
    footing; guarded by a regression test (`test_eta_is_never_none_
    when_probability_is_high`).
- **`anomaly.py`** -- flags when today's price sits outside Prophet's
  forecast confidence interval ("unusually low, good time to buy").
  Shown as a badge on the product detail page.
- **`suggest.py`** -- suggested trigger price = min(10th percentile of
  trailing 6mo price, forecasted 2-week low). Pre-fills the "Set Trigger
  Price" modal.

A product needs at least ~14-21 days of `PriceLog` history before these
kick in (`MIN_HISTORY_FOR_ML` in `catalog/views.py`) -- freshly seeded
products without a backfill won't show ML insights yet. Cross-validation
specifically needs ~90+14 days; run `python manage.py retrain_models`
after backfilling to populate it (also runs nightly via Celery Beat).
`retrain_models` also precomputes and caches `evaluate_model()`'s
comparison and the component-plot image for a bounded sample of
products (`MAX_EVAL` in `catalog/tasks.py`) -- both are too slow (~1-2.5s
each) to compute live for every product `/ml-insights/` shows.

## Tests

```powershell
python manage.py test accounts orders catalog
```

Covers: the demand-curve formula's determinism/bounds, `Product.discount_percent`,
Wallet's Decimal-vs-float handling, trigger firing (fires exactly when
target is reached, not before, not twice), checkout atomicity (a failed
multi-item checkout must roll back completely -- wallet balance and
order count untouched), the 48h order-cancellation window, and the ML
pipeline (forecast/evaluate/anomaly/suggest/cross-validation/component
plot all produce well-formed output on synthetic history). The ML tests
fit real Prophet models, so the suite takes a while to run; the model
cache is redirected to a temp directory during tests so they never touch
`ml/model_cache/`.

## Validation against real data (`validate_on_real_data`)

Every number elsewhere in this README comes from the synthetic
demand-curve catalog -- data generated to have exactly the trend +
weekly-seasonality structure Prophet is built to exploit. To check the
pipeline isn't just well-tuned to its own generator, `python manage.py
validate_on_real_data` runs the **identical** evaluation code
(`ml.forecasting.evaluate_model`, unmodified) against real transaction
data: the UCI "Online Retail II" dataset (a real UK online/wholesale
retailer, 2009-2011). Download it from the UCI Machine Learning
Repository ("Online Retail II") and place `online_retail_II.xlsx` in
`real_data_validation/` (gitignored -- ~45MB, not part of the repo).

**Result on 10 real products** (`real_data_validation/results.json`):
Prophet beat the naive baseline by an average of **8.6%** -- honest,
but nowhere near the 65-77% seen on synthetic data -- and beat
Holt-Winters on only 5/10 products, essentially a coin flip.

**Why, and what it means:** this dataset's `Price` is close to a fixed
wholesale catalog price per SKU -- it barely moves day to day, unlike
the pronounced weekly seasonality + trend deliberately built into the
simulated catalog. When price is nearly constant, the naive baseline
("tomorrow = today") is already a strong forecast, leaving little room
for any model to add value -- and on a few products, Prophet did
slightly *worse* than the baseline. This is the honest boundary
condition for this approach: it adds real value on data with genuine
trend/seasonal structure (which is the premise the whole
target-price-trigger feature is built on), not on data that's closer
to flat-with-noise. That distinction, not a blanket "the model works,"
is the actual finding -- and real-data validation is what surfaced it;
it never would have shown up testing only against the synthetic catalog.

**A real bug this also caught**: the first attempt at this failed on
every single real product with a `KeyError`. `evaluate_model` predicted
over N *consecutive* calendar days (`make_future_dataframe(periods=N)`),
which is always true for the gap-free synthetic backfill but not for
real transaction data (a product can simply have no recorded sale on a
given day) -- so the holdout's actual dates fell outside that
assumption. Fixed by predicting on the holdout's exact dates instead of
an assumed consecutive range; regression-tested with an intentionally
gapped date series (`test_evaluate_model_handles_gapped_real_world_dates`).

## Scope decisions (see spec section 8 for the full framing)

- **Payments are mocked**: `Wallet.balance` just increments; UPI/card are
  simulated successes. Real gateway integration needs merchant KYC/PCI
  compliance, out of scope academically.
- **SQLite by default, Postgres-ready**: keeps the zero-setup dev loop
  fast; flip one env var for a Postgres-backed demo/deploy.
- **Monolithic Django + Celery, no microservices**: `ml/` is plain Python
  imported directly by Celery tasks -- a separate service would add
  deployment complexity without benefit at this scale.
- **Demand-curve-plus-noise pricing** (`catalog/demand.py`), not pure
  randomness, shared between the live task and the historical backfill --
  so the forecasting model has real, learnable signal.
- **Trigger-fired emails use Django's console backend by default**
  (`EMAIL_BACKEND` in `.env`) -- prints to the server/worker log instead
  of needing real SMTP credentials for local dev/demo. Point it at real
  SMTP (`EMAIL_HOST`, `EMAIL_HOST_USER`, etc.) for production.

