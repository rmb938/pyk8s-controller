import logging
import time
from queue import Queue

from k8scontroller.informer.cache import InformerCache
from k8scontroller.informer.lister import InformerList
from k8scontroller.informer.processor import InformerProcessQueue
from k8scontroller.informer.watcher import InformerWatch


class Informer(object):
    def __init__(self, name, resync_seconds, list_func, *list_args, **list_kwargs):
        self.logger = logging.getLogger("%s.%s" % (self.__module__, self.__class__.__name__))
        self.queue = Queue()
        self.name = name
        self.list_func = list_func
        self.list_args = list_args
        self.list_kwargs = list_kwargs
        self.resync_seconds = resync_seconds

        self.add_funcs = []
        self.update_funcs = []
        self.delete_funcs = []

        self.cache = InformerCache()
        self.processor = None
        self.watcher = None
        self.lister = None

    def add_event_funcs(self, add_func, update_func, delete_func):
        if add_func is not None:
            self.add_funcs.append(add_func)
        if update_func is not None:
            self.update_funcs.append(update_func)
        if delete_func is not None:
            self.delete_funcs.append(delete_func)

    def start(self):

        if self.processor is not None:
            raise Exception("Informer already running.")

        self.processor = InformerProcessQueue(self.queue, self.add_funcs, self.update_funcs, self.delete_funcs)
        self.watcher = InformerWatch(self.name, self.queue, self.cache, self.list_func, self.list_args,
                                     self.list_kwargs)
        self.lister = InformerList(self.name, self.queue, self.cache, self.resync_seconds, self.list_func,
                                   self.list_args, self.list_kwargs)

        self.processor.start()
        self.watcher.start()
        self.lister.start()

    # Wait until the cache is filled with the initial objects
    def wait_for_cache(self):
        while self.lister.first_run:
            time.sleep(1)

    def stop(self):
        self.lister.shutdown()
        self.watcher.shutdown()
        self.queue.join()
        # Shutdown the processor last so all remaining items can be processes
        self.processor.shutdown()
