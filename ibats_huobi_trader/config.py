# -*- coding: utf-8 -*-
"""
Created on 2017/6/9
@author: MG
"""
import logging
from ibats_common.config import ConfigBase as ConBase, update_db_config
from ibats_common.common import ExchangeName

logger = logging.getLogger()


class ConfigBase(ConBase):
    # 交易所名称
    MARKET_NAME = ExchangeName.HuoBi.name

    # api configuration
    EXCHANGE_ACCESS_KEY = ""
    EXCHANGE_SECRET_KEY = ""

    # mysql db info
    DB_SCHEMA_MD = 'md_huobi'
    DB_URL_DIC = {
        DB_SCHEMA_MD: 'mysql://m*:****10.0.3.66/' + DB_SCHEMA_MD,
        ConBase.DB_SCHEMA_IBATS: 'mysql://m*:****@10.0.3.66/' + ConBase.DB_SCHEMA_IBATS,
    }

    # redis info
    REDIS_INFO_DIC = {'REDIS_HOST': 'localhost',
                      'REDIS_PORT': '6379',
                      }

    # evn configuration
    LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s %(filename)s.%(funcName)s:%(lineno)d|%(message)s'

    # 每一次实务均产生数据库插入或更新动作（默认：否）
    UPDATE_OR_INSERT_PER_ACTION = False

    def __init__(self):
        super().__init__()
        # 设定默认日志格式
        logging.basicConfig(level=logging.DEBUG, format=self.LOG_FORMAT)
        # 设置rest调用日志输出级别
        logging.getLogger('requests.packages.urllib3.connectionpool').setLevel(logging.WARNING)
        logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
        logging.getLogger('EventAgent').setLevel(logging.INFO)
        logging.getLogger('StgBase').setLevel(logging.INFO)


class ConfigProduct(ConfigBase):
    # 测试子账户 key
    EXCHANGE_ACCESS_KEY = '***'
    EXCHANGE_SECRET_KEY = '***'

    DB_URL_DIC = {
        ConfigBase.DB_SCHEMA_MD: 'mysql://m*:***@10.0.3.66/' + ConfigBase.DB_SCHEMA_MD,
        ConfigBase.DB_SCHEMA_IBATS: 'mysql://m*:***@10.0.3.66/' + ConfigBase.DB_SCHEMA_IBATS,
    }


# 开发配置（SIMNOW MD + Trade）
# config = ConfigBase()
# 测试配置（测试行情库）
# config = ConfigTest()
# 生产配置
config = ConfigProduct()
update_db_config(config.DB_URL_DIC)


def update_config(config_new: ConfigBase, update_db=True):
    global config
    config = config_new
    logger.info('更新默认配置信息 %s < %s', ConfigBase, config_new.__class__)
    if update_db:
        update_db_config(config.DB_URL_DIC)
