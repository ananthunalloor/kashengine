from channels_redis.core import RedisChannelLayer

from config.settings import base


def test_channel_layer_read_timeout_outlasts_blocking_receive():
    # redis-py 8 defaults socket_timeout to 5s, the same as channels_redis's BZPOPMIN wait,
    # which made idle WebSocket consumers crash with "Timeout reading from redis".
    for host in base.CHANNEL_LAYERS["default"]["CONFIG"]["hosts"]:
        assert host["socket_timeout"] > RedisChannelLayer.brpop_timeout
