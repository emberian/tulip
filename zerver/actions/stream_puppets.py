from django.utils.timezone import now as timezone_now

from zerver.models import Stream, UserProfile
from zerver.models.streams import StreamPuppet


def register_stream_puppet(
    stream: Stream,
    puppet_name: str,
    puppet_avatar_url: str | None,
    sender: UserProfile,
    puppet_color: str | None = None,
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
            "color": puppet_color,
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
        if puppet_color is not None:
            puppet.color = puppet_color
            update_fields.append("color")
        puppet.save(update_fields=update_fields)
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
