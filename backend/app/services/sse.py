"""
Shared in-memory pub/sub for Server-Sent Events.

Keeps the alert listener list in a single authoritative place so
`scoring.py` can publish and `dashboard.py` can subscribe without
creating a circular import.
"""
import asyncio

# All active SSE client queues. Populated by the /alerts/live endpoint,
# drained by broadcast_alert().
alert_listeners: list[asyncio.Queue] = []


async def broadcast_alert(alert_data: dict) -> None:
    """
    Publish *alert_data* to every connected SSE client.
    Removes stale queues on failure.
    """
    stale: list[asyncio.Queue] = []
    for q in alert_listeners:
        try:
            await q.put(alert_data)
        except Exception:
            stale.append(q)

    for q in stale:
        if q in alert_listeners:
            alert_listeners.remove(q)
