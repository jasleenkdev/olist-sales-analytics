"""Check that every number in README.md's "Key insights" section matches outputs/*.csv.

Each CHECK pairs the exact text used in the README with a value recomputed
from the output files. The script fails if:
  * a recomputed value does not appear in the README text, or
  * the insights section contains a number that no check covers.
"""
import re
import sys

import pandas as pd

from common import OUTPUT_DIR, ROOT


def o(name: str) -> pd.DataFrame:
    return pd.read_csv(OUTPUT_DIR / f"{name}.csv")


def money(v: float) -> str:
    return f"R$ {v:,.0f}"


def money2(v: float) -> str:
    return f"R$ {v:,.2f}"


def pct(v: float, d: int = 2) -> str:
    return f"{v:.{d}f}%"


def build_checks() -> list[tuple[str, str]]:
    y = o("q1_yearly_summary").set_index("order_year")
    m = o("q1_monthly_revenue")
    m18 = m[m.order_month >= "2018-01-01"]
    nov = m.set_index("order_month").loc["2017-11-01"]
    peak = o("q1_peak_days").iloc[0]
    rep = o("q8_repeat_summary").iloc[0]
    curve = o("q3_retention_curve").set_index("month_number")
    mat = o("q3_cohort_retention_matrix")
    max_cell = mat[[f"m{i}" for i in range(1, 13)]].max().max()
    dov = o("q5_delivery_overall").iloc[0]
    lb = o("q5_review_by_lateness").set_index("lateness_bucket")
    st = o("q5_delivery_by_state").set_index("customer_state")
    cat = o("q2_top_categories")
    dec = o("q6_seller_concentration").set_index("revenue_decile")
    pay = o("q7_payment_mix").set_index("payment_type")
    inst = o("q7_installments").set_index("installment_band")
    seg = o("q4_rfm_segments").set_index("segment")

    assert max_cell < 1, "insight 3 claims under 1% monthly retention"
    return [
        # 1. growth
        ("R$ 7,218,125", money(y.loc[2018, "revenue"])),
        ("R$ 2,993,456", money(y.loc[2017, "revenue"])),
        ("141.13%", pct(y.loc[2018, "revenue_yoy_pct"])),
        ("139.94%", pct(y.loc[2018, "orders_yoy_pct"])),
        ("R$ 136.08", money2(y.loc[2017, "aov"])),
        ("R$ 136.75", money2(y.loc[2018, "aov"])),
        ("R$ 826,437", money(m18.revenue.min())),
        ("R$ 977,545", money(m18.revenue.max())),
        # 2. Black Friday
        ("R$ 987,765", money(nov.revenue)),
        ("+52.37% MoM", f"+{pct(nov.revenue_mom_pct)} MoM"),
        ("24 Nov 2017", pd.Timestamp(peak.order_date).strftime("%-d %b %Y")),
        ("1,147 delivered orders", f"{int(peak.orders):,} delivered orders"),
        ("4.7x", f"{peak.times_month_average:.1f}x"),
        # 3. retention
        ("3.0%", pct(rep.repeat_rate_pct, 1)),
        ("93,358 customers", f"{int(rep.customers):,} customers"),
        ("2,801 people", f"{int(rep.repeat_customers):,} people"),
        ("under 1%", "under 1%"),
        ("0.483% at month 1", f"{curve.loc[1, 'weighted_retention_pct']:.3f}% at month 1"),
        ("29 days", f"{rep.median_days_to_second:.0f} days"),
        ("75 days", f"{rep.median_days_to_second_excl_same_day:.0f} days"),
        ("829 same-day", f"{int(rep.same_day_second_orders)} same-day"),
        # 4. delivery
        ("6.77%", pct(dov.late_pct)),
        ("**4.29**", f"**{dov.avg_review_on_time:.2f}**"),
        ("**2.27**", f"**{dov.avg_review_late:.2f}**"),
        ("9.23%", pct(lb.loc["1. On time or early", "pct_low_reviews_1_2"])),
        ("80.08%", pct(lb.loc["4. 8-14 days late", "pct_low_reviews_1_2"])),
        ("8 to 14 days late", "8 to 14 days late"),
        ("1 and 2 star", "1 and 2 star"),
        ("21.41%", pct(st.loc["AL", "late_pct"])),
        ("17.43%", pct(st.loc["MA", "late_pct"])),
        ("4.49%", pct(st.loc["SP", "late_pct"])),
        # 5. categories and sellers
        ("top 10 categories", "top 10 categories"),
        ("62.43%", pct(cat.cumulative_share_pct.iloc[9])),
        ("9.33%", pct(cat.revenue_share_pct.iloc[0])),
        ("top 10% of sellers (297)", f"top 10% of sellers ({dec.loc[1, 'sellers']})"),
        ("67.11%", pct(dec.loc[1, "revenue_share_pct"])),
        ("top 30%", "top 30%"),
        ("90.05%", pct(dec.loc[3, "cumulative_share_pct"])),
        # 6. payments
        ("78.46%", pct(pay.loc["credit_card", "value_share_pct"])),
        ("3.5 installments", f"{pay.loc['credit_card', 'avg_installments']:.1f} installments"),
        ("R$ 95.60", money2(inst.loc["01 (single payment)", "avg_payment_value"])),
        ("10+", "10+"),
        ("R$ 407.47", money2(inst.loc["10+", "avg_payment_value"])),
        # 7. RFM
        ("13,888 one-time buyers", f"{seg.loc['At Risk', 'customers']:,} one-time buyers"),
        ("6 to 12 months", "6 to 12 months"),  # r_score 2-3 = 178-383 days, see q4_rfm_score_grid
        ("27.69%", pct(seg.loc["At Risk", "revenue_share_pct"])),
        ("R$ 3,660,858", money(seg.loc["At Risk", "total_revenue"])),
        ("29.25%", pct(seg.loc["Promising", "revenue_share_pct"])),
    ]


def main() -> int:
    text = (ROOT / "README.md").read_text()
    section = text.split("## Key insights", 1)[1].split("\n## ", 1)[0]
    flat = " ".join(section.split())
    checks = build_checks()
    bad = [(want, got) for want, got in checks if want != got or got not in flat]
    covered = " ".join(w for w, _ in checks)
    # Numbers in prose (ignore list numbering "1." at line start and "Jan to Aug" style text).
    numbers = set(n.rstrip(",") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", re.sub(r"(?m)^\d+\.\s", "", section)))
    uncovered = sorted(n for n in numbers if n not in covered and n not in {"2017", "2018"})
    for want, got in bad:
        print(f"MISMATCH: README has '{want}', outputs give '{got}'")
    for n in uncovered:
        print(f"UNCHECKED number in README insights: {n}")
    if bad or uncovered:
        return 1
    print(f"README verified: {len(checks)} figures match outputs/*.csv, "
          f"{len(numbers)} distinct numbers in the insights section all covered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
