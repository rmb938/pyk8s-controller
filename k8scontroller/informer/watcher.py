import logging
import time
from threading import Thread

from kubernetes import watch


class InformerWatch(Thread):
    def __init__(self, name, queue, cache, list_func, list_args, list_kwargs):
        super().__init__()
        self.logger = logging.getLogger("%s.%s" % (self.__module__, self.__class__.__name__))
        self.name = name
        self.queue = queue
        self.cache = cache
        self.list_func = list_func
        self.list_args = list_args
        self.list_kwargs = list_kwargs
        self.watcher = watch.Watch()
        self.shutting_down = False

    def run(self):
        resource_version = None
        while self.shutting_down is False:
            try:
                if resource_version is None:
                    # List first so we can get the resourceVersion to start at
                    # if we don't do this we get all events from the beginning of history
                    ret = self.list_func(*self.list_args, **self.list_kwargs)
                    resource_version = ret['metadata']['resourceVersion']
                stream = self.watcher.stream(self.list_func, *self.list_args,
                                             **{**self.list_kwargs, 'resource_version': resource_version})
                # If there is nothing to stream this will hang for as long as the api server
                # allows it. Any idea on how to break out sooner as it prevents a quick shutdown?
                for event in stream:
                    operation = event['type']
                    obj = event['object']

                    metadata = obj.get("metadata")
                    resource_version = metadata['resourceVersion']

                    cache_key = metadata.get("namespace") + "/" + metadata.get(
                        "name") if metadata.get("namespace") != "" else metadata.get("name")

                    self.cache.add(cache_key, obj)
                    self.queue.put((operation, obj))
            except Exception as e:
                self.logger.error(
                    "Caught Exception while watching " + self.name +
                    " sleeping for 30 seconds before trying again. Enable debug logging to see exception")
                self.logger.debug("Exception: ", exc_info=True)
                time.sleep(30)

    def shutdown(self):
        self.watcher.stop()
        self.shutting_down = True
