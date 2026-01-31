from datetime import timedelta

from django.utils.timezone import now as timezone_now

from zerver.models import Stream, UserProfile
from zerver.models.streams import PuppetHandler, StreamPuppet


def _normalize_hex_color(color: str | None) -> str | None:
    """Normalize 3-digit hex colors to 6-digit format."""
    if color is None:
        return None
    if len(color) == 4:  # #RGB
        return f"#{color[1]}{color[1]}{color[2]}{color[2]}{color[3]}{color[3]}"
    return color


def register_stream_puppet(
    stream: Stream,
    puppet_name: str,
    puppet_avatar_url: str | None,
    sender: UserProfile,
    puppet_color: str | None = None,
) -> StreamPuppet:
    """Register or update a puppet name in a stream.

    Called when a puppet message is sent to track the puppet name for
    @-mentions and conversation participants. Also registers the sender
    as a handler for this puppet (for receiving whispers).
    """
    # Normalize color to 6-digit hex format
    normalized_color = _normalize_hex_color(puppet_color)

    puppet, created = StreamPuppet.objects.update_or_create(
        stream=stream,
        name=puppet_name,
        defaults={
            "avatar_url": puppet_avatar_url,
            "color": normalized_color,
            "last_used": timezone_now(),
            "created_by": sender,
        },
    )
    if not created:
        # Update last_used, avatar, and color even if puppet already exists
        puppet.last_used = timezone_now()
        update_fields = ["last_used"]
        if puppet_avatar_url:
            puppet.avatar_url = puppet_avatar_url
            update_fields.append("avatar_url")
        if normalized_color is not None:
            puppet.color = normalized_color
            update_fields.append("color")
        puppet.save(update_fields=update_fields)

    # Register sender as a handler for this puppet (auto-updates last_used)
    PuppetHandler.objects.update_or_create(
        puppet=puppet,
        handler=sender,
        defaults={
            "handler_type": PuppetHandler.HANDLER_TYPE_RECENT,
            "last_used": timezone_now(),
        },
    )

    return puppet


def get_stream_puppets(stream: Stream) -> list[dict[str, str | int | None]]:
    """Get all puppet names registered in a stream for autocomplete."""
    puppets = StreamPuppet.objects.filter(stream=stream).order_by("-last_used")
    return [
        {
            "id": puppet.id,
            "name": puppet.name,
            "avatar_url": puppet.avatar_url,
            "color": puppet.color,
        }
        for puppet in puppets
    ]


def get_puppet_handler_user_ids(puppet_ids: list[int], stream: Stream) -> set[int]:
    """Resolve puppet IDs to the user IDs that should receive whispers.

    For 'claimed' puppets: returns only explicitly claimed handlers.
    For 'open' puppets: returns handlers used within the recency window.
    """
    if not puppet_ids:
        return set()

    user_ids: set[int] = set()
    now = timezone_now()

    puppets = StreamPuppet.objects.filter(
        id__in=puppet_ids,
        stream=stream,
    ).prefetch_related("handlers")

    for puppet in puppets:
        if puppet.visibility_mode == StreamPuppet.VISIBILITY_CLAIMED:
            # Only include explicitly claimed handlers (and active users)
            handler_ids = puppet.handlers.filter(
                handler_type=PuppetHandler.HANDLER_TYPE_CLAIMED,
                handler__is_active=True,
            ).values_list("handler_id", flat=True)
            user_ids.update(handler_ids)
        else:
            # Open mode: include all handlers used within the time window (and active users)
            cutoff = now - timedelta(hours=puppet.recent_handler_window_hours)
            handler_ids = puppet.handlers.filter(
                last_used__gte=cutoff,
                handler__is_active=True,
            ).values_list("handler_id", flat=True)
            user_ids.update(handler_ids)

    return user_ids


def get_user_handled_puppet_ids(user: UserProfile, stream: Stream) -> list[int]:
    """Get puppet IDs that a user currently handles in a stream.

    Returns puppets where the user is either:
    - A claimed handler (regardless of recency)
    - A recent handler (within the puppet's recency window) for open puppets
    """
    now = timezone_now()
    puppet_ids: list[int] = []

    handlers = PuppetHandler.objects.filter(
        handler=user,
        puppet__stream=stream,
    ).select_related("puppet")

    for handler in handlers:
        puppet = handler.puppet
        if handler.handler_type == PuppetHandler.HANDLER_TYPE_CLAIMED:
            # Claimed handlers always count
            puppet_ids.append(puppet.id)
        elif puppet.visibility_mode == StreamPuppet.VISIBILITY_OPEN:
            # For open puppets, check recency window
            cutoff = now - timedelta(hours=puppet.recent_handler_window_hours)
            if handler.last_used >= cutoff:
                puppet_ids.append(puppet.id)

    return puppet_ids


def get_all_user_handled_puppet_ids(user: UserProfile) -> list[int]:
    """Get all puppet IDs that a user currently handles across all streams.

    Used for whisper visibility filtering in narrow queries where stream
    context is not available.

    TODO:FUTUREWORK: This function is called for every narrow query that
    needs to filter whispers by visibility. For users who handle many puppets
    across multiple streams, this could add latency. Consider caching the
    result (e.g., in memcached with a short TTL, invalidated when puppet
    handlers change) or pre-computing and storing handled puppet IDs on the
    UserProfile model for heavy users.
    """
    now = timezone_now()
    puppet_ids: list[int] = []

    handlers = PuppetHandler.objects.filter(handler=user).select_related("puppet")

    for handler in handlers:
        puppet = handler.puppet
        if handler.handler_type == PuppetHandler.HANDLER_TYPE_CLAIMED:
            # Claimed handlers always count
            puppet_ids.append(puppet.id)
        elif puppet.visibility_mode == StreamPuppet.VISIBILITY_OPEN:
            # For open puppets, check recency window
            cutoff = now - timedelta(hours=puppet.recent_handler_window_hours)
            if handler.last_used >= cutoff:
                puppet_ids.append(puppet.id)

    return puppet_ids


def claim_puppet(
    puppet: StreamPuppet,
    user: UserProfile,
) -> PuppetHandler:
    """Explicitly claim a puppet for receiving whispers."""
    handler, created = PuppetHandler.objects.update_or_create(
        puppet=puppet,
        handler=user,
        defaults={
            "handler_type": PuppetHandler.HANDLER_TYPE_CLAIMED,
            "last_used": timezone_now(),
        },
    )
    # If already existed as 'recent', upgrade to 'claimed'
    if not created and handler.handler_type != PuppetHandler.HANDLER_TYPE_CLAIMED:
        handler.handler_type = PuppetHandler.HANDLER_TYPE_CLAIMED
        handler.save(update_fields=["handler_type"])
    return handler


def unclaim_puppet(
    puppet: StreamPuppet,
    user: UserProfile,
) -> bool:
    """Remove a claimed handler from a puppet. Returns True if deleted."""
    deleted, _ = PuppetHandler.objects.filter(
        puppet=puppet,
        handler=user,
        handler_type=PuppetHandler.HANDLER_TYPE_CLAIMED,
    ).delete()
    return deleted > 0


def set_puppet_visibility(
    puppet: StreamPuppet,
    visibility_mode: str,
    recent_handler_window_hours: int | None = None,
) -> None:
    """Set the visibility mode for a puppet."""
    puppet.visibility_mode = visibility_mode
    if recent_handler_window_hours is not None:
        puppet.recent_handler_window_hours = recent_handler_window_hours
    puppet.save(update_fields=["visibility_mode", "recent_handler_window_hours"])


def cleanup_stale_handlers(dry_run: bool = False) -> int:
    """Remove stale 'recent' handlers whose time window has expired.

    For 'open' puppets, handlers are considered stale when their last_used
    timestamp is older than the puppet's recent_handler_window_hours.

    Claimed handlers are never cleaned up - they persist until explicitly removed.

    Args:
        dry_run: If True, only count stale handlers without deleting them.

    Returns:
        The number of stale handlers deleted (or that would be deleted if dry_run).
    """
    now = timezone_now()
    stale_count = 0

    # Get all 'recent' handlers for 'open' puppets
    handlers = PuppetHandler.objects.filter(
        handler_type=PuppetHandler.HANDLER_TYPE_RECENT,
        puppet__visibility_mode=StreamPuppet.VISIBILITY_OPEN,
    ).select_related("puppet")

    handlers_to_delete = []
    for handler in handlers:
        puppet = handler.puppet
        cutoff = now - timedelta(hours=puppet.recent_handler_window_hours)
        if handler.last_used < cutoff:
            handlers_to_delete.append(handler.id)
            stale_count += 1

    if not dry_run and handlers_to_delete:
        PuppetHandler.objects.filter(id__in=handlers_to_delete).delete()

    return stale_count
