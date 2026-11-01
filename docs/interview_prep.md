# Interview prep: Olist Sales Analytics

Ten questions an interviewer is likely to ask about this project, with answers grounded in the actual
numbers and decisions. Figures come from `outputs/*.csv`.

---

### 1. Walk me through the project in two minutes.

"I took Olist's public marketplace data: about 99k orders across 9 related tables. I wanted to answer four
business questions: where revenue comes from, whether customers come back, how delivery affects satisfaction,
and which sellers and payment habits matter. I loaded it into DuckDB with a proper schema (primary keys, foreign
keys, checks) and ran a data quality pass that turned up 18 issues, each with a documented handling rule. Then I
wrote eight SQL analyses using CTEs and window functions, built a star schema as views, and generated a Power BI
project with 22 DAX measures across 4 pages. One script rebuilds everything from raw data and verifies that every
number in the README matches the query outputs.

The headline: 2018 growth was +141% year over year, but it came entirely from volume. AOV was flat, only 3% of
customers ever came back, and late deliveries cut the average review from 4.29 to 2.27."

### 2. What data quality problems did you find, and how did you handle them?

The three that would have changed the answers:

* **Customer identity.** `customer_id` is regenerated per order: 99,441 ids but only 96,096 real people. Analysing
  on `customer_id` would show almost zero repeat customers, so all customer work uses `customer_unique_id`.
* **Order status.** 2,963 orders (2.98%) are shipped, canceled, unavailable and so on. Revenue only counts
  **delivered** orders, since the others aren't completed sales.
* **Time coverage.** The data has 4 orders in Sept 2016, none in Nov 2016, and no delivered orders in
  Sept/Oct 2018. Month-over-month growth on those months is noise, so trends use the 20 complete months Jan 2017
  to Aug 2018.

Others: 547 orders with several reviews (averaged per order so no order counts twice), 610 products with
no category (labelled `unknown`), 2 untranslated categories (mapped by hand), and 1,548 timestamp-order
anomalies (kept, since no metric depends on them). Everything is in `docs/data_quality.md` with counts.

### 3. How did you define revenue, and why?

Revenue = `SUM(order_items.price)` on delivered orders. I considered `payment_value`, but it includes freight
and installment interest, and it can't be split by product or seller. Item price splits cleanly by category,
seller and customer, so every analysis reconciles to one total: R$ 13,221,498 across 96,478 delivered orders.
Freight is reported separately. I checked the gap: 299 of 96,477 delivered orders have payments that don't equal
items plus freight, which is explained by interest and vouchers.

### 4. Explain your cohort retention query.

Each customer's cohort is the month of their first delivered order, found with
`MIN(order_month) OVER (PARTITION BY customer_unique_id)`. For every month they ordered, I compute the month offset:
`(year diff) * 12 + (month diff)`. Then I count distinct customers per cohort and offset and divide by cohort size.
`COUNT(*) FILTER (WHERE month_number = k)` pivots that into a matrix. One subtle point: cohorts near the end of the
data haven't had time to reach month 12, so I blank those cells with a CASE on months observed, rather than
showing a misleading 0%.

Result: no cohort ever retains more than 0.72% in any month, and the size-weighted month-1 retention is 0.483%.

### 5. How did you build the RFM segmentation? Why not NTILE for everything?

Recency = days since last order (relative to the day after the last purchase in the data), Frequency = delivered
orders, Monetary = item revenue. R and M are `NTILE(5)` quintiles. **F is not**, because 97% of customers have exactly
one order. NTILE would split identical one-order customers across quintiles 1 to 4 at random. So F uses fixed bands
(1 order = 1, 2 orders = 3, 3+ orders = 5). I also added `customer_unique_id` as a tie-breaker in the NTILE order, so
scores are deterministic between runs.

Segments are CASE rules on those scores. The most actionable one is **At Risk**: 13,888 customers who spent well
but haven't ordered in 6 to 12 months, holding 27.69% of revenue.

### 6. Late deliveries: how did you measure "late", and how strong is the effect?

Late = delivered on a later **calendar date** than the estimated date. The estimate has no time of day, so
comparing timestamps would mark same-day deliveries as late. 6.77% of delivered orders were late. Average review
is 4.29 on time vs 2.27 late. Bucketing by days late shows the effect is non-linear: one to three days late already
drops the score to 3.29, and from 8 days on, about 80% of reviews are 1 or 2 stars. It's also regional: Alagoas
21.41% late vs São Paulo 4.49%.

This is correlation, so I'd be careful about causal claims. But the dose-response pattern (more late, worse review),
and the fact that late orders score lower in 26 of 27 states (the exception, Amapá, has only 2 late orders), make it a strong signal.

### 7. Why a star schema for Power BI, and what modelling choices did you make?

Power BI's engine is built for star schemas: filters flow one way from dimensions to facts, and DAX stays simple.
I have two facts at different grains, `fact_orders` (one row per order: delivery, review, payment) and
`fact_order_items` (one row per line: price, freight). Instead of relating the two facts to each other, which
creates ambiguous filter paths, I put `customer_unique_id` and `purchase_date` on the items fact, so both facts
connect directly to the shared dimensions. `dim_date` is a gap-free calendar for full years, marked as the date
table, which time intelligence like `SAMEPERIODLASTYEAR` needs. RFM segment lives on `dim_customer` so it works as a
slicer.

### 8. Walk me through a DAX measure you wrote.

**Repeat Customer %**:

```DAX
VAR _customers =
    ADDCOLUMNS (
        CALCULATETABLE ( VALUES ( fact_orders[customer_unique_id] ), fact_orders[is_delivered] = 1 ),
        "@orders", CALCULATE ( DISTINCTCOUNT ( fact_orders[order_id] ), fact_orders[is_delivered] = 1 )
    )
RETURN DIVIDE ( COUNTROWS ( FILTER ( _customers, [@orders] >= 2 ) ), COUNTROWS ( _customers ) )
```

It builds a virtual table of the customers visible in the current filter context, with each one's order count
(`CALCULATE` triggers context transition per row), then divides the customers with 2+ orders by all customers.
Because it respects filter context, slicing by state or segment just works. Unsliced, it returns 3.00%, the same
as the SQL. I documented the expected card values in the build guide so anyone can check the DAX after refresh.

### 9. How do you know your numbers are right?

Several layers:
1. **Constraints at load.** PKs and FKs mean no duplicates or orphans can sneak in, and row counts are checked
   against every CSV.
2. **Reconciliation.** The same total (R$ 13,221,498 and 96,478 orders) comes out of the monthly, category, RFM
   and star schema paths. RFM segment counts from the view match the analysis query exactly.
3. **Automated README check.** `verify_readme.py` recomputes all 48 figures in the insights section and fails
   if any number isn't backed by an output file.
4. **Power BI validation.** Report JSON is validated against Microsoft's schemas, and a lint checks that every DAX
   and visual reference exists in the model. I tested both checkers by feeding them broken files.

### 10. What would you do next, or do differently?

* **Causality on delivery.** Model review score against lateness while controlling for category, price and
  freight, or use the estimate-padding idea as an A/B test.
* **Churn or second-purchase model.** With 3% repeat, a propensity model for who buys again in 30 days would
  target the retention budget.
* **Geography.** I skipped the 1M-row geolocation table. Seller-to-customer distance is probably the main
  driver of the North / Northeast lateness and would make the recommendation concrete.
* **Production.** On a real team I'd move the SQL to dbt (tests instead of my checks, lineage docs), run on
  PostgreSQL or a warehouse, and publish the PBIP through deployment pipelines.
