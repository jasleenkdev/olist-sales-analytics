# Power BI build guide

`scripts/build_pbip.py` generates this file from the same spec it uses to write the PBIR report,
so the guide and `powerbi/OlistSalesAnalytics/` always match. Use it to check the generated
report, or to rebuild any page by hand in Power BI Desktop.

## 1. Open the project

1. Power BI Desktop (Windows), version from 2024 or later. Under *File > Options > Preview features*,
   turn on **Power BI Project (.pbip) save option** and **Store semantic model using TMDL format**.
   In newer releases, also turn on **Store reports using enhanced metadata format (PBIR)** if it is listed.
2. Point the `DataFolder` parameter at your copy of `powerbi/data/`. Either:
   * regenerate the project with the path baked in:
     `python scripts/build_pbip.py --data-folder "C:\\path\\to\\olist-sales-analytics\\powerbi\\data\\"`, or
   * open the file, then *Transform data > Edit parameters > DataFolder*.
   The value must end with a backslash.
3. Open `powerbi/OlistSalesAnalytics/OlistSalesAnalytics.pbip` and click **Refresh**.

## 2. Model

| Table | Grain | Role |
|---|---|---|
| fact_orders | one row per order (all statuses) | order-level facts: delivery, review, payment |
| fact_order_items | one row per order line | revenue facts: price, freight |
| dim_customer | one row per customer_unique_id | location + RFM segment |
| dim_product | one row per product | English category |
| dim_seller | one row per seller | seller location |
| dim_date | one row per day, 2016-01-01 to 2018-12-31 | **marked as date table** (`dataCategory: Time`, `isKey` on `date`) |
| _Measures | none | holds all DAX measures (hidden placeholder column) |

Relationships (all many-to-one, single direction):

* `fact_orders[customer_unique_id]` -> `dim_customer[customer_unique_id]`
* `fact_orders[purchase_date]` -> `dim_date[date]`
* `fact_order_items[customer_unique_id]` -> `dim_customer[customer_unique_id]`
* `fact_order_items[purchase_date]` -> `dim_date[date]`
* `fact_order_items[product_id]` -> `dim_product[product_id]`
* `fact_order_items[seller_id]` -> `dim_seller[seller_id]`

Auto date/time is off. Implicit measures are discouraged, so use the measures below.

## 3. Measures

| Measure | Folder | Format | DAX |
|---|---|---|---|
| Total Revenue | Sales | `\R\$ #,0` | `CALCULATE ( SUM ( fact_order_items[price] ), fact_order_items[is_delivered] = 1 )` |
| Total Orders | Sales | `#,0` | `CALCULATE ( DISTINCTCOUNT ( fact_order_items[order_id] ), fact_order_items[is_delivered] = 1 )` |
| AOV | Sales | `\R\$ #,0.00` | `DIVIDE ( [Total Revenue], [Total Orders] )` |
| Total Freight | Sales | `\R\$ #,0` | `CALCULATE ( SUM ( fact_order_items[freight_value] ), fact_order_items[is_delivered] = 1 )` |
| Revenue PY | Time Intelligence | `\R\$ #,0` | `CALCULATE ( [Total Revenue], SAMEPERIODLASTYEAR ( dim_date[date] ) )` |
| Revenue YoY % | Time Intelligence | `0.0%` | `VAR _py = [Revenue PY] RETURN IF ( NOT ISBLANK ( _py ), DIVIDE ( [Total Revenue] - _py, _py ) )` |
| Revenue PM | Time Intelligence | `\R\$ #,0` | `CALCULATE ( [Total Revenue], DATEADD ( dim_date[date], -1, MONTH ) )` |
| Revenue MoM % | Time Intelligence | `0.0%` | `VAR _pm = [Revenue PM] RETURN IF ( NOT ISBLANK ( _pm ), DIVIDE ( [Total Revenue] - _pm, _pm ) )` |
| Running Total Revenue | Time Intelligence | `\R\$ #,0` | `VAR _maxDate = MAX ( dim_date[date] ) RETURN CALCULATE ( [Total Revenue], REMOVEFILTERS ( dim_date ), dim_date[date] <= _maxDate )` |
| Delivered Orders With Date | Delivery | `#,0` | `CALCULATE ( COUNTROWS ( fact_orders ), NOT ISBLANK ( fact_orders[is_late] ) )` |
| Late Orders | Delivery | `#,0` | `CALCULATE ( COUNTROWS ( fact_orders ), fact_orders[is_late] = 1 )` |
| Late Delivery % | Delivery | `0.0%` | `DIVIDE ( [Late Orders], [Delivered Orders With Date] )` |
| Avg Delivery Days | Delivery | `0.0` | `CALCULATE ( AVERAGE ( fact_orders[delivery_days] ), fact_orders[is_delivered] = 1 )` |
| Avg Review Score | Reviews | `0.00` | `CALCULATE ( AVERAGE ( fact_orders[review_score] ), fact_orders[is_delivered] = 1 )` |
| Avg Review On Time | Reviews | `0.00` | `CALCULATE ( [Avg Review Score], fact_orders[is_late] = 0 )` |
| Avg Review Late | Reviews | `0.00` | `CALCULATE ( [Avg Review Score], fact_orders[is_late] = 1 )` |
| Active Customers | Customers | `#,0` | `CALCULATE ( DISTINCTCOUNT ( fact_orders[customer_unique_id] ), fact_orders[is_delivered] = 1 )` |
| Repeat Customer % | Customers | `0.00%` | `VAR _customers = ADDCOLUMNS ( CALCULATETABLE ( VALUES ( fact_orders[customer_unique_id] ), fact_orders[is_delivered] = 1 ), "@orders", CALCULATE ( DISTINCTCOUNT ( fact_orders[order_id] ), fact_orders[is_delivered] = 1 ) ) RETURN DIVIDE ( COUNTROWS ( FILTER ( _customers, [@orders] >= 2 ) ), COUNTROWS ( _customers ) )` |
| RFM Customers | Customers | `#,0` | `CALCULATE ( COUNTROWS ( dim_customer ), dim_customer[rfm_segment] <> "No Delivered Order" )` |
| RFM Revenue | Customers | `\R\$ #,0` | `SUM ( dim_customer[lifetime_revenue] )` |
| Avg Customer Value | Customers | `\R\$ #,0.00` | `DIVIDE ( [RFM Revenue], [RFM Customers] )` |
| Avg Recency Days | Customers | `0` | `AVERAGE ( dim_customer[recency_days] )` |

## 4. Theme

`powerbi/theme/OlistTheme.json` (copied into the report's `StaticResources/RegisteredResources/`).
To apply it by hand: *View > Themes > Browse for themes*. It uses an 8-colour categorical palette
checked for colour-blind separation, a light page background (`#f9f9f7`), white-ish cards
(`#fcfcfb`) with a hairline border, and recessive grey axes.

## 5. Pages

Canvas 1280 x 720, *Fit to page*. Positions are x, y, width, height in pixels.
"Window filter" = visual-level filter `dim_date[in_analysis_window] = 1`, which keeps only
the 20 complete months (Jan 2017 to Aug 2018).

### 5.1 Executive Overview

| Visual | Title | Fields | Sort | Position | Filter |
|---|---|---|---|---|---|
| Card | Total Revenue | **Values**: [Total Revenue] |  | 16, 16, 196, 100 |  |
| Card | Total Orders | **Values**: [Total Orders] |  | 226, 16, 196, 100 |  |
| Card | AOV | **Values**: [AOV] |  | 437, 16, 196, 100 |  |
| Card | Active Customers | **Values**: [Active Customers] |  | 647, 16, 196, 100 |  |
| Card | Avg Review Score | **Values**: [Avg Review Score] |  | 858, 16, 196, 100 |  |
| Card | Late Delivery % | **Values**: [Late Delivery %] |  | 1068, 16, 196, 100 |  |
| Line chart | Monthly revenue (Jan 2017 to Aug 2018) | **Category**: dim_date[year_month]<br>**Y**: [Total Revenue] | dim_date[year_month] ascending | 16, 132, 808, 572 | Window filter |
| Table | Monthly growth | **Values**: dim_date[year_month], [Total Revenue], [Revenue MoM %], [Revenue YoY %] | dim_date[year_month] ascending | 840, 132, 424, 572 | Window filter |

### 5.2 Sales Trends

| Visual | Title | Fields | Sort | Position | Filter |
|---|---|---|---|---|---|
| Slicer | Year | **Values**: dim_date[year] |  | 16, 16, 300, 84 |  |
| Clustered column chart | Revenue by month | **Category**: dim_date[year_month]<br>**Y**: [Total Revenue] | dim_date[year_month] ascending | 16, 112, 408, 292 | Window filter |
| Line chart | Orders by month | **Category**: dim_date[year_month]<br>**Y**: [Total Orders] | dim_date[year_month] ascending | 436, 112, 408, 292 | Window filter |
| Line chart | Running total revenue | **Category**: dim_date[year_month]<br>**Y**: [Running Total Revenue] | dim_date[year_month] ascending | 856, 112, 408, 292 | Window filter |
| Clustered bar chart | Revenue by category | **Category**: dim_product[category]<br>**Y**: [Total Revenue] | [Total Revenue] descending | 16, 420, 624, 284 |  |
| Clustered bar chart | Revenue by customer state | **Category**: dim_customer[customer_state]<br>**Y**: [Total Revenue] | [Total Revenue] descending | 656, 420, 608, 284 |  |

### 5.3 Customers & RFM

| Visual | Title | Fields | Sort | Position | Filter |
|---|---|---|---|---|---|
| Card | Active Customers | **Values**: [Active Customers] |  | 16, 16, 300, 100 |  |
| Card | Repeat Customer % | **Values**: [Repeat Customer %] |  | 332, 16, 300, 100 |  |
| Card | Avg Customer Value | **Values**: [Avg Customer Value] |  | 648, 16, 300, 100 |  |
| Card | Avg Recency Days | **Values**: [Avg Recency Days] |  | 964, 16, 300, 100 |  |
| Clustered bar chart | Customers by RFM segment | **Category**: dim_customer[rfm_segment]<br>**Y**: [RFM Customers] | [RFM Customers] descending | 16, 132, 408, 572 |  |
| Clustered bar chart | Revenue by RFM segment | **Category**: dim_customer[rfm_segment]<br>**Y**: [RFM Revenue] | [RFM Revenue] descending | 440, 132, 408, 572 |  |
| Table | Segment profile | **Values**: dim_customer[rfm_segment], [RFM Customers], [Avg Recency Days], [Avg Customer Value], [RFM Revenue] | [RFM Revenue] descending | 864, 132, 400, 572 |  |

### 5.4 Delivery & Reviews

| Visual | Title | Fields | Sort | Position | Filter |
|---|---|---|---|---|---|
| Card | Late Delivery % | **Values**: [Late Delivery %] |  | 16, 16, 300, 100 |  |
| Card | Avg Delivery Days | **Values**: [Avg Delivery Days] |  | 332, 16, 300, 100 |  |
| Card | Avg Review On Time | **Values**: [Avg Review On Time] |  | 648, 16, 300, 100 |  |
| Card | Avg Review Late | **Values**: [Avg Review Late] |  | 964, 16, 300, 100 |  |
| Clustered bar chart | Late delivery % by customer state | **Category**: dim_customer[customer_state]<br>**Y**: [Late Delivery %] | [Late Delivery %] descending | 16, 132, 408, 572 |  |
| Clustered column chart | Average review score by days past the estimate | **Category**: fact_orders[lateness_bucket]<br>**Y**: [Avg Review Score] | fact_orders[lateness_bucket] ascending | 440, 132, 824, 284 |  |
| Line chart | Late delivery % by month | **Category**: dim_date[year_month]<br>**Y**: [Late Delivery %] | dim_date[year_month] ascending | 440, 432, 824, 272 | Window filter |

## 6. Expected values

With no slicers applied, the cards should show these values (computed from the same CSVs
with SQL). A mismatch means a relationship or measure is wrong.

| Card | Expected value |
|---|---:|
| Total Revenue | R$ 13,221,498 |
| Total Orders | 96,478 |
| AOV | R$ 137.04 |
| Active Customers | 93,358 |
| Avg Review Score | 4.16 |
| Late Delivery % | 6.8% |
| Avg Delivery Days | 12.5 |
| Repeat Customer % | 3.00% |

## 7. Screenshots

After refreshing, export each page (*File > Export > PDF*, or a screen capture) to
`images/powerbi_<page>.png`. The matplotlib versions in `images/` show the same metrics
until those exist.
