import concurrent.futures
import logging
from abc import ABC, abstractmethod

from go_defer import with_defer, defer

from k8scontroller.informer.informer import Informer
from k8scontroller.workqueue import WorkQueue


class Controller(ABC):
    def __init__(self, name, worker_count, resync_seconds, list_func, *list_args, **list_kwargs):
        super().__init__()
        self.logger = logging.getLogger("%s.%s" % (self.__module__, self.__class__.__name__))
        self.worker_count = worker_count

        self.informer = Informer(name, resync_seconds, list_func, *list_args, **list_kwargs)
        self.informer.add_event_funcs(self.__add_func, self.__update_func, None)

        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.worker_count)

        self.workqueue = WorkQueue()
        self.shutdown = False

    def __add_func(self, obj):
        metadata = obj.get("metadata")
        key = metadata.get("namespace") + "/" + metadata.get("name") if metadata.get(
            "namespace") != "" else metadata.get("name")
        # Add the key to the queue
        # This allows us to pull the item from cache
        self.workqueue.add(key)

    def __update_func(self, _, obj):
        return self.__add_func(obj)

    def start(self):
        self.informer.start()
        self.informer.wait_for_cache()

        # Run workers
        for _ in range(0, self.worker_count):
            if self.executor._shutdown is False:
                self.executor.submit(self.run_worker)

    def run_worker(self):
        while self.shutdown is False and self.process_next_item():
            pass

    def process_next_item(self):
        key, shutdown = self.workqueue.get()
        if shutdown:
            # If the queue is shutdown we should stop working
            return False

        @with_defer
        def _process_item(key):
            # Remove from workqueue because we are done with the object
            defer(self.workqueue.done, key)
            self.sync_handler(key)

        # noinspection PyBroadException
        try:
            _process_item(key)
        except (SystemExit, KeyboardInterrupt, GeneratorExit):
            # Ignore these exceptions, exiting will be handled via signals
            pass
        except Exception:
            # Catch all errors and just log them so the loop doesn't break
            self.logger.exception("Error processing item: " + key)

        return True

    def stop(self):
        self.informer.stop()
        self.workqueue.shutdown()
        self.executor.shutdown()
        self.shutdown = True

    @abstractmethod
    def sync_handler(self, key):
        raise NotImplementedError
