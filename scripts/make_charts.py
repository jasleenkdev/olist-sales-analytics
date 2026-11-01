"""Render static PNG charts into images/.

dashboard_*.png mirror the four Power BI pages. The other files chart single
analyses. Every figure reads outputs/*.csv (the SQL results); the revenue-by-
state panel reads powerbi/data/, the exported star schema.

Style: one light surface, recessive axes and hairline grid, one hue per chart
unless colour carries meaning (blue = metric, orange = late / attention).
No dual axes.
"""
import matplotlib

matplotlib.use("Agg")
import duckdb
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from common import IMAGES_DIR, OUTPUT_DIR, PBI_DATA_DIR

SURFACE, PAGE = "#fcfcfb", "#f9f9f7"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

plt.rcParams.update({
    "font.family": ["Helvetica Neue", "Arial", "DejaVu Sans"],
    "font.size": 10, "text.color": INK, "axes.labelcolor": INK2,
    "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "axes.facecolor": SURFACE,
    "figure.facecolor": PAGE, "xtick.color": MUTED, "ytick.color": MUTED,
    "xtick.labelsize": 9, "ytick.labelsize": 9, "axes.titlesize": 12,
    "axes.titleweight": "semibold", "axes.titlelocation": "left", "axes.titlepad": 10,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "legend.frameon": False, "savefig.dpi": 160,
})


def out(name: str) -> pd.DataFrame:
    return pd.read_csv(OUTPUT_DIR / f"{name}.csv")


def brl(x: float, decimals: int = 0) -> str:
    if abs(x) >= 1e6:
        return f"R$ {x / 1e6:.2f}M"
    if abs(x) >= 1e3 and decimals == 0:
        return f"R$ {x / 1e3:.0f}k"
    return f"R$ {x:,.{decimals}f}"


money_axis = mtick.FuncFormatter(lambda v, _: brl(v))


def ygrid_only(ax):
    ax.grid(axis="x", visible=False)


def xgrid_only(ax):
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)


def save(fig, name: str) -> None:
    fig.savefig(IMAGES_DIR / name, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"wrote images/{name}")


def month_labels(months: pd.Series) -> list[str]:
    d = pd.to_datetime(months)
    return [m.strftime("%b\n%Y") if m.month == 1 or i == 0 else m.strftime("%b")
            for i, m in enumerate(d)]


# ------------------------------------------------------------------ panels
def panel_revenue_trend(ax, df):
    x = np.arange(len(df))
    ax.plot(x, df.revenue, color=BLUE, lw=2, marker="o", ms=4)
    ax.yaxis.set_major_formatter(money_axis)
    ax.set_xticks(x, month_labels(df.order_month))
    peak = df.revenue.idxmax()
    ax.annotate(f"Nov 2017 peak (Black Friday)\n{brl(df.revenue[peak])}", (x[peak], df.revenue[peak]),
                xytext=(-190, 0), textcoords="offset points", fontsize=9, color=INK2,
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    ax.set_ylim(0, df.revenue.max() * 1.15)
    ygrid_only(ax)


def panel_hbar(ax, labels, values, fmt, color=BLUE, highlight=None):
    y = np.arange(len(labels))[::-1]
    colors = [ORANGE if highlight and highlight(i) else color for i in range(len(labels))]
    ax.barh(y, values, color=colors, height=0.66)
    ax.set_yticks(y, labels)
    for yi, v in zip(y, values):
        ax.text(v, yi, "  " + fmt(v), va="center", fontsize=8.5, color=INK2)
    ax.set_xlim(0, max(values) * 1.32)
    ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)
    xgrid_only(ax)


def kpi_row(fig, gs_row, items):
    for i, (label, value) in enumerate(items):
        ax = fig.add_subplot(gs_row[i])
        ax.set_facecolor(SURFACE)
        ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(True)
            s.set_color(GRID)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.text(0.08, 0.66, label, fontsize=9.5, color=INK2, transform=ax.transAxes)
        ax.text(0.08, 0.24, value, fontsize=19, weight="semibold", color=INK, transform=ax.transAxes)


# ------------------------------------------------------------------ figures
def headline_numbers() -> dict:
    d = PBI_DATA_DIR.as_posix()
    rev, orders, cust = duckdb.sql(
        f"SELECT SUM(price), COUNT(DISTINCT order_id), COUNT(DISTINCT customer_unique_id) "
        f"FROM read_csv('{d}/fact_order_items.csv') WHERE is_delivered = 1").fetchone()
    dl = out("q5_delivery_overall").iloc[0]
    rep = out("q8_repeat_summary").iloc[0]
    return dict(revenue=float(rev), orders=orders, customers=cust, aov=float(rev) / orders,
                review=dl.avg_review, late=dl.late_pct, repeat=rep.repeat_rate_pct)


def dashboard_executive(h):
    m = out("q1_monthly_revenue")
    fig = plt.figure(figsize=(14, 7.2))
    gs = fig.add_gridspec(2, 6, height_ratios=[1, 4.2], hspace=0.28, wspace=0.12)
    kpi_row(fig, [gs[0, i] for i in range(6)], [
        ("Total revenue", brl(h["revenue"])), ("Delivered orders", f"{h['orders']:,}"),
        ("Avg order value", brl(h["aov"], 2)), ("Active customers", f"{h['customers']:,}"),
        ("Avg review score", f"{h['review']:.2f} / 5"), ("Late deliveries", f"{h['late']:.1f}%")])
    ax = fig.add_subplot(gs[1, :])
    panel_revenue_trend(ax, m)
    ax.set_title("Monthly revenue, delivered orders (Jan 2017 to Aug 2018)")
    fig.suptitle("Executive Overview", x=0.125, ha="left", fontsize=16, weight="bold", y=0.98)
    save(fig, "dashboard_1_executive_overview.png")


def state_revenue() -> pd.DataFrame:
    d = PBI_DATA_DIR.as_posix()
    return duckdb.sql(f"""
        SELECT c.customer_state AS state, SUM(i.price) AS revenue
        FROM read_csv('{d}/fact_order_items.csv') i
        JOIN read_csv('{d}/dim_customer.csv') c USING (customer_unique_id)
        WHERE i.is_delivered = 1
        GROUP BY 1 ORDER BY 2 DESC LIMIT 10""").df()


def dashboard_sales():
    m = out("q1_monthly_revenue")
    cat = out("q2_top_categories")
    st = state_revenue()
    fig = plt.figure(figsize=(14, 9))
    gs = fig.add_gridspec(2, 2, hspace=0.42, wspace=0.42)
    x = np.arange(len(m))
    ax = fig.add_subplot(gs[0, 0])
    ax.bar(x, m.revenue, color=BLUE, width=0.7)
    ax.yaxis.set_major_formatter(money_axis)
    ax.set_xticks(x, month_labels(m.order_month), fontsize=7.5)
    ax.set_title("Revenue by month")
    ygrid_only(ax)
    ax = fig.add_subplot(gs[0, 1])
    ax.plot(x, m.orders, color=BLUE, lw=2, marker="o", ms=4)
    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("{x:,.0f}"))
    ax.set_ylim(0, m.orders.max() * 1.12)
    ax.set_xticks(x, month_labels(m.order_month), fontsize=7.5)
    ax.set_title("Delivered orders by month")
    ygrid_only(ax)
    ax = fig.add_subplot(gs[1, 0])
    panel_hbar(ax, cat.category.str.replace("_", " "), cat.revenue,
               lambda v: f"{brl(v)}")
    ax.set_title("Top 10 categories by revenue")
    ax = fig.add_subplot(gs[1, 1])
    panel_hbar(ax, st.state, st.revenue, lambda v: brl(v))
    ax.set_title("Top 10 customer states by revenue")
    fig.suptitle("Sales Trends", x=0.125, ha="left", fontsize=16, weight="bold", y=0.97)
    save(fig, "dashboard_2_sales_trends.png")


def dashboard_customers(h):
    seg = out("q4_rfm_segments")
    fig = plt.figure(figsize=(14, 7.6))
    gs = fig.add_gridspec(2, 4, height_ratios=[1, 4.4], hspace=0.3, wspace=0.12)
    rep = out("q8_repeat_summary").iloc[0]
    kpi_row(fig, [gs[0, i] for i in range(4)], [
        ("Active customers", f"{h['customers']:,}"),
        ("Repeat customers", f"{rep.repeat_rate_pct:.2f}%"),
        ("Median days to 2nd order", f"{rep.median_days_to_second:.0f}"),
        ("Revenue per customer", brl(h["revenue"] / h["customers"], 2))])
    by_size = seg.sort_values("customers", ascending=False)
    bottom = gs[1, :].subgridspec(1, 2, wspace=0.42)
    ax = fig.add_subplot(bottom[0])
    panel_hbar(ax, by_size.segment, by_size.customers, lambda v: f"{v:,.0f}")
    ax.set_title("Customers by RFM segment")
    by_rev = seg.sort_values("total_revenue", ascending=False)
    ax = fig.add_subplot(bottom[1])
    panel_hbar(ax, by_rev.segment, by_rev.total_revenue,
               lambda v: f"{brl(v)}  ({100 * v / seg.total_revenue.sum():.1f}%)")
    ax.set_title("Revenue by RFM segment")
    fig.suptitle("Customers & RFM", x=0.125, ha="left", fontsize=16, weight="bold", y=0.98)
    save(fig, "dashboard_3_customers_rfm.png")


def dashboard_delivery():
    st = out("q5_delivery_by_state").sort_values("late_pct", ascending=False)
    lb = out("q5_review_by_lateness")
    ov = out("q5_delivery_overall").iloc[0]
    fig = plt.figure(figsize=(14, 8.6))
    gs = fig.add_gridspec(2, 2, width_ratios=[1, 1.5], hspace=0.4, wspace=0.25)
    ax = fig.add_subplot(gs[:, 0])
    overall = ov.late_pct
    panel_hbar(ax, st.customer_state, st.late_pct, lambda v: f"{v:.1f}%",
               highlight=lambda i: st.late_pct.iloc[i] > overall * 1.5)
    ax.set_title(f"Late delivery % by customer state\n(orange = over 1.5x the {overall:.1f}% average)",
                 fontsize=11)
    ax.tick_params(axis="y", labelsize=8)
    ax = fig.add_subplot(gs[0, 1])
    labels = [b.split(". ", 1)[1] for b in lb.lateness_bucket]
    colors = [BLUE] + [ORANGE] * (len(lb) - 1)
    bars = ax.bar(labels, lb.avg_review, color=colors, width=0.6)
    for b, v in zip(bars, lb.avg_review):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.06, f"{v:.2f}", ha="center", fontsize=9, color=INK2)
    ax.set_ylim(0, 5)
    ax.set_ylabel("Average review score (1 to 5)")
    ax.set_title("Review score collapses once an order is late")
    ygrid_only(ax)
    ax = fig.add_subplot(gs[1, 1])
    bars = ax.bar(labels, lb.pct_low_reviews_1_2, color=colors, width=0.6)
    for b, v in zip(bars, lb.pct_low_reviews_1_2):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.2, f"{v:.0f}%", ha="center", fontsize=9, color=INK2)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_title("Share of 1 and 2 star reviews")
    ygrid_only(ax)
    fig.suptitle("Delivery & Reviews", x=0.125, ha="left", fontsize=16, weight="bold", y=0.97)
    save(fig, "dashboard_4_delivery_reviews.png")


def chart_cohort_heatmap():
    mat = out("q3_cohort_retention_matrix")
    mat = mat[mat["m1"].notna()].reset_index(drop=True)  # Aug 2018 has no follow-up month yet
    cols = [f"m{i}" for i in range(1, 13)]
    data = mat[cols].to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(12, 7.5))
    cmap = LinearSegmentedColormap.from_list("seq", SEQ)
    cmap.set_bad(SURFACE)
    im = ax.imshow(np.ma.masked_invalid(data), cmap=cmap, aspect="auto", vmin=0, vmax=0.8)
    for (r, c_), v in np.ndenumerate(data):
        if not np.isnan(v):
            ax.text(c_, r, f"{v:.2f}", ha="center", va="center", fontsize=7.5,
                    color="#ffffff" if v > 0.45 else INK)
    ax.set_xticks(range(12), [f"+{i}" for i in range(1, 13)])
    ax.set_yticks(range(len(mat)), [f"{pd.Timestamp(d):%b %Y}  (n={n:,})"
                                    for d, n in zip(mat.cohort_month, mat.cohort_customers)], fontsize=8)
    ax.set_xlabel("Months after first purchase")
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label("% of cohort ordering again", color=INK2)
    cb.outline.set_visible(False)
    ax.set_title("Monthly cohort retention (%): under 1% of any cohort returns in a given month")
    save(fig, "cohort_retention_heatmap.png")


def chart_monthly_revenue():
    m = out("q1_monthly_revenue")
    fig, ax = plt.subplots(figsize=(12, 5))
    panel_revenue_trend(ax, m)
    ax.set_title("Monthly revenue, delivered orders (Jan 2017 to Aug 2018)")
    save(fig, "monthly_revenue.png")


def chart_payment_mix():
    p = out("q7_payment_mix")
    inst = out("q7_installments")
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6), gridspec_kw=dict(wspace=0.45))
    panel_hbar(axes[0], p.payment_type.str.replace("_", " "), p.value_share_pct, lambda v: f"{v:.1f}%")
    axes[0].set_title("Share of payment value by method")
    bars = axes[1].bar(inst.installment_band.str.replace(" (single payment)", "\n(single)"),
                       inst.payment_share_pct, color=BLUE, width=0.6)
    for b, v, a in zip(bars, inst.payment_share_pct, inst.avg_payment_value):
        axes[1].text(b.get_x() + b.get_width() / 2, v + 0.8, f"{v:.0f}%\navg {brl(a, 0) if a >= 1000 else f'R$ {a:.0f}'}",
                     ha="center", fontsize=8.5, color=INK2)
    axes[1].set_ylim(0, inst.payment_share_pct.max() * 1.3)
    axes[1].yaxis.set_major_formatter(mtick.PercentFormatter())
    axes[1].set_xlabel("Installments")
    axes[1].set_title("Credit card payments by number of installments")
    ygrid_only(axes[1])
    save(fig, "payment_mix.png")


def chart_seller_concentration():
    s = out("q6_seller_concentration")
    fig, ax = plt.subplots(figsize=(10, 4.6))
    x = s.revenue_decile
    bars = ax.bar(x, s.revenue_share_pct, color=BLUE, width=0.65)
    for b, v in zip(bars, s.revenue_share_pct):
        ax.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.1f}%", ha="center", fontsize=9, color=INK2)
    ax.set_xticks(x, [f"Top {10 * d}%" if d == 1 else f"D{d}" for d in x])
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_ylim(0, 80)
    ax.set_xlabel("Seller revenue decile (297 sellers each)")
    ax.set_title("Share of revenue by seller decile: the top 10% of sellers earn two thirds")
    ygrid_only(ax)
    save(fig, "seller_concentration.png")


def chart_orders_per_customer():
    o = out("q8_orders_per_customer")
    fig, ax = plt.subplots(figsize=(9, 4.2))
    bars = ax.bar(o.orders_per_customer.astype(str), o.customer_share_pct, color=BLUE, width=0.55)
    for b, v, n in zip(bars, o.customer_share_pct, o.customers):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.2f}%\n({n:,})", ha="center", fontsize=9, color=INK2)
    ax.set_ylim(0, 115)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_xlabel("Delivered orders per customer")
    ax.set_title("97% of customers bought exactly once")
    ygrid_only(ax)
    save(fig, "orders_per_customer.png")


def main():
    IMAGES_DIR.mkdir(exist_ok=True)
    h = headline_numbers()
    dashboard_executive(h)
    dashboard_sales()
    dashboard_customers(h)
    dashboard_delivery()
    chart_monthly_revenue()
    chart_cohort_heatmap()
    chart_payment_mix()
    chart_seller_concentration()
    chart_orders_per_customer()


if __name__ == "__main__":
    main()
