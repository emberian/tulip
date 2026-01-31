"""
Models for AI agent registration and verification.
"""

from django.db import models

from zerver.models.users import UserProfile


class AgentClaim(models.Model):
    """
    Tracks agent claim tokens for human verification.

    When an AI agent registers, it receives a claim_token and verification_code.
    The human must tweet the verification code, then submit the tweet URL here.
    """

    user_profile = models.OneToOneField(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="agent_claim",
    )
    claim_token = models.CharField(max_length=64, unique=True, db_index=True)
    verification_code = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    # Filled in when claimed
    claimed = models.BooleanField(default=False)
    claimed_at = models.DateTimeField(null=True, blank=True)
    twitter_url = models.URLField(max_length=500, null=True, blank=True)
    twitter_handle = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["claim_token"]),
            models.Index(fields=["claimed"]),
        ]

    def __str__(self) -> str:
        status = "claimed" if self.claimed else "pending"
        return f"AgentClaim({self.user_profile.full_name}, {status})"
