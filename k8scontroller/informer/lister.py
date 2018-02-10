import logging
import time
from threading import Thread, Event


class InformerList(Thread):
    def __init__(self, name, queue, cache, resync_seconds, list_func, list_args, list_kwargs):
        super().__init__()
        self.logger = logging.getLogger("%s.%s" % (self.__module__, self.__class__.__name__))
        self.name = name
        self.queue = queue
        self.cache = cache
        self.list_func = list_func
        self.list_args = list_args
        self.list_kwargs = list_kwargs
        self.resync_seconds = resync_seconds
        self.shutting_down = Event()
        self.first_run = True

    def run(self):
        while True:
            try:
                new_cache = {}
                ret = self.list_func(*self.list_args, **self.list_kwargs)
                for obj in ret['items']:
                    if self.shutting_down.is_set():
                        break
                    metadata = obj.get("metadata")

                    cache_key = metadata.get("namespace") + "/" + metadata.get(
                        "name") if metadata.get("namespace") != "" else metadata.get("name")

                    new_cache[cache_key] = obj
                self.cache.reset(new_cache)
                for _, obj in new_cache.items():
                    self.queue.put(("MODIFIED", obj))
                self.first_run = False
            except Exception:
                self.logger.error(
                    "Caught Exception while listing " + self.name +
                    " sleeping for 30 seconds before trying again. Enable debug logging to see exception")
                self.logger.debug("Exception: ", exc_info=True)
                time.sleep(30)
            if self.shutting_down.wait(timeout=self.resync_seconds):
                break

    def shutdown(self):
        self.shutting_down.set()
