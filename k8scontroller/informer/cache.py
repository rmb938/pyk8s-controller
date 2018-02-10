from threading import RLock

from go_defer import with_defer, defer


class InformerCache(object):
    def __init__(self):
        self.cache = {}
        self.lock = RLock()

    @with_defer
    def get(self, key):
        self.lock.acquire()
        defer(self.lock.release)
        return self.cache.get(key)

    @with_defer
    def add(self, key, item):
        self.lock.acquire()
        defer(self.lock.release)
        self.cache[key] = item

    @with_defer
    def delete(self, key):
        self.lock.acquire()
        defer(self.lock.release)
        self.cache.pop(key, None)

    @with_defer
    def reset(self, new_cache):
        self.lock.acquire()
        defer(self.lock.release)
        self.cache = new_cache
