# PriceSense — ML-Driven Predictive Shopping Platform (Django Edition)

*Semester project spec + build prompt — full Python stack, team of 2–3, 6–8 week timeline*

---

## 1. Concept in one line

An e-commerce platform where users set a **target price**, and a machine learning pipeline **forecasts and detects** the right moment to auto-execute the order. The ML component is the graded deliverable; the e-commerce shell exists to demonstrate it.

---

## 2. Architecture (single Python codebase)

```
┌─────────────────────────────────────────────────────────┐
│                     Django Project                       │
│                                                            │
│  ┌──────────────┐   ┌───────────────┐   ┌──────────────┐ │
│  │  Django Views │   │  Django Admin  │   │  DRF (optional│ │
│  │  + Templates  │   │  (Sales, Prod- │   │  API for      │ │
│  │  (users, cart,│   │  ucts, Users — │   │  price charts │ │
│  │  orders, etc.)│   │  free CRUD!)   │   │  / AJAX)      │ │
│  └──────┬───────┘   └───────┬───────┘   └──────┬───────┘ │
│         │                    │                    │        │
│         └────────────────────┼────────────────────┘        │
│                               ▼                             │
│                      Django ORM / PostgreSQL                │
│                (users, products, orders, price_logs,         │
│                 triggers, addresses, sales)                  │
│                               ▲                              │
│  ┌────────────────────────────┴───────────────────────────┐│
│  │  Celery + Redis (task queue + scheduler / celery-beat)  ││
│  │  - update_prices  (every 15 min)                        ││
│  │  - check_triggers (every 15 min, after price update)    ││
│  │  - confirm_pending_orders (every hour, checks 48h window)││
│  │  - retrain_forecast_models (nightly)                     ││
│  └───────────────────────────┬──────────────────────────────┘│
│                               ▼                              │
│              ml/ (plain Python module inside the project)     │
│              - forecasting.py  (Prophet or statsmodels)       │
│              - anomaly.py      (dip detection)                │
│              - suggest.py      (trigger price suggestion)     │
└─────────────────────────────────────────────────────────┘
```

**Why this is simpler than a microservice split:** since it's "full Python anyway," the ML code doesn't need to be a separate service behind a REST API — it's just a Python module Celery tasks import directly. One less moving part, one less deployment target, easier to demo and explain. If a professor asks "why not microservices," the honest answer is: unnecessary complexity for this scale, and Django + Celery already gives clean separation between web logic and background/ML jobs.

---

## 3. Team split (2–3 people)

- **Person A — Core Django app:** models, auth, cart, orders, addresses, wallet, checkout flow
- **Person B — Celery + ML module:** price simulation task, forecasting model, anomaly detection, trigger-check task, model retraining
- **Person C (if 3rd member) — Templates/frontend:** product pages, price history charts (Chart.js via CDN), trigger-setting UI, admin dashboard polish
- If only 2 people: B also owns the ML insights template, since by week 5 the hard ML logic is done and it's mostly rendering charts from an existing API.

---

## 4. Feature scope

| Feature | Approach in Django |
|---|---|
| Multi-user accounts | Django's built-in `auth` app — don't rebuild this |
| Categories, 1000+ products/category | Scaled to 5 categories × 120–150 products, seeded via a **management command** (`manage.py seed_products`) using Faker + a public dataset (Kaggle Flipkart/Amazon CSV) |
| Sale events (Diwali, Independence Day, ad-hoc) | `Sale` model with `discount_percent, start_date, end_date, category`. **Manage entirely through Django Admin** — no custom admin UI needed, this is Django's biggest win here |
| Admin starts sale mid-month | Same — Django Admin, no extra engineering |
| Multiple addresses | `Address` model, FK to `User`, `label` field (home/work) |
| Payments: UPI/card/wallet | **Mocked.** `Wallet` model with `balance` field; "add money" just increments it. UPI/card forms simulate success after a delay. State this as a deliberate scope decision in your report. |
| Price changes every 15 min | Celery Beat task `update_prices`: for each product, `new_price = base_price * demand_curve(time) * noise * active_sale_discount`. Demand curve = weekly seasonality (sine wave) + trend, not pure randomness, so the model has real signal. |
| Price history, 6–12 months, lowest/current | `PriceLog(product, price, timestamp)` — backfilled synthetically at seed time using the same demand-curve formula run backward |
| Add to cart / buy now | Standard Django views/forms |
| **Trigger orders** (target price + payment method + address, set at trigger-creation time) | `Trigger` model: `user, product, target_price, payment_method, address, status (active/fired/cancelled/expired)` |
| Auto-order on trigger fire, COD included | Celery task `check_triggers`, runs right after `update_prices`: any active trigger whose target ≥ new price creates an `Order` with status `pending_cancellation` |
| 2-day cancellation window | Celery Beat task `confirm_pending_orders`, hourly: flips `pending_cancellation` → `confirmed` after 48h; user can cancel via a view in that window |

---

## 5. The ML component (this is what makes it an ML project)

Build these as plain Python functions in `ml/`, called from Celery tasks — no separate service needed:

1. **`forecasting.py`** — per product, forecast next 7–30 days of price. Use **Prophet** (`pip install prophet`) — handles weekly seasonality out of the box and is easy to explain in a viva. An LSTM is an option if your team wants a deep-learning angle, but costs more tuning time for a 6–8 week window.
2. **`anomaly.py`** — flag when today's actual price falls outside Prophet's forecast confidence interval → "unusually low, good time to buy" signal.
3. **`suggest.py`** — derive a suggested trigger price from the forecast (e.g. 10th percentile of trailing 6 months, or the forecasted 2-week low). This can literally be one function reusing forecasting.py's output — it doesn't need its own model.
4. **Model evaluation view** (`/ml-insights/`) — a Django template showing predicted vs. actual price for a sample of products (matplotlib/Chart.js) with **RMSE/MAE displayed**. This single page carries more grading weight than any e-commerce feature — don't skip it.

Retrain nightly via Celery Beat, not in real time — keeps things simple and is standard practice for this kind of forecasting.

---

## 6. Timeline (6–8 weeks)

| Week | Milestone |
|---|---|
| 1 | Django project setup, models, migrations, Django Admin config, auth |
| 2 | Product catalog + seed command, cart, addresses, wallet (mocked) |
| 3 | Celery + Redis setup, `update_prices` task, PriceLog storage + backfill |
| 4 | Trigger model + `check_triggers` task + `confirm_pending_orders` (48h window) |
| 5 | ML module: Prophet forecasting wired to real PriceLog data |
| 6 | Anomaly detection, suggested trigger price, `/ml-insights/` dashboard |
| 7 | Frontend polish (price history charts), Django Admin theming for sales/products |
| 8 | Integration testing, report writing, demo prep, buffer |

---

## 7. Final build prompt (paste into Claude Code)

```
Build a Django project called "PriceSense" — a full-Python ML-driven
e-commerce platform. Use Django + Django REST Framework (for AJAX/chart
endpoints only) + PostgreSQL + Celery + Redis (celery-beat for scheduling).

APPS:
- accounts  → custom User extensions (or use Django auth as-is), Address,
  Wallet
- catalog   → Category, Product, PriceLog, Sale
- orders    → Order, Trigger
- ml        → plain Python module: forecasting.py, anomaly.py, suggest.py
  (no Django models needed here, just functions operating on PriceLog data)

MODELS:
- Address: user (FK), label (home/work), line1, city, pincode
- Wallet: user (OneToOne), balance
- Category: name
- Product: name, category (FK), base_price, current_price, description,
  image, stock
- PriceLog: product (FK), price, timestamp
- Sale: name, category (FK, nullable = all categories), discount_percent,
  start_date, end_date
- Order: user (FK), product (FK), price_paid, status (placed/
  pending_cancellation/confirmed/shipped/delivered/cancelled),
  payment_method (upi/card/wallet/cod), address (FK), created_at
- Trigger: user (FK), product (FK), target_price, payment_method, address
  (FK), status (active/fired/cancelled/expired), created_at

DJANGO ADMIN:
- Register Sale, Product, Category with full CRUD in Django Admin —
  this IS the admin panel for managing sales/discounts, no custom UI needed
- Register Order/Trigger as read-only list views for admin oversight

MANAGEMENT COMMANDS:
- seed_products: load ~120-150 products x 5 categories from a public
  e-commerce CSV dataset (e.g. Kaggle Flipkart/Amazon products), using
  Faker for any missing fields
- backfill_price_history: for each product, generate 6 months of synthetic
  PriceLog entries using a demand-curve formula (weekly seasonality sine
  wave + trend + gaussian noise), so ML models have real signal to learn

CELERY TASKS (celery-beat schedule):
- update_prices (every 15 min): recompute each product's current_price
  using the demand-curve formula, apply active Sale discount if in date
  range, write to PriceLog
- check_triggers (every 15 min, right after update_prices): for each
  active Trigger, if current_price <= target_price, create an Order with
  status "pending_cancellation" using the trigger's stored payment_method
  and address, then mark trigger as "fired"
- confirm_pending_orders (hourly): flip any Order in
  "pending_cancellation" older than 48h to "confirmed"
- retrain_forecast_models (nightly): retrain Prophet models per product
  on accumulated PriceLog data, cache serialized models (pickle or joblib)

VIEWS/TEMPLATES:
- Standard auth (Django's built-in login/register, extended with a
  post-signup Wallet + Address setup step)
- Product listing by category, product detail page with:
  - price history chart (Chart.js via CDN, 6mo/1yr toggle), lowest/current
    price
  - "Buy Now" button and "Set Trigger Price" modal (target price, payment
    method dropdown incl. COD, address dropdown)
- Cart, checkout (deducts from Wallet if wallet selected, otherwise
  simulate UPI/card success after a fake delay)
- "My Orders" and "My Triggers" pages; cancel button visible only within
  the 48h pending_cancellation window
- /ml-insights/ dashboard: forecast chart (predicted vs actual) and
  RMSE/MAE for a sample of products, pulling from ml/forecasting.py

Build incrementally: models + migrations + auth first, then catalog +
seed data, then Celery price/trigger engine, then the ML module, then
polish. Give me a working, runnable increment at each stage rather than
all files at once.
```

---

## 8. Report/viva framing for scope decisions

- "Payments are simulated (Wallet model + fake UPI/card success flows) because real gateway integration requires merchant KYC/PCI compliance outside academic scope."
- "Product catalogs are seeded from [dataset name] + a synthetic price-history backfill rather than manually entered, so effort concentrates on the ML pipeline."
- "We chose a monolithic Django + Celery architecture over a microservice split because the ML logic is plain Python running as background tasks — a separate service would add deployment complexity without a corresponding benefit at this scale."
- "Price simulation follows a demand-curve-plus-noise model, not pure randomness, so the forecasting model has learnable signal — a deliberate design choice to make the ML component meaningful rather than decorative."
