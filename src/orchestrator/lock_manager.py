import contextlib
import logging

logger = logging.getLogger(__name__)

class LockManager:
    def __init__(self):
        self._locks = set()

    @contextlib.contextmanager
    def advisory_lock(self, lock_id: str):
        if lock_id in self._locks:
            raise RuntimeError(f"Lock {lock_id} is already acquired")
        self._locks.add(lock_id)
        logger.debug(f"Acquired lock {lock_id}")
        try:
            yield
        finally:
            if lock_id in self._locks:
                self._locks.remove(lock_id)
                logger.debug(f"Released lock {lock_id}")
