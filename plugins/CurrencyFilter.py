"""
Currency pairlist filter
"""
import logging
import sys
from copy import deepcopy
from typing import Any, Dict, List, Optional

from pandas import DataFrame

from freqtrade.plugins.pairlist.IPairList import IPairList
from freqtrade.exceptions import ExchangeError

logger = logging.getLogger(__name__)


class CurrencyFilter(IPairList):
    '''
    Filters pairs that exist in other currencies
    '''

    def __init__(self, exchange, pairlistmanager,
                 config: Dict[str, Any], pairlistconfig: Dict[str, Any],
                 pairlist_pos: int) -> None:
        super().__init__(exchange, pairlistmanager, config, pairlistconfig, pairlist_pos)

        self._currency = pairlistconfig.get('currency', 'BTC')
      
      
    @property
    def needstickers(self) -> bool:
        """
        Boolean property defining if tickers are necessary.
        If no Pairlist requires tickers, an empty List is passed
        as tickers argument to filter_pairlist
        """
        return False

    def short_desc(self) -> str:
        """
        Short whitelist method description - used for startup-messages
        """
        return (f"{self.name} - Filtering pairs that don't exist in "
                f"{self._currency}.")

    def filter_pairlist(self, pairlist: List[str], tickers: Dict) -> List[str]:
        """
        Validate trading range
        :param pairlist: pairlist to filter or sort
        :param tickers: Tickers (from exchange.get_tickers()). May be cached.
        :return: new allowlist
        """
        markets = self._exchange.markets
        result_pairlist = []
        
        for pair in pairlist:
            try:
                self._exchange.get_valid_pair_combination(pair[:pair.find("/")],self._currency)
                result_pairlist.append(pair)

            except ExchangeError:
                self.log_once(f"Removed {pair} from whitelist, because it's not part "
                              f"of the {self._currency} market.", logger.info)

        return result_pairlist

    