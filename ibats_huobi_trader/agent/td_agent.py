# -*- coding: utf-8 -*-
"""
Created on 2017/10/3
@author: MG
"""
import logging
from datetime import datetime, timedelta
from huobitrade import setKey
from ibats_huobi_trader.config import config
from ibats_common.utils.db import with_db_session
from ibats_common.backend import engines
from ibats_common.common import PositionDateType, RunMode, ExchangeName
from ibats_common.utils.mess import floor
from ibats_common.trade import TraderAgentBase, trader_agent, BacktestTraderAgentBase
from huobitrade.service import HBRestAPI
from ibats_huobi_trader.backend import engine_md
from ibats_huobi_trader.backend.orm import SymbolPair
from collections import defaultdict
from enum import Enum

engine_ibats = engines.engine_ibats
logger = logging.getLogger()
# 设置秘钥
setKey(config.EXCHANGE_ACCESS_KEY, config.EXCHANGE_SECRET_KEY)


class OrderType(Enum):
    """
    buy-market：市价买, sell-market：市价卖, buy-limit：限价买, sell-limit：限价卖, buy-ioc：IOC买单, sell-ioc：IOC卖单
    """
    buy_market = 'buy-market'
    sell_market = 'sell-market'
    buy_limit = 'buy-limit'
    sell_limit = 'sell-limit'
    buy_ioc = 'buy-ioc'
    sell_ioc = 'sell-ioc'


@trader_agent(RunMode.Backtest, ExchangeName.HuoBi, is_default=False)
class BacktestTraderAgent(BacktestTraderAgentBase):
    """
    供调用模拟交易接口使用
    """

    def __init__(self, stg_run_id, **kwargs):
        super().__init__(stg_run_id, **kwargs)


@trader_agent(RunMode.Realtime, ExchangeName.BitMex, is_default=False)
class RealTimeTraderAgent(TraderAgentBase):
    """
    供调用实时交易接口使用
    """

    def __init__(self, stg_run_id, **run_mode_params):
        super().__init__(stg_run_id, **run_mode_params)
        self.trader_api = HBRestAPI()
        self.currency_balance_dic = {}
        self.currency_balance_last_get_datetime = None
        self.symbol_currency_dic = None
        self.symbol_precision_dic = None
        self._datetime_last_rtn_trade_dic = {}
        self._datetime_last_update_position_dic = {}

    def connect(self):
        with with_db_session(engine_md) as session:
            data = session.query(SymbolPair).all()
            self.symbol_currency_dic = {
                f'{sym.base_currency}{sym.quote_currency}': sym.base_currency
                for sym in data}
            self.symbol_precision_dic = {
                f'{sym.base_currency}{sym.quote_currency}': (int(sym.price_precision), int(sym.amount_precision))
                for sym in data}

    # @try_n_times(times=3, sleep_time=2, logger=logger)
    def open_long(self, symbol, price, vol):
        """买入多头"""
        price_precision, amount_precision = self.symbol_precision_dic[symbol]
        if isinstance(price, float):
            price = format(price, f'.{price_precision}f')
        if isinstance(vol, float):
            if vol < 10 ** -amount_precision:
                logger.warning('%s open_long 订单量 %f 太小，忽略', symbol, vol)
                return
            vol = format(floor(vol, amount_precision), f'.{amount_precision}f')
        self.trader_api.send_order(vol, symbol, OrderType.buy_limit.value, price)
        self._datetime_last_rtn_trade_dic[symbol] = datetime.now()

    def close_long(self, symbol, price, vol):
        """卖出多头"""
        price_precision, amount_precision = self.symbol_precision_dic[symbol]
        if isinstance(price, float):
            price = format(price, f'.{price_precision}f')
        if isinstance(vol, float):
            if vol < 10 ** -amount_precision:
                logger.warning('%s close_long 订单量 %f 太小，忽略', symbol, vol)
                return
            vol = format(floor(vol, amount_precision), f'.{amount_precision}f')
        self.trader_api.send_order(vol, symbol, OrderType.sell_limit.value, price)
        self._datetime_last_rtn_trade_dic[symbol] = datetime.now()

    def open_short(self, instrument_id, price, vol):
        # self.trader_api.open_short(instrument_id, price, vol)
        raise NotImplementedError()

    def close_short(self, instrument_id, price, vol):
        # self.trader_api.close_short(instrument_id, price, vol)
        raise NotImplementedError()

    def get_position(self, instrument_id, force_refresh=False) -> dict:
        """
        instrument_id（相当于 symbol )
        symbol ethusdt, btcusdt
        currency eth, btc
        :param instrument_id:
        :param force_refresh:
        :return:
        """
        symbol = instrument_id
        currency = self.get_currency(symbol)
        # currency = instrument_id
        # self.logger.debug('symbol:%s force_refresh=%s', symbol, force_refresh)
        position_date_inv_pos_dic = self.get_balance(currency=currency, force_refresh=force_refresh)
        return position_date_inv_pos_dic

    def get_currency(self, symbol):
        """
        根据 symbol 找到对应的 currency
        symbol: ethusdt, btcusdt
        currency: eth, btc
        :param symbol:
        :return:
        """
        return self.symbol_currency_dic[symbol]

    def get_balance(self, non_zero_only=False, trade_type_only=True, currency=None, force_refresh=False):
        """
        调用接口 查询 各个币种仓位
        :param non_zero_only: 只保留非零币种
        :param trade_type_only: 只保留 trade 类型币种，frozen 类型的不保存
        :param currency: 只返回制定币种 usdt eth 等
        :param force_refresh: 强制刷新，默认没30秒允许重新查询一次
        :return: {'usdt': {<PositionDateType.History: 2>: {'currency': 'usdt', 'type': 'trade', 'balance': 144.09238}}}
        """
        if force_refresh or self.currency_balance_last_get_datetime is None or \
                self.currency_balance_last_get_datetime < datetime.now() - timedelta(seconds=30):
            ret_data = self.trader_api.get_balance()
            acc_balance = ret_data['data']['list']
            self.logger.debug('更新持仓数据： %d 条', len(acc_balance))
            acc_balance_new_dic = defaultdict(dict)
            for balance_dic in acc_balance:
                currency_curr = balance_dic['currency']
                self._datetime_last_update_position_dic[currency_curr] = datetime.now()

                if non_zero_only and balance_dic['balance'] == '0':
                    continue

                if trade_type_only and balance_dic['type'] != 'trade':
                    continue
                balance_dic['balance'] = float(balance_dic['balance'])
                # self.logger.debug(balance_dic)
                if PositionDateType.History in acc_balance_new_dic[currency_curr]:
                    balance_dic_old = acc_balance_new_dic[currency_curr][PositionDateType.History]
                    balance_dic_old['balance'] += balance_dic['balance']
                    # TODO: 日后可以考虑将 PositionDateType.History 替换为 type
                    acc_balance_new_dic[currency_curr][PositionDateType.History] = balance_dic
                else:
                    acc_balance_new_dic[currency_curr] = {PositionDateType.History: balance_dic}

            self.currency_balance_dic = acc_balance_new_dic
            self.currency_balance_last_get_datetime = datetime.now()

        if currency is not None:
            if currency in self.currency_balance_dic:
                ret_data = self.currency_balance_dic[currency]
                # for position_date_type, data in self.currency_balance_dic[currency].items():
                #     if data['currency'] == currency:
                #         ret_data = data
                #         break
            else:
                ret_data = None
        else:
            ret_data = self.currency_balance_dic
        return ret_data

    @property
    def datetime_last_update_position(self) -> datetime:
        return self.currency_balance_last_get_datetime

    @property
    def datetime_last_rtn_trade_dic(self) -> dict:
        return self._datetime_last_rtn_trade_dic

    @property
    def datetime_last_update_position_dic(self) -> dict:
        return self._datetime_last_update_position_dic

    @property
    def datetime_last_send_order_dic(self) -> dict:
        raise NotImplementedError()

    def get_order(self, instrument_id, states='submitted') -> list:
        """

        :param instrument_id:
        :param states:
        :return: 格式如下：
        [{'id': 603164274, 'symbol': 'ethusdt', 'account-id': 909325, 'amount': '4.134700000000000000',
'price': '983.150000000000000000', 'created-at': 1515166787246, 'type': 'buy-limit',
'field-amount': '4.134700000000000000', 'field-cash-amount': '4065.030305000000000000',
'field-fees': '0.008269400000000000', 'finished-at': 1515166795669, 'source': 'web',
'state': 'filled', 'canceled-at': 0},
 ... ]
        """
        symbol = instrument_id
        ret_data = self.trader_api.get_orders_info(symbol=symbol, states=states)
        return ret_data['data']

    def cancel_order(self, instrument_id):
        symbol = instrument_id
        order_list = self.get_order(symbol)
        order_id_list = [data['id'] for data in order_list]
        return self.trader_api.batchcancel_order(order_id_list)

    def release(self):
        pass


if __name__ == "__main__":
    import time

    # 测试交易 下单接口及撤单接口
    # symbol, vol, price = 'ocnusdt', 1, 0.00004611  # OCN/USDT
    symbol, vol, price = 'eosusdt', 1.0251, 4.1234  # OCN/USDT

    td = RealTimeTraderAgent(stg_run_id=1, run_mode_params={})
    td.open_long(symbol=symbol, price=price, vol=vol)
    order_dic_list = td.get_order(instrument_id=symbol)
    print('after open_long', order_dic_list)
    assert len(order_dic_list) == 1
    td.cancel_order(instrument_id=symbol)
    time.sleep(1)
    order_dic_list = td.get_order(instrument_id=symbol)
    print('after cancel', order_dic_list)
    assert len(order_dic_list) == 0
