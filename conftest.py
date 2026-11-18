"""pytest 根配置。

这里不定义 fixture，只把 helpers 暴露在根目录，供各案例测试直接 import。
真正可复用的工具函数见 helpers.py。
"""

from helpers import SUBPROCESS_ENV, free_port, load_server, wait_healthy  # noqa: F401
