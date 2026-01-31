from typing import Annotated

from django.http import HttpRequest, HttpResponse
from pydantic import StringConstraints

from zerver.actions.personas import (
    do_create_persona,
    do_delete_persona,
    do_get_personas,
    do_update_persona,
)
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.models import UserProfile
from zerver.models.personas import UserPersona


def normalize_hex_color(color: str | None) -> str | None:
    """Normalize 3-digit hex colors to 6-digit format."""
    if color is None:
        return None
    if len(color) == 4:  # #RGB
        # Expand #RGB to #RRGGBB
        return f"#{color[1]}{color[1]}{color[2]}{color[2]}{color[3]}{color[3]}"
    return color


def get_personas(
    request: HttpRequest,
    user_profile: UserProfile,
) -> HttpResponse:
    """List all active personas for the current user."""
    return json_success(request, data={"personas": do_get_personas(user_profile)})


@typed_endpoint
def create_persona(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    name: Annotated[
        str,
        StringConstraints(
            min_length=1, max_length=UserPersona.MAX_NAME_LENGTH, strip_whitespace=True
        ),
    ],
    avatar_url: Annotated[
        str | None,
        StringConstraints(max_length=500, pattern=r"^https://[^\s]+$"),
    ] = None,
    color: Annotated[
        str | None,
        StringConstraints(pattern=r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"),
    ] = None,
    bio: Annotated[
        str,
        StringConstraints(max_length=UserPersona.MAX_BIO_LENGTH),
    ] = "",
) -> HttpResponse:
    """Create a new persona."""
    # Normalize color to 6-digit hex
    normalized_color = normalize_hex_color(color)

    persona = do_create_persona(
        user_profile=user_profile,
        name=name.strip(),
        avatar_url=avatar_url,
        color=normalized_color,
        bio=bio.strip(),
    )
    return json_success(request, data={"persona": persona.to_api_dict()})


@typed_endpoint
def update_persona(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    persona_id: PathOnly[int],
    name: Annotated[
        str | None,
        StringConstraints(
            min_length=1, max_length=UserPersona.MAX_NAME_LENGTH, strip_whitespace=True
        ),
    ] = None,
    avatar_url: Annotated[
        str | None,
        StringConstraints(max_length=500, pattern=r"^(|https://[^\s]+)$"),
    ] = None,
    color: Annotated[
        str | None,
        StringConstraints(pattern=r"^(|#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}))$"),
    ] = None,
    bio: Annotated[
        str | None,
        StringConstraints(max_length=UserPersona.MAX_BIO_LENGTH),
    ] = None,
) -> HttpResponse:
    """Update an existing persona."""
    if name is None and avatar_url is None and color is None and bio is None:
        # No changes requested
        return json_success(request)

    # Normalize color to 6-digit hex (or None if empty)
    normalized_color = normalize_hex_color(color) if color else color

    persona = do_update_persona(
        persona_id=persona_id,
        user_profile=user_profile,
        name=name.strip() if name else None,
        avatar_url=avatar_url,
        color=normalized_color,
        bio=bio.strip() if bio else None,
    )
    return json_success(request, data={"persona": persona.to_api_dict()})


def delete_persona(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    persona_id: int,
) -> HttpResponse:
    """Soft-delete a persona."""
    do_delete_persona(persona_id, user_profile)
    return json_success(request)


def get_realm_personas(
    request: HttpRequest,
    user_profile: UserProfile,
) -> HttpResponse:
    """Get active personas in the realm for @-mention typeahead.

    Limited to 200 most recently created personas to prevent
    performance issues in large realms.
    """
    personas = (
        UserPersona.objects.filter(
            user__realm=user_profile.realm,
            user__is_active=True,
            is_active=True,
        )
        .select_related("user")
        .order_by("-created_at")[:200]
    )

    return json_success(
        request,
        data={
            "personas": [
                {
                    "id": p.id,
                    "name": p.name,
                    "avatar_url": p.avatar_url,
                    "color": p.color,
                    "user_id": p.user_id,
                    "user_full_name": p.user.full_name,
                }
                for p in personas
            ]
        },
    )
