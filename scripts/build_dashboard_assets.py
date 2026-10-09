from __future__ import annotations

from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

COLORS = {
    "navy": "#102A43",
    "blue": "#2F80ED",
    "teal": "#2A9D8F",
    "amber": "#F4A261",
    "red": "#D64550",
    "paper": "#F7F9FC",
    "ink": "#243B53",
}


def _style() -> None:
    sns.set_theme(style="whitegrid")
    plt.rcParams.update(
        {
            "figure.facecolor": COLORS["paper"],
            "axes.facecolor": "white",
            "axes.edgecolor": "#D9E2EC",
            "axes.labelcolor": COLORS["ink"],
            "text.color": COLORS["ink"],
            "font.size": 10,
        }
    )


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    database_path = root / "data" / "warehouse" / "restaurant_ops.duckdb"
    output = root / "dashboard"
    output.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(database_path), read_only=True)
    try:
        risk = connection.execute(
            """
            SELECT restaurant_name, borough, cuisine_description, risk_score, risk_tier,
                   critical_violation_count, matched_complaint_count
            FROM rpt_restaurant_risk
            WHERE inspection_count > 0
            ORDER BY risk_score DESC
            LIMIT 15
            """
        ).df()
        trend = connection.execute(
            """
            SELECT DATE_TRUNC('month', date_key) AS month,
                   SUM(inspections) AS inspections,
                   SUM(complaints) AS complaints,
                   SUM(critical_violations) AS critical_violations
            FROM rpt_daily_operations
            GROUP BY 1 ORDER BY 1
            """
        ).df()
        repeat = connection.execute(
            """
            SELECT v.violation_code, d.violation_description, COUNT(*) AS occurrences
            FROM fct_violation v
            JOIN dim_violation d USING (violation_code)
            GROUP BY 1, 2
            ORDER BY occurrences DESC
            LIMIT 12
            """
        ).df()
        complaint = connection.execute(
            """
            SELECT complaint_type, COUNT(*) AS complaints
            FROM fct_complaint GROUP BY 1 ORDER BY 2 DESC
            """
        ).df()
        kpis = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM dim_restaurant) AS restaurants,
                (SELECT COUNT(*) FROM fct_inspection) AS inspections,
                (SELECT COUNT(*) FROM fct_violation) AS violations,
                (SELECT COUNT(*) FROM fct_complaint) AS complaints,
                (SELECT COUNT(*) FROM rpt_restaurant_risk WHERE risk_tier IN ('HIGH','CRITICAL')) AS priority_restaurants
            """
        ).df().iloc[0]
    finally:
        connection.close()

    _style()
    fig = plt.figure(figsize=(16, 9), layout="constrained")
    grid = fig.add_gridspec(3, 12, height_ratios=[1.0, 4.0, 4.0])
    fig.suptitle("NYC Restaurant Operations & Risk Monitor", fontsize=22, fontweight="bold", color=COLORS["navy"])
    for idx, (label, value) in enumerate(
        [
            ("Restaurants", int(kpis["restaurants"])),
            ("Inspections", int(kpis["inspections"])),
            ("Violations", int(kpis["violations"])),
            ("311 complaints", int(kpis["complaints"])),
            ("Priority restaurants", int(kpis["priority_restaurants"])),
        ]
    ):
        ax = fig.add_subplot(grid[0, idx * 12 // 5 : (idx + 1) * 12 // 5])
        ax.axis("off")
        ax.text(0.02, 0.70, f"{value:,}", fontsize=22, fontweight="bold", color=COLORS["navy"])
        ax.text(0.02, 0.20, label, fontsize=10, color="#627D98")

    ax1 = fig.add_subplot(grid[1, :7])
    colors = risk["risk_tier"].map(
        {"CRITICAL": COLORS["red"], "HIGH": COLORS["amber"], "MEDIUM": COLORS["teal"], "LOW": COLORS["blue"]}
    )
    ax1.barh(risk["restaurant_name"].str.slice(0, 28)[::-1], risk["risk_score"][::-1], color=colors[::-1])
    ax1.set_title("Highest-priority restaurants")
    ax1.set_xlabel("Risk score")

    ax2 = fig.add_subplot(grid[1, 7:])
    ax2.bar(complaint["complaint_type"], complaint["complaints"], color=COLORS["teal"])
    ax2.set_title("311 complaint mix")
    ax2.tick_params(axis="x", rotation=30)
    ax2.set_ylabel("Complaints")

    ax3 = fig.add_subplot(grid[2, :7])
    if not trend.empty:
        ax3.plot(trend["month"], trend["inspections"], label="Inspections", color=COLORS["blue"], linewidth=2)
        ax3.plot(trend["month"], trend["complaints"], label="Complaints", color=COLORS["red"], linewidth=2)
    ax3.set_title("Monthly operating trend")
    ax3.legend(frameon=False)

    ax4 = fig.add_subplot(grid[2, 7:])
    labels = repeat["violation_code"].fillna("Unknown") + " — " + repeat["violation_description"].fillna("").str.slice(0, 22)
    ax4.barh(labels[::-1], repeat["occurrences"][::-1], color=COLORS["amber"])
    ax4.set_title("Most frequent violation codes")
    ax4.set_xlabel("Occurrences")
    fig.savefig(output / "executive-dashboard.png", dpi=170, bbox_inches="tight")
    plt.close(fig)

    trend.to_csv(output / "monthly_trend.csv", index=False)
    risk.to_csv(output / "priority_restaurants.csv", index=False)
    repeat.to_csv(output / "repeat_violations.csv", index=False)
    complaint.to_csv(output / "complaint_mix.csv", index=False)
    pd.DataFrame([kpis]).to_csv(output / "portfolio_kpis.csv", index=False)


if __name__ == "__main__":
    main()

