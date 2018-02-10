import logging
from queue import Empty
from threading import Thread


class InformerProcessQueue(Thread):
    def __init__(self, queue, add_funcs, update_funcs, delete_funcs):
        super().__init__()
        self.logger = logging.getLogger("%s.%s" % (self.__module__, self.__class__.__name__))
        self.queue = queue
        self.funcs = {
            'ADDED': add_funcs,
            'MODIFIED': update_funcs,
            'DELETED': delete_funcs
        }
        self.shutting_down = False

    def run(self):
        while self.shutting_down is False:
            try:
                event, item = self.queue.get(timeout=1)
                try:
                    for func in self.funcs[event]:
                        if event == 'MODIFIED':
                            func(None, item)
                        else:
                            func(item)
                except (SystemExit, KeyboardInterrupt, GeneratorExit):
                    # Ignore these exceptions, exiting will be handled via signals
                    pass
                except Exception:
                    # Catch all errors and just log them so the loop doesn't break
                    # self.logger.exception("Error running function for event " + event + " and item " + item)
                    pass
                self.queue.task_done()
            except Empty:
                continue

    def shutdown(self):
        self.shutting_down = True
