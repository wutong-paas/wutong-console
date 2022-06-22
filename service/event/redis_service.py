import json
from datetime import datetime, date

import redis
from loguru import logger
from redis import Sentinel
from redis.asyncio import Redis


class RedisService(object):
    """
    直接操作redis
    """

    def __init__(self, host=None, port=None, pwd=None, db=0, max_connections=10):
        """
        redis链接初始化
        :param host: redis实例的地址
        :param port:  端口
        :param pwd: 密码
        :param db:  使用的db
        :param max_connections: 连接池大小
        """
        self.pool = None
        self.redis_pool = None
        self.host = host
        self.port = port
        self.pwd = pwd
        self.db = db
        self.max_connections = max_connections

    def __get_redis_pool(self, flag):
        """
        获取连接池（主从切换以后把flag设置为True，重新初始化连接池）
        :param flag: 为False不用重新获取，为True需要重新获取
        :param max_connections: 连接池大小
        :return:
        """
        try:
            if not flag:
                if self.pool:
                    return self.pool
            # 缓存连接池
            self.pool = redis.ConnectionPool(host=self.host, port=self.port, db=self.db, password=self.pwd,
                                             max_connections=self.max_connections)
            return self.pool
        except Exception as e:
            logger.error(e)
            raise e

    def get_redis_client_from_pool(self, flag=False) -> Redis:
        """
        从链接池获取redis链接
        :param flag: 是否重新获取(主从切换后)
        :return:
        """
        return redis.Redis(connection_pool=self.__get_redis_pool(flag))

    def get_redis(self) -> Redis:
        """
        直接获取redis链接
        :return:
        """
        if self.pwd:
            return redis.Redis(host=self.host, port=self.port, db=self.db, password=self.pwd)
        return redis.Redis(host=self.host, port=self.port, db=self.db)


class SentinelService(RedisService):
    """
    通过哨兵操作redis
    """

    def __init__(self, sentinel_nodes_str=None, service_name=None, pwd=None, max_connections=10):
        """
        初始化哨兵服务
        :param sentinel_nodes_str: 哨兵地址
        :param service_name: 集群服务名称
        :param pwd:  密码
        :param max_connections:连接池大小
        """
        super(SentinelService, self).__init__(pwd=pwd, max_connections=max_connections)
        # 缓存的master的地址（如果一台机器不同端口，请拼接）
        self.master_host = None
        self.sentinel_nodes_str = sentinel_nodes_str
        self.service_name = service_name
        self.sentinel_nodes = self.__parse_nodes_str()

    def __parse_nodes_str(self):
        """
        哨兵参数解析
        :return:
        """
        try:
            list = []
            for sentinelInfo in self.sentinel_nodes_str.split(','):
                kv = sentinelInfo.split(":")
                list.append((kv[0], kv[1]))
            logger.info("from sentinel: %s", list)
            return list
        except Exception as e:
            logger.error(e)
            raise e

    def __get_master(self):
        """
        从哨兵节点获取master节点
        :return:
        """
        # 链接哨兵节点
        sentinel = Sentinel(self.sentinel_nodes, socket_timeout=0.1)
        # 获取master节点
        master = sentinel.discover_master(self.service_name)
        if master:
            # 赋值给RedisService
            self.host = master[0]
            self.port = master[1]
        return master

    def get_redis_client_from_pool(self, flag=False) -> Redis:
        """
        从链接池获取redis客户端
        :param flag:
        :return:
        """
        # 初始化master节点
        master = self.__get_master()
        # 没有主从切换，直接从连接池里获取
        if self.master_host in master:
            return super().get_redis_client_from_pool()
        # 主从切换了，更新缓存
        self.master_host = master[0]
        return super().get_redis_client_from_pool(True)

    def get_redis(self) -> Redis:
        """
        直接获取redis客户端
        :return:
        """
        self.__get_master()
        return super().get_redis()


class RedisStreamService(object):
    """
    redis stream封装
    """

    def __init__(self, redis_client, stream_name, consumer_group):
        """
        :param redis_client:redis的客户端
        :param stream_name:stream的名称
        :param consumer_group:消费组名称
        """
        self.redis_client = redis_client
        self.stream_name = stream_name
        self.consumer_group = consumer_group

    def stream_init(self, data, id="0", max_len=20000, target=None):
        """
        初始化stream，上线之前手动调用下即可，不用在项目里调用
        :param target: 目标方法
        :param data: 业务数据  测试数据
        :param id: 0 从开始消费, $ 从创建以后新进来的开始消费
        :param max_len: 队里最大长度
        :return:
        """
        if not self.redis_client.exists(self.stream_name):
            """
            不存在消费者，直接创建消费者和消费组
            """
            self.redis_client.xadd(self.stream_name, self.__data_wrap(data), maxlen=max_len)
            self.xgroup_create(id)
            self.redis_client.xadd(self.stream_name, self.__data_wrap(data), maxlen=max_len)
        self.consumer("system", count=2, target=target)

    def xgroup_create(self, id):
        """
        创建消费组
        :param id:
        :return:
        """
        self.redis_client.xgroup_create(self.stream_name, self.consumer_group, id=id)

    def __data_wrap(self, data) -> dict:
        """
        包装数据
        :param data:
        :return:
        """
        return {"biz_data": json.dumps(data, cls=JsonDateEncoder)}

    def xack(self, msgId):
        """
        ack
        :param msgId:
        :return:
        """
        self.redis_client.xack(self.stream_name, self.consumer_group, msgId)

    def __get_biz_data(self, data):
        """
        从消息流中获取业务数据
        :param item:
        :return:
        """
        if not data or not data[0]:
            return None, None
        msg_id = str(data[0], 'utf-8')
        data = {str(key, 'utf-8'): str(val, 'utf-8') for key, val in data[1].items()}
        return msg_id, data["biz_data"]

    def add(self, data):
        """
        新增数据
        :param stream_name:
        :param data:
        :return:
        """
        self.redis_client.xadd(self.stream_name, self.__data_wrap(data))

    def consumer(self, consumer_name, consume_message_id=">", block=60000, count=1, target=None):
        """
        消费数据
        :param consumer_name: 消费者名称，建议传递ip
        :param consume_message_id: 从哪开始消费
        :param block: 无消息阻塞时间，毫秒，默认60秒，在60秒内有消息直接消费
        :param count: 消费多少条，默认1
        :param target: 业务处理回调方法
        :return:
        """
        # block 0 时阻塞等待, 其他数值表示读取超时时间
        streams = {self.stream_name: consume_message_id}
        rst = self.redis_client.xreadgroup(self.consumer_group, consumer_name, streams, block=block, count=count)

        if not rst or not rst[0] or not rst[0][1]:
            logger.info("队列消息为空")
            return None
        logger.info("消费数据:{}", rst)
        # 遍历获取到的列表信息（可以消费多条，根据count）
        for item in rst[0][1]:
            try:
                # 解析数据
                msg_id, data = self.__get_biz_data(item)
                """
                执行回调函数target,成功后ack
                """
                if target and target(msg_id, data):
                    # 将处理完成的消息标记，类似于kafka的offset
                    self.redis_client.xack(self.stream_name, self.consumer_group, msg_id)
            except Exception as e:
                # 消费失败，下次从头消费(消费成功的都已经提交ack了，可以先不处理，以后再处理)
                logger.error("consumer is error:", e)


class JsonDateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(obj, date):
            return obj.strftime('%Y-%m-%d')
        else:
            return json.JSONEncoder.default(self, obj)
