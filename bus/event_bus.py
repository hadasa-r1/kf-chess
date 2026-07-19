"""In-process publish/subscribe event bus.

Responsibility split: EventBus only routes `Event` objects from publishers
to subscribed callables matched by type - it has no idea what a "move" or
a "score" means, and no idea who its subscribers are (UI, sound, logging,
persistence, ...). Behavior lives entirely in the handlers that get
subscribed. A later step will construct one EventBus instance and inject
it into GameEngine (to publish) and into UI/sound/logging components (to
subscribe) - this module does not wire itself into anything.
"""

from __future__ import annotations

import itertools
import logging
import threading
from dataclasses import dataclass
from typing import Callable

from bus.events import Event

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Subscription:
    """Opaque handle returned by `subscribe`, passed back to `unsubscribe`.

    Lets callers drop a subscription without holding onto the original
    handler callable themselves.
    """

    id: int
    event_type: type


class EventBus:
    """Routes published events to subscribers registered for their type.

    Instantiable, not a singleton - whoever assembles the application owns
    one instance and passes it around via constructor injection.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._subscribers: dict[type, dict[int, Callable[[Event], None]]] = {}
        self._ids = itertools.count()

    def subscribe(self, event_type: type, handler: Callable[[Event], None]) -> Subscription:
        """Register `handler` for `event_type`. Subscribing to a base class
        (e.g. `Event` itself) also receives every subclass event, since
        `publish` matches against the published event's full MRO."""
        subscription_id = next(self._ids)
        with self._lock:
            self._subscribers.setdefault(event_type, {})[subscription_id] = handler
        return Subscription(id=subscription_id, event_type=event_type)

    def unsubscribe(self, subscription: Subscription) -> None:
        with self._lock:
            handlers = self._subscribers.get(subscription.event_type)
            if handlers is not None:
                handlers.pop(subscription.id, None)

    def publish(self, event: Event) -> None:
        """Dispatch `event` to every handler subscribed to its type or any
        of its base types. Handlers run outside the lock so a handler that
        itself calls subscribe/publish cannot deadlock, and each handler's
        exceptions are isolated so one bad subscriber can't stop the rest
        or crash the publisher."""
        handlers_to_call = []
        with self._lock:
            for event_type in type(event).__mro__:
                handlers = self._subscribers.get(event_type)
                if handlers:
                    handlers_to_call.extend(handlers.values())

        for handler in handlers_to_call:
            try:
                handler(event)
            except Exception:
                logger.exception("EventBus handler %r raised while handling %r", handler, event)
