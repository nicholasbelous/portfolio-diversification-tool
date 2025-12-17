from typing import Dict, List
from collections import Counter


class AnalyticsService:
    """
    Handles portfolio-level analytics based on company metadata.
    """

    @staticmethod
    def calculate_sector_breakdown(
        companies: Dict[str, Dict]
    ) -> Dict[str, float]:
        """
        Returns sector exposure percentages.
        """
        sectors = [
            data["sector"]
            for data in companies.values()
            if "sector" in data
        ]

        sector_counts = Counter(sectors)
        total = sum(sector_counts.values())

        return {
            sector: round(count / total, 2)
            for sector, count in sector_counts.items()
        }

    @staticmethod
    def summarize_profile(
        companies: Dict[str, Dict]
    ) -> Dict[str, str]:
        """
        Returns high-level risk and growth summary.
        """
        risk_levels = [data.get("risk_profile") for data in companies.values()]
        growth_levels = [data.get("growth_profile") for data in companies.values()]

        risk_summary = Counter(risk_levels).most_common(1)[0][0]
        growth_summary = Counter(growth_levels).most_common(1)[0][0]

        return {
            "overall_risk": risk_summary,
            "overall_growth": growth_summary
        }
