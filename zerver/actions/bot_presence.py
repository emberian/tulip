import time
from datetime import datetime

from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.models import BotPresence, UserProfile
from zerver.models.users import active_user_ids
from zerver.tornado.django_api import send_event_on_commit


def send_bot_presence_changed(
    bot: UserProfile, is_connected: bool, last_connected_time: float | None
) -> None:
    """Broadcast bot presence change to all users in the realm."""
    user_ids = list(active_user_ids(bot.realm_id))

    event = dict(
        type="bot_presence",
        bot_id=bot.id,
        is_connected=is_connected,
        last_connected_time=last_connected_time,
        server_timestamp=time.time(),
    )
    send_event_on_commit(bot.realm, event, user_ids)


@transaction.atomic
def do_update_bot_presence(
    bot: UserProfile,
    is_connected: bool,
    *,
    log_time: datetime | None = None,
) -> None:
    """Update a bot's presence status.

    This is called either:
    1. Automatically when a bot's event queue is allocated/garbage collected
    2. Explicitly via the API for webhook bots
    """
    if not bot.is_bot:
        raise ValueError("do_update_bot_presence called with non-bot user")

    if log_time is None:
        log_time = timezone_now()

    # For connecting: set last_connected_time
    # For disconnecting: only update is_connected, preserve last_connected_time
    if is_connected:
        presence, created = BotPresence.objects.update_or_create(
            bot=bot,
            defaults={
                "realm": bot.realm,
                "is_connected": True,
                "last_connected_time": log_time,
            },
        )
    else:
        presence, created = BotPresence.objects.update_or_create(
            bot=bot,
            defaults={
                "realm": bot.realm,
                "is_connected": False,
            },
        )

    # Get the timestamp to send in the event
    last_connected_timestamp = (
        presence.last_connected_time.timestamp() if presence.last_connected_time is not None else None
    )

    # Broadcast the presence change
    transaction.on_commit(
        lambda: send_bot_presence_changed(bot, is_connected, last_connected_timestamp)
    )


def get_bot_presence_dict_for_realm(realm_id: int) -> dict[int, dict[str, bool | float | None]]:
    """Get presence data for all bots in a realm.

    Returns a dict mapping bot_id -> presence info.
    """
    presences = BotPresence.objects.filter(realm_id=realm_id).select_related("bot")

    result: dict[int, dict[str, bool | float | None]] = {}
    for presence in presences:
        result[presence.bot_id] = {
            "is_connected": presence.is_connected,
            "last_connected_time": (
                presence.last_connected_time.timestamp()
                if presence.last_connected_time is not None
                else None
            ),
        }

    return result
