# Data quality report

Produced by `sql/02_data_quality.sql`. Raw results are in `outputs/data_quality/*.csv`.
Every count below comes from those files.

## 1. Load integrity

All 9 tables loaded with row counts equal to their CSVs. Primary keys, foreign keys
and the `review_score BETWEEN 1 AND 5` check were enforced during the load, so
**no duplicate keys and no orphan child rows exist** (for example, every
`order_items.product_id` is a real product).

| table | rows |
|---|---:|
| orders | 99,441 |
| order_items | 112,650 |
| order_payments | 103,886 |
| order_reviews | 99,224 |
| customers | 99,441 |
| products | 32,951 |
| sellers | 3,095 |
| geolocation | 1,000,163 |
| category_translation | 71 |

## 2. Issues found and how each is handled

| # | Issue | Count | Handling |
|---|---|---:|---|
| 1 | Orders not in status `delivered` (shipped, canceled, unavailable, invoiced, processing, created, approved) | 2,963 of 99,441 (2.98%) | **All revenue, customer and delivery analysis uses delivered orders only** (96,478). An order still in progress or cancelled is not a completed sale. |
| 2 | Orders with no items | 775 | All 775 are non-delivered, so the delivered-only rule already drops them. |
| 3 | `order_delivered_customer_date` NULL | 2,965 | 8 of these are `delivered` orders. They count toward revenue but are **left out of delivery-time and late % metrics** because their delivery date is unknown. |
| 4 | Delivery date present but status not delivered | 6 | Status wins: these are treated as not delivered. |
| 5 | Handed to carrier before purchase (166) or before approval (1,359); delivered before carrier pickup (23) | 1,548 rows | Source timestamp noise. Not used by any metric (late % compares the customer delivery date to the estimate), so the rows are kept. |
| 6 | `customer_id` is per order, not per person: 96,096 unique people behind 99,441 ids; 2,997 people have several ids | 2,997 | **Customer-level analysis (cohorts, RFM, repeat rate) uses `customer_unique_id`.** Using `customer_id` would show almost zero repeat customers. |
| 7 | `review_id` shared by several orders | 789 ids | Primary key is `(review_id, order_id)`. |
| 8 | Orders with more than one review | 547 | The scores are **averaged per order** before any aggregate, so an order is not counted twice. |
| 9 | Orders with no review | 768 (646 of them delivered) | Left out of review averages, kept everywhere else. |
| 10 | Products with NULL category (also NULL name length, description length and photos) | 610 | Shown as category **`unknown`**. |
| 11 | Categories with no English translation (`pc_gamer`, `portateis_cozinha_e_preparadores_de_alimentos`) | 13 products | Mapped in the views to `pc_gamer` and `portable_kitchen_food_preparers`. |
| 12 | Products with NULL weight (2) or weight 0 (4) | 6 | Kept. Weight is not used by any metric. |
| 13 | Payments with value 0 (9), installments 0 (2), type `not_defined` (3) | 14 rows | `not_defined` rows all belong to canceled orders, so the delivered-only rule drops them. The rest are kept: they are vouchers or rounding. |
| 14 | Delivered order with no payment row | 1 | Revenue comes from item prices, so this order still counts. It is left out only of the payment-mix analysis. |
| 15 | Payments do not equal items + freight | 299 of 96,477 delivered orders (260 paid more, 39 paid less) | Expected: installment interest and vouchers. **Revenue is defined as the sum of `order_items.price`** (product revenue, freight excluded), so all analyses reconcile to one number. |
| 16 | Sparse start and hard stop in time: 4 orders in Sept 2016, none in Nov 2016, 1 in Dec 2016, and only 16 and 4 orders (none delivered) in Sept and Oct 2018 | see `08_date_coverage.csv` | **Time-series analysis (monthly trend, MoM, YoY) uses the 20 full months Jan 2017 to Aug 2018.** Other analyses use all delivered orders. |
| 17 | Geolocation exact duplicate rows | 261,831 extra copies | Table is not used downstream (see DECISIONS.md 1.7). |
| 18 | Customer zip prefixes missing from geolocation | 278 | Not relevant, since geolocation is not used. |

## 3. Order status distribution

| status | orders | % |
|---|---:|---:|
| delivered | 96,478 | 97.02 |
| shipped | 1,107 | 1.11 |
| canceled | 625 | 0.63 |
| unavailable | 609 | 0.61 |
| invoiced | 314 | 0.32 |
| processing | 301 | 0.30 |
| created | 5 | 0.01 |
| approved | 2 | 0.00 |

## 4. Resulting analysis base

* **96,478 delivered orders**, **110,197 order items**, **13,221,498.11 BRL** item revenue.
* Customer identity = `customer_unique_id`.
* Revenue = `SUM(order_items.price)`; freight is reported separately.
