from __future__ import annotations

import asyncio
import queue
from dataclasses import dataclass, field
from typing import Any

# Event type constants
TRACK_DOWNLOAD_STARTED = "TRACK_DOWNLOAD_STARTED"
TRACK_DOWNLOAD_COMPLETED = "TRACK_DOWNLOAD_COMPLETED"
PLAYLIST_PROGRESS = "PLAYLIST_PROGRESS"
PLAYLIST_COMPLETED = "PLAYLIST_COMPLETED"
SYNC_PROGRESS = "SYNC_PROGRESS"
SYNC_COMPLETED = "SYNC_COMPLETED"
ERROR = "ERROR"


@dataclass
class NotificationEvent:
    """Payload for a notification event."""
    event_type: str
    job_id: str | None = None
    progress: float | None = None
    message: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "job_id": self.job_id,
            "progress": self.progress,
            "message": self.message,
            **self.payload,
        }


class NotificationBus:
    """
    Notification bus with sync publishing (for threads/CLI) and async consumption (WebSocket).
    Uses a thread-safe queue.Queue for sync publish; a bridge task forwards to subscriber queues.
    """

    def __init__(self) -> None:
        self._sync_queue: queue.Queue[NotificationEvent] = queue.Queue()
        self._subscribers: set[asyncio.Queue[NotificationEvent]] = set()
        self._bridge_task: asyncio.Task[None] | None = None
        self._stop = False

    def publish_sync(self, event: NotificationEvent) -> None:
        """Thread-safe: publish from sync code (e.g. background worker thread)."""
        self._sync_queue.put_nowait(event)

    async def publish(self, event: NotificationEvent) -> None:
        """Async: publish from async code."""
        for sub in list(self._subscribers):
            try:
                sub.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def subscribe(self) -> asyncio.Queue[NotificationEvent]:
        """Create a new subscriber queue. Caller should await queue.get() in a loop."""
        q: asyncio.Queue[NotificationEvent] = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[NotificationEvent]) -> None:
        self._subscribers.discard(q)

    def _get_event(self) -> NotificationEvent:
        """Block until an event is available (used by bridge in thread)."""
        return self._sync_queue.get(timeout=0.5)

    async def _bridge(self) -> None:
        """Run in event loop: drain sync_queue and broadcast to all subscribers."""
        while not self._stop:
            try:
                event = await asyncio.to_thread(self._get_event)
            except queue.Empty:
                continue
            except asyncio.CancelledError:
                break
            except Exception:
                continue
            for sub in list(self._subscribers):
                try:
                    sub.put_nowait(event)
                except asyncio.QueueFull:
                    pass

    def start_bridge(self, loop: asyncio.AbstractEventLoop) -> None:
        """Start the bridge task that forwards sync_queue to subscribers."""
        if self._bridge_task is not None:
            return
        self._stop = False
        self._bridge_task = loop.create_task(self._bridge())

    def stop_bridge(self) -> None:
        """Signal the bridge to stop. Call from shutdown."""
        self._stop = True
        if self._bridge_task is not None:
            self._bridge_task.cancel()
            self._bridge_task = None
