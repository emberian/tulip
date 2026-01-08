from django.utils.timezone import now as timezone_now

from zerver.models import Stream, UserProfile
from zerver.models.streams import StreamPuppet


def register_stream_puppet(
    stream: Stream,
    puppet_name: str,
    puppet_avatar_url: str | None,
    sender: UserProfile,
) -> StreamPuppet:
    """Register or update a puppet name in a stream.

    Called when a puppet message is sent to track the puppet name for
    @-mentions and conversation participants.
    """
    puppet, created = StreamPuppet.objects.update_or_create(
        stream=stream,
        name=puppet_name,
        defaults={
            "avatar_url": puppet_avatar_url,
            "last_used": timezone_now(),
            "created_by": sender,
        },
    )
    if not created:
        # Update last_used and avatar even if puppet already exists
        puppet.last_used = timezone_now()
        if puppet_avatar_url:
            puppet.avatar_url = puppet_avatar_url
        puppet.save(update_fields=["last_used", "avatar_url"])
    return puppet


def get_stream_puppets(stream: Stream) -> list[dict[str, str | int | None]]:
    """Get all puppet names registered in a stream for autocomplete."""
    puppets = StreamPuppet.objects.filter(stream=stream).order_by("-last_used")
    return [
        {
            "id": puppet.id,
            "name": puppet.name,
            "avatar_url": puppet.avatar_url,
        }
        for puppet in puppets
    ]
