import logging
import threading
import time
import uuid

import arrow

from k8scontroller.election.record import ElectionRecord


class LeaderElector(threading.Thread):

    def __init__(self, election_name, election_namespace, on_started_leading, on_stopped_leading):
        super().__init__()
        self.logger = logging.getLogger("%s.%s" % (self.__module__, self.__class__.__name__))
        self.identity = str(uuid.uuid4())
        # duration before another election
        self.lease_duration = 15
        # duration that the acting master will retry
        # refreshing it's leadership before giving up
        self.renew_deadline = 10
        # duration clients should wait between tries of actions
        self.retry_period = 2

        # Election Info
        self.election_name = election_name
        self.election_namespace = election_namespace

        # async functions
        self.on_started_leading = on_started_leading
        self.on_stopped_leading = on_stopped_leading

        self.observed_record = None
        self.observed_time = None

        self.shutting_down = False

    def run(self):
        self.logger.debug("My identity is: " + self.identity)
        while self.shutting_down is False:
            self.logger.debug("Trying to become a leader")
            while True:
                try:
                    if self.shutting_down is True:
                        return
                    is_leader = self.try_acquire_or_renew()
                    if is_leader:
                        break
                except Exception:
                    self.logger.exception("Error trying to become leader")
                time.sleep(self.retry_period)
            self.logger.debug("I am now the leader... starting renew")
            threading.Thread(target=self.on_started_leading).start()
            try:
                self.renew()
            except Exception:
                self.logger.exception("Error trying to renew leadership")
            self.logger.debug("I am no longer the leader")
            threading.Thread(target=self.on_stopped_leading).start()

    def shutdown(self):
        self.shutting_down = True

    def renew(self):
        # Keep renewing until it returns false
        while self.try_acquire_or_renew() is True:
            if self.shutting_down is True:
                break
            time.sleep(self.retry_period)

    def try_acquire_or_renew(self):
        current_record = ElectionRecord.get(self.election_name, self.election_namespace)
        if current_record is None:
            self.logger.debug("Creating election record.. forcing leader to me")
            result = ElectionRecord()
            result.name = self.election_name
            result.leader_identity = self.identity
            result.lease_duration = self.lease_duration
            result.acquire_date = arrow.now()
            result.renew_date = result.acquire_date
            try:
                result.create(self.election_namespace)
            except Exception:
                self.logger.debug("Someone else forced leader before me")
                return False
            self.observed_record = result
            self.observed_time = arrow.now()
            return True

        if self.observed_record is None or self.observed_record.leader_data != current_record.leader_data:
            self.observed_record = current_record
            self.observed_time = arrow.now()

        if self.observed_time.shift(seconds=+self.lease_duration) > arrow.now() \
                and current_record.leader_identity != self.identity:
            self.logger.debug("Someone else is currently the leader")
            return False

        if current_record.leader_identity == self.identity:
            current_record.renew_date = arrow.now()
            self.logger.debug("I am the leader and I am renewing my lease")
        else:
            current_record.leader_identity = self.identity
            current_record.leader_transitions = current_record.leader_transitions + 1
            self.logger.debug("Previous leader lease expired... trying to become leader")

        try:
            current_record.update()
        except Exception:
            self.logger.debug("I tried to become a leader or renew but failed... someone took it!")
            # Someone else won the election
            return False
        self.observed_record = current_record
        self.observed_time = arrow.now()
        return True
