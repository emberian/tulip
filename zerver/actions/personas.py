from typing import Any

from django.db import transaction
from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError, ResourceNotFoundError
from zerver.models import UserProfile
from zerver.models.personas import UserPersona
from zerver.tornado.django_api import send_event_on_commit


def do_get_personas(user_profile: UserProfile) -> list[dict[str, Any]]:
    """Get all active personas for a user."""
    personas = UserPersona.objects.filter(user=user_profile, is_active=True)
    return [persona.to_api_dict() for persona in personas]


def do_get_persona_by_id(persona_id: int, user_profile: UserProfile) -> UserPersona:
    """Get a specific persona, verifying ownership."""
    try:
        return UserPersona.objects.get(id=persona_id, user=user_profile)
    except UserPersona.DoesNotExist:
        raise ResourceNotFoundError(_("Persona does not exist."))


@transaction.atomic(durable=True)
def do_create_persona(
    user_profile: UserProfile,
    name: str,
    avatar_url: str | None = None,
    color: str | None = None,
    bio: str = "",
) -> UserPersona:
    """Create a new persona for a user."""
    # Check persona limit (0 = unlimited)
    max_personas = user_profile.realm.max_personas_per_user
    if max_personas > 0:
        current_count = UserPersona.objects.filter(user=user_profile, is_active=True).count()
        if current_count >= max_personas:
            raise JsonableError(
                _("You have reached the maximum number of personas ({limit}).").format(
                    limit=max_personas
                )
            )

    # Check for duplicate name
    if UserPersona.objects.filter(user=user_profile, name=name).exists():
        raise JsonableError(_("You already have a persona with this name."))

    persona = UserPersona.objects.create(
        user=user_profile,
        name=name,
        avatar_url=avatar_url,
        color=color,
        bio=bio,
    )

    event = {
        "type": "user_persona",
        "op": "add",
        "persona": persona.to_api_dict(),
    }
    send_event_on_commit(user_profile.realm, event, [user_profile.id])

    return persona


def do_update_persona(
    persona_id: int,
    user_profile: UserProfile,
    name: str | None = None,
    avatar_url: str | None = None,
    color: str | None = None,
    bio: str | None = None,
) -> UserPersona:
    """Update an existing persona."""
    persona = do_get_persona_by_id(persona_id, user_profile)

    if name is not None and name != persona.name:
        # Check for duplicate name
        if UserPersona.objects.filter(user=user_profile, name=name).exclude(id=persona_id).exists():
            raise JsonableError(_("You already have a persona with this name."))
        persona.name = name

    if avatar_url is not None:
        persona.avatar_url = avatar_url if avatar_url else None
    if color is not None:
        persona.color = color if color else None
    if bio is not None:
        persona.bio = bio

    with transaction.atomic(durable=True):
        persona.save()

        event = {
            "type": "user_persona",
            "op": "update",
            "persona": persona.to_api_dict(),
        }
        send_event_on_commit(user_profile.realm, event, [user_profile.id])

    return persona


def do_delete_persona(
    persona_id: int,
    user_profile: UserProfile,
) -> None:
    """Soft-delete a persona (mark as inactive)."""
    persona = do_get_persona_by_id(persona_id, user_profile)

    with transaction.atomic(durable=True):
        persona.is_active = False
        persona.save(update_fields=["is_active"])

        event = {
            "type": "user_persona",
            "op": "remove",
            "persona_id": persona_id,
        }
        send_event_on_commit(user_profile.realm, event, [user_profile.id])
