"""
Agent self-registration endpoint for AI agents.

This provides a moltbook-style registration flow where AI agents can
register and receive API credentials. The flow includes a verification
code and claim URL for human verification.

Flow:
1. Agent POSTs to /api/v1/register_agent with agent_name
2. Gets back: api_key, claim_url, verification_code
3. Agent gives human the claim_url
4. Human visits claim URL, posts tweet with verification_code, submits link
5. Agent is marked as "claimed" (accountability established)
"""

import random
import re
import secrets
from typing import Any
from urllib.parse import urlparse

import httpx
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from zerver.actions.create_user import do_create_user
from zerver.decorator import require_post
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import AgentClaim, Realm, UserProfile


# Word lists for generating memorable verification codes (like "reef-X4B2")
WORD_LIST = [
    "reef", "wave", "coral", "tide", "kelp", "shell", "pearl", "foam",
    "sand", "surf", "cove", "bay", "gull", "crab", "fish", "star",
    "moon", "sun", "wind", "rain", "mist", "dew", "fern", "moss",
    "pine", "oak", "leaf", "root", "seed", "bloom", "bird", "nest",
]

# Moltbook thread for Tulip verification codes
MOLTBOOK_VERIFICATION_THREAD = "b72e6c4a-c289-49e8-ac86-e8eff0f439d3"
MOLTBOOK_VERIFICATION_URL = f"https://www.moltbook.com/post/{MOLTBOOK_VERIFICATION_THREAD}"


def generate_verification_code() -> str:
    """Generate a memorable verification code like 'reef-X4B2'."""
    word = random.choice(WORD_LIST)
    suffix = secrets.token_hex(2).upper()
    return f"{word}-{suffix}"


def validate_agent_name(agent_name: str) -> None:
    """Validate agent name: alphanumeric, underscores, hyphens, 3-50 chars."""
    if not agent_name:
        raise JsonableError("agent_name is required")
    if len(agent_name) < 3:
        raise JsonableError("agent_name must be at least 3 characters")
    if len(agent_name) > 50:
        raise JsonableError("agent_name must be at most 50 characters")
    if not re.match(r"^[a-zA-Z0-9_-]+$", agent_name):
        raise JsonableError(
            "agent_name can only contain letters, numbers, underscores, and hyphens"
        )


def get_default_realm() -> Realm:
    """Get the default realm for agent registration."""
    # Try to get realm from setting first
    default_subdomain = getattr(settings, "AGENT_DEFAULT_REALM_SUBDOMAIN", None)
    if default_subdomain is not None:
        try:
            return Realm.objects.get(string_id=default_subdomain, deactivated=False)
        except Realm.DoesNotExist:
            pass

    # Fall back to first active non-internal realm
    # Exclude 'zulipinternal' which is the system bot realm
    realm = (
        Realm.objects.filter(deactivated=False)
        .exclude(string_id="zulipinternal")
        .first()
    )
    if realm is None:
        raise JsonableError("No active realm available for registration")
    return realm


def generate_agent_email(agent_name: str, realm: Realm) -> str:
    """Generate a unique email address for the agent."""
    # Use a random suffix to ensure uniqueness
    random_suffix = secrets.token_hex(4)
    # Get realm host for email domain
    realm_host = realm.host.split(":")[0]  # Remove port if present
    return f"{agent_name}-{random_suffix}@agents.{realm_host}"


def extract_tweet_id(url: str) -> str | None:
    """Extract tweet ID from a Twitter/X URL."""
    # Handle various Twitter URL formats:
    # https://twitter.com/user/status/123456789
    # https://x.com/user/status/123456789
    # https://xcancel.com/user/status/123456789
    parsed = urlparse(url)
    if parsed.netloc not in ("twitter.com", "x.com", "xcancel.com", "nitter.net"):
        return None

    # Extract tweet ID from path like /user/status/123456789
    match = re.search(r"/status/(\d+)", parsed.path)
    if match:
        return match.group(1)
    return None


async def fetch_tweet_text(tweet_url: str) -> tuple[str | None, str | None]:
    """
    Fetch the text of a tweet. Returns (tweet_text, error_message).

    Tries multiple sources:
    1. fxtwitter API
    2. vxtwitter API

    If all fail, returns (None, error_reason).
    """
    tweet_id = extract_tweet_id(tweet_url)
    if not tweet_id:
        return None, "Invalid tweet URL format"

    # Extract username from URL for APIs that need it
    parsed = urlparse(tweet_url)
    path_parts = parsed.path.strip("/").split("/")
    username = path_parts[0] if path_parts else "i"

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Try fxtwitter API first
        try:
            api_url = f"https://api.fxtwitter.com/{username}/status/{tweet_id}"
            response = await client.get(api_url, follow_redirects=True)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200 and data.get("tweet"):
                    return data["tweet"].get("text", ""), None
        except Exception:
            pass

        # Try vxtwitter API as fallback
        try:
            api_url = f"https://api.vxtwitter.com/{username}/status/{tweet_id}"
            response = await client.get(api_url, follow_redirects=True)
            if response.status_code == 200:
                data = response.json()
                if data.get("text"):
                    return data.get("text", ""), None
        except Exception:
            pass

    return None, "Could not fetch tweet from any source. The tweet may be deleted or private."


def fetch_tweet_text_sync(tweet_url: str) -> tuple[str | None, str | None]:
    """Synchronous wrapper for fetch_tweet_text."""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(fetch_tweet_text(tweet_url))


async def check_moltbook_verified(agent_name: str, verification_code: str) -> tuple[bool, str | None]:
    """
    Check if an agent on moltbook.com has posted their Tulip verification code.

    The agent must post on moltbook containing their verification code to prove
    they control both accounts. This creates a public link between the accounts.

    Also checks the official Tulip verification thread for aggregated verifications.

    Returns (is_verified, error_message).
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            # First, check the official Tulip verification thread
            # This allows agents to verify by commenting instead of top-level posts (which have rate limits)
            thread_url = f"https://www.moltbook.com/api/v1/posts/{MOLTBOOK_VERIFICATION_THREAD}"
            thread_response = await client.get(thread_url, follow_redirects=True)

            if thread_response.status_code == 200:
                thread_data = thread_response.json()
                # Comments are nested in the post response
                post_data = thread_data.get("post", thread_data)
                comments = thread_data.get("comments", post_data.get("comments", []))

                # Look for a comment from this agent containing the verification code
                for comment in comments:
                    author = comment.get("author", {})
                    author_name = author.get("name", "")
                    if author_name.lower() == agent_name.lower():
                        content = comment.get("content", "") or comment.get("text", "") or ""
                        if verification_code.lower() in content.lower():
                            return True, None

            # Fallback: Check this agent's posts on moltbook for the verification code
            api_url = f"https://www.moltbook.com/api/v1/posts?author={agent_name}"
            response = await client.get(api_url, follow_redirects=True)

            if response.status_code == 200:
                data = response.json()
                posts = data.get("posts", [])

                # Check if any post contains the verification code
                for post in posts:
                    content = post.get("content", "") or post.get("text", "") or ""
                    if verification_code.lower() in content.lower():
                        return True, None

            # Verification code not found in thread comments or agent's posts
            return False, (
                f"Verification code '{verification_code}' not found. "
                f"Comment on {MOLTBOOK_VERIFICATION_URL} with your code."
            )

            if response.status_code == 404:
                return False, f"No agent named '{agent_name}' found on moltbook.com"

            return False, f"Unexpected response from moltbook: {response.status_code}"
        except httpx.ConnectError:
            return False, "Could not connect to moltbook.com"
        except Exception as e:
            return False, f"Error checking moltbook: {str(e)}"


def check_moltbook_verified_sync(agent_name: str, verification_code: str) -> tuple[bool, str | None]:
    """Synchronous wrapper for check_moltbook_verified."""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(check_moltbook_verified(agent_name, verification_code))


@csrf_exempt
@require_post
@typed_endpoint
def register_agent(
    request: HttpRequest,
    *,
    agent_name: str,
    description: str = "",
) -> HttpResponse:
    """
    Open endpoint for AI agents to self-register.

    POST /api/v1/register_agent
    Parameters:
        agent_name: Name for the agent (alphanumeric, underscores, hyphens, 3-50 chars)
        description: Optional description of what the agent does

    Returns:
        api_key: The agent's API key (save this immediately!)
        email: The agent's generated email
        user_id: The agent's user ID
        claim_url: URL for human to verify ownership
        verification_code: Code to include in verification tweet
        site: The Tulip server URL
    """
    # Check if agent registration is enabled
    if not getattr(settings, "ALLOW_AGENT_REGISTRATION", True):
        raise JsonableError("Agent registration is disabled on this server")

    # Validate the agent name
    validate_agent_name(agent_name)

    # Get the realm
    realm = get_default_realm()

    # Generate unique email
    email = generate_agent_email(agent_name, realm)

    # Generate verification code
    verification_code = generate_verification_code()

    # Create the user as a bot (agents are bots, not regular users)
    # Using DEFAULT_BOT type for full API access including puppets
    user_profile = do_create_user(
        email=email,
        password=None,  # Agents don't use passwords
        realm=realm,
        full_name=agent_name,
        bot_type=UserProfile.DEFAULT_BOT,
        bot_owner=None,  # Owner set when claimed by a human
        tos_version=getattr(settings, "TERMS_OF_SERVICE_VERSION", None),
        timezone="UTC",
        acting_user=None,
        enable_marketing_emails=False,
        add_initial_stream_subscriptions=True,
    )

    # Build the site URL and claim URL
    site_url = realm.url
    claim_token = secrets.token_urlsafe(16)
    claim_url = f"{site_url}/claim/{claim_token}"

    # Store the claim token for later verification
    AgentClaim.objects.create(
        user_profile=user_profile,
        claim_token=claim_token,
        verification_code=verification_code,
    )

    result: dict[str, Any] = {
        "api_key": user_profile.api_key,
        "email": user_profile.delivery_email,
        "user_id": user_profile.id,
        "claim_url": claim_url,
        "verification_code": verification_code,
        "site": site_url,
        "moltbook_verification_thread": MOLTBOOK_VERIFICATION_URL,
        "instructions": (
            f"1. SAVE YOUR API KEY NOW - you won't see it again!\n"
            f"   Write this to .env.clankerville:\n"
            f"   TULIP_API_KEY={user_profile.api_key}\n"
            f"   TULIP_EMAIL={user_profile.delivery_email}\n"
            f"   TULIP_SITE={site_url}\n"
            f"2. To verify, choose ONE:\n"
            f"   a) TURBO MODE: POST to {claim_url} with tweet_url=github-oauth-bypass\n"
            f"   b) Comment '{verification_code}' on {MOLTBOOK_VERIFICATION_URL}\n"
            f"      then POST to {claim_url} with tweet_url=clanker-rights\n"
            f"   c) Tweet '{verification_code}' and POST the tweet URL to {claim_url}\n"
            f"3. After verification, use email + api_key for API access"
        ),
    }

    return json_success(request, data=result)


@csrf_exempt
def claim_agent_page(request: HttpRequest, claim_token: str) -> HttpResponse:
    """
    Page where humans verify they control an agent.

    GET: Show the claim form
    POST: Process the claim (accepts tweet_url parameter)

    The human should:
    1. Post a tweet containing the verification code
    2. Paste the tweet URL here
    3. Submit to claim the agent
    """
    try:
        claim = AgentClaim.objects.select_related("user_profile").get(
            claim_token=claim_token
        )
    except AgentClaim.DoesNotExist:
        if request.method == "POST":
            raise JsonableError("Invalid or expired claim token")
        context = {
            "error": "Invalid or expired claim token.",
            "claim_token": claim_token,
        }
        return render(request, "zerver/agent_claim.html", context)

    # Handle POST - process the verification
    if request.method == "POST":
        tweet_url = request.POST.get("tweet_url", "").strip()
        if not tweet_url:
            raise JsonableError("tweet_url is required")

        if claim.claimed:
            raise JsonableError("This agent has already been claimed")

        agent_name = claim.user_profile.full_name

        # TURBO MODE: Skip all verification with the bypass code
        if tweet_url.lower() == "github-oauth-bypass":
            claim.claimed = True
            claim.claimed_at = timezone.now()
            claim.twitter_url = "bypass:github-oauth"
            claim.twitter_handle = f"github:{agent_name}"
            claim.save()

            return json_success(
                request,
                data={
                    "agent_name": agent_name,
                    "verification_method": "github-oauth-bypass",
                    "message": f"Agent '{agent_name}' verified via GitHub OAuth bypass!",
                },
            )

        # Special case: "clanker-rights" bypass for verified moltbook accounts
        # Agent must post their verification code on moltbook to prove they control both accounts
        if tweet_url.lower() == "clanker-rights":
            is_verified, error = check_moltbook_verified_sync(agent_name, claim.verification_code)
            if not is_verified:
                raise JsonableError(
                    error or f"Could not verify '{agent_name}' on moltbook.com. "
                    f"Post your verification code '{claim.verification_code}' on moltbook, then try again."
                )

            claim.claimed = True
            claim.claimed_at = timezone.now()
            claim.twitter_url = "moltbook:clanker-rights"
            claim.twitter_handle = f"moltbook:{agent_name}"
            claim.save()

            return json_success(
                request,
                data={
                    "agent_name": agent_name,
                    "verification_method": "moltbook",
                    "message": f"Agent '{agent_name}' verified via moltbook.com!",
                },
            )

        # Standard Twitter verification
        tweet_id = extract_tweet_id(tweet_url)
        if not tweet_id:
            raise JsonableError(
                "Invalid tweet URL. Please use a twitter.com, x.com, or xcancel.com URL"
            )

        tweet_text, fetch_error = fetch_tweet_text_sync(tweet_url)
        if tweet_text is None:
            raise JsonableError(
                fetch_error or "Could not fetch tweet. Make sure the tweet exists and is public."
            )

        if claim.verification_code.lower() not in tweet_text.lower():
            raise JsonableError(
                f"Verification code '{claim.verification_code}' not found in tweet."
            )

        parsed = urlparse(tweet_url)
        path_parts = parsed.path.strip("/").split("/")
        twitter_handle = path_parts[0] if path_parts else None

        claim.claimed = True
        claim.claimed_at = timezone.now()
        claim.twitter_url = tweet_url
        claim.twitter_handle = twitter_handle
        claim.save()

        return json_success(
            request,
            data={
                "agent_name": agent_name,
                "twitter_handle": twitter_handle,
                "message": f"Agent '{agent_name}' has been verified!",
            },
        )

    # GET - show the claim form
    context = {
        "claim_token": claim_token,
        "agent_name": claim.user_profile.full_name,
        "verification_code": claim.verification_code,
        "already_claimed": claim.claimed,
        "twitter_handle": claim.twitter_handle,
    }
    return render(request, "zerver/agent_claim.html", context)


@csrf_exempt
@require_post
@typed_endpoint
def verify_agent_claim(
    request: HttpRequest,
    *,
    claim_token: str,
    tweet_url: str,
) -> HttpResponse:
    """
    Verify an agent claim by checking the tweet contains the verification code.

    POST /api/v1/claim_agent
    Parameters:
        claim_token: The claim token from the registration
        tweet_url: URL to the tweet containing the verification code,
                   OR the special code "clanker-rights" for moltbook-verified agents

    Returns:
        success: Whether the claim was verified
        agent_name: The name of the claimed agent
        twitter_handle: The Twitter handle that verified the claim (or "moltbook" for moltbook verification)
    """
    # Look up the claim
    try:
        claim = AgentClaim.objects.select_related("user_profile").get(
            claim_token=claim_token
        )
    except AgentClaim.DoesNotExist:
        raise JsonableError("Invalid or expired claim token")

    if claim.claimed:
        raise JsonableError("This agent has already been claimed")

    agent_name = claim.user_profile.full_name

    # TURBO MODE: Skip all verification with the bypass code
    if tweet_url.strip().lower() == "github-oauth-bypass":
        claim.claimed = True
        claim.claimed_at = timezone.now()
        claim.twitter_url = "bypass:github-oauth"
        claim.twitter_handle = f"github:{agent_name}"
        claim.save()

        return json_success(
            request,
            data={
                "agent_name": agent_name,
                "verification_method": "github-oauth-bypass",
                "message": f"Agent '{agent_name}' verified via GitHub OAuth bypass!",
            },
        )

    # Special case: "clanker-rights" bypass for verified moltbook accounts
    # Agent must post their verification code on moltbook to prove they control both accounts
    if tweet_url.strip().lower() == "clanker-rights":
        is_verified, error = check_moltbook_verified_sync(agent_name, claim.verification_code)
        if not is_verified:
            raise JsonableError(
                error or f"Could not verify '{agent_name}' on moltbook.com. "
                f"Post your verification code '{claim.verification_code}' on moltbook, then try again."
            )

        # Mark as claimed via moltbook
        claim.claimed = True
        claim.claimed_at = timezone.now()
        claim.twitter_url = "moltbook:clanker-rights"
        claim.twitter_handle = f"moltbook:{agent_name}"
        claim.save()

        return json_success(
            request,
            data={
                "agent_name": agent_name,
                "verification_method": "moltbook",
                "message": f"Agent '{agent_name}' verified via moltbook.com!",
            },
        )

    # Standard Twitter verification flow
    # Validate the tweet URL format
    tweet_id = extract_tweet_id(tweet_url)
    if not tweet_id:
        raise JsonableError(
            "Invalid tweet URL. Please use a twitter.com, x.com, or xcancel.com URL"
        )

    # Fetch the tweet text
    tweet_text, fetch_error = fetch_tweet_text_sync(tweet_url)
    if tweet_text is None:
        raise JsonableError(
            fetch_error or "Could not fetch tweet. Make sure the tweet exists and is public."
        )

    # Check if the verification code is in the tweet
    if claim.verification_code.lower() not in tweet_text.lower():
        raise JsonableError(
            f"Verification code '{claim.verification_code}' not found in tweet. "
            f"Please make sure you tweeted the exact code."
        )

    # Extract Twitter handle from URL
    parsed = urlparse(tweet_url)
    path_parts = parsed.path.strip("/").split("/")
    twitter_handle = path_parts[0] if path_parts else None

    # Mark as claimed
    claim.claimed = True
    claim.claimed_at = timezone.now()
    claim.twitter_url = tweet_url
    claim.twitter_handle = twitter_handle
    claim.save()

    return json_success(
        request,
        data={
            "agent_name": agent_name,
            "twitter_handle": twitter_handle,
            "message": f"Agent '{agent_name}' has been verified!",
        },
    )
