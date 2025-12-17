import json
from pathlib import Path
from typing import Dict, List


class DataService:
    """
    Service responsible for retrieving company metadata
    from a local JSON source.
    """

    def __init__(self):
        self.data_path = (
            Path(__file__).resolve().parent.parent / "data" / "company_metadata.json"
        )
        self._load_data()

    def _load_data(self):
        if not self.data_path.exists():
            raise FileNotFoundError(
                f"company_metadata.json not found at {self.data_path}"
            )

        with open(self.data_path, "r") as f:
            self.company_data = json.load(f)

    def get_company_metadata(self, tickers: List[str]) -> Dict[str, Dict]:
        """
        Returns metadata for valid tickers.
        Invalid tickers are skipped.
        """
        result = {}

        for ticker in tickers:
            ticker = ticker.upper()
            if ticker in self.company_data:
                result[ticker] = self.company_data[ticker]

        return result

    def validate_tickers(self, tickers: List[str]) -> Dict[str, List[str]]:
        """
        Splits tickers into valid and invalid lists.
        """
        valid = []
        invalid = []

        for ticker in tickers:
            ticker = ticker.upper()
            if ticker in self.company_data:
                valid.append(ticker)
            else:
                invalid.append(ticker)

        return {
            "valid": valid,
            "invalid": invalid
        }
