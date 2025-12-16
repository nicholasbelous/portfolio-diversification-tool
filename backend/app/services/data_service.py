from typing import List, Dict, Tuple
import pandas as pd

class DataSevice:
    """
    Fetching and caching market data
    """
    
    def __init__(self, cach_ttl: int = 3600):
        self.cache_ttl = cach_ttl
        self._price_cache = {}
        self._info_cache = {}
        
    async def fetch_portfolio_data(
        self,
        tickers: List[str],
        period: str = "1y"
    ) -> Tuple[pd.DataFrame, dict[str, str]]:
        """
        Historical pricing and sector info for the list of tickers
        
        :param self: Description
        :param tickers: Description
        :type tickers: List[str]
        :param period: Description
        :type period: str
        :return: Description
        :rtype: Tuple[DataFrame, dict[str, str]]
        """
        
        raise NotImplementedError
    
    async def validate_tickers(self, tickers: List[str]) -> Dict[str, List[str]]:
        """
        Validates ticker symbols,
        returns valid and invalid symbols
        
        :param self: Description
        :param tickers: Description
        :type tickers: List[str]
        :return: Description
        :rtype: Dict[str, List[str]]
        """
        
        raise NotImplementedError