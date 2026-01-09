from datetime import timedelta
from unittest import mock
from unittest.mock import patch

from django.utils.timezone import now as timezone_now

from zerver.actions.bot_presence import (
    do_update_bot_presence,
    get_bot_presence_dict_for_realm,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import BotPresence


class BotPresenceTests(ZulipTestCase):
    def test_do_update_bot_presence_connect(self) -> None:
        """Test that connecting a bot creates/updates presence with correct timestamp."""
        bot = self.example_user("default_bot")
        BotPresence.objects.filter(bot=bot).delete()

        # Connect the bot
        log_time = timezone_now()
        do_update_bot_presence(bot, is_connected=True, log_time=log_time)

        presence = BotPresence.objects.get(bot=bot)
        self.assertTrue(presence.is_connected)
        self.assertEqual(presence.last_connected_time, log_time)
        self.assertEqual(presence.realm_id, bot.realm_id)

    def test_do_update_bot_presence_disconnect_preserves_timestamp(self) -> None:
        """Test that disconnecting a bot preserves last_connected_time."""
        bot = self.example_user("default_bot")
        BotPresence.objects.filter(bot=bot).delete()

        # First connect
        connect_time = timezone_now()
        do_update_bot_presence(bot, is_connected=True, log_time=connect_time)

        # Then disconnect - should preserve timestamp
        disconnect_time = connect_time + timedelta(hours=1)
        do_update_bot_presence(bot, is_connected=False, log_time=disconnect_time)

        presence = BotPresence.objects.get(bot=bot)
        self.assertFalse(presence.is_connected)
        # last_connected_time should still be the original connect time
        self.assertEqual(presence.last_connected_time, connect_time)

    def test_do_update_bot_presence_reconnect_updates_timestamp(self) -> None:
        """Test that reconnecting updates last_connected_time."""
        bot = self.example_user("default_bot")
        BotPresence.objects.filter(bot=bot).delete()

        # First connect
        first_connect_time = timezone_now()
        do_update_bot_presence(bot, is_connected=True, log_time=first_connect_time)

        # Disconnect
        do_update_bot_presence(bot, is_connected=False)

        # Reconnect with new timestamp
        second_connect_time = first_connect_time + timedelta(hours=2)
        do_update_bot_presence(bot, is_connected=True, log_time=second_connect_time)

        presence = BotPresence.objects.get(bot=bot)
        self.assertTrue(presence.is_connected)
        self.assertEqual(presence.last_connected_time, second_connect_time)

    def test_do_update_bot_presence_non_bot_raises(self) -> None:
        """Test that calling with non-bot user raises ValueError."""
        user = self.example_user("hamlet")
        self.assertFalse(user.is_bot)

        with self.assertRaises(ValueError) as cm:
            do_update_bot_presence(user, is_connected=True)

        self.assertIn("non-bot user", str(cm.exception))

    def test_get_bot_presence_dict_for_realm(self) -> None:
        """Test getting all bot presences for a realm."""
        bot1 = self.example_user("default_bot")
        bot2 = self.example_user("webhook_bot")
        BotPresence.objects.filter(realm=bot1.realm).delete()

        # Connect both bots
        time1 = timezone_now()
        time2 = time1 + timedelta(minutes=5)
        do_update_bot_presence(bot1, is_connected=True, log_time=time1)
        do_update_bot_presence(bot2, is_connected=True, log_time=time2)

        # Disconnect bot1
        do_update_bot_presence(bot1, is_connected=False)

        result = get_bot_presence_dict_for_realm(bot1.realm_id)

        self.assertEqual(len(result), 2)

        self.assertFalse(result[bot1.id]["is_connected"])
        bot1_last_connected = result[bot1.id]["last_connected_time"]
        assert isinstance(bot1_last_connected, float)
        self.assertAlmostEqual(bot1_last_connected, time1.timestamp(), delta=1.0)

        self.assertTrue(result[bot2.id]["is_connected"])
        bot2_last_connected = result[bot2.id]["last_connected_time"]
        assert isinstance(bot2_last_connected, float)
        self.assertAlmostEqual(bot2_last_connected, time2.timestamp(), delta=1.0)

    def test_get_bot_presence_dict_empty_realm(self) -> None:
        """Test getting bot presences when none exist."""
        bot = self.example_user("default_bot")
        BotPresence.objects.filter(realm=bot.realm).delete()

        result = get_bot_presence_dict_for_realm(bot.realm_id)
        self.assertEqual(result, {})


class BotPresenceAPITests(ZulipTestCase):
    def test_update_bot_presence_api(self) -> None:
        """Test the bot presence API endpoint."""
        bot = self.example_user("default_bot")
        BotPresence.objects.filter(bot=bot).delete()

        # Set bot as connected
        result = self.api_post(
            bot,
            "/api/v1/bots/me/presence",
            {"is_connected": "true"},
        )
        self.assert_json_success(result)

        presence = BotPresence.objects.get(bot=bot)
        self.assertTrue(presence.is_connected)

    def test_update_bot_presence_api_disconnect(self) -> None:
        """Test disconnecting via API."""
        bot = self.example_user("default_bot")
        BotPresence.objects.filter(bot=bot).delete()

        # First connect
        self.api_post(bot, "/api/v1/bots/me/presence", {"is_connected": "true"})

        # Then disconnect
        result = self.api_post(
            bot,
            "/api/v1/bots/me/presence",
            {"is_connected": "false"},
        )
        self.assert_json_success(result)

        presence = BotPresence.objects.get(bot=bot)
        self.assertFalse(presence.is_connected)

    def test_update_bot_presence_api_non_bot_rejected(self) -> None:
        """Test that non-bots cannot use the bot presence endpoint."""
        user = self.example_user("hamlet")
        self.assertFalse(user.is_bot)

        result = self.api_post(
            user,
            "/api/v1/bots/me/presence",
            {"is_connected": "true"},
        )
        self.assert_json_error(result, "This endpoint is only for bots.")


class BotPresenceEventTests(ZulipTestCase):
    """Tests for bot presence events.

    Uses mock-based event capture to verify events are sent correctly without
    requiring OpenAPI schema documentation (which is still being finalized).
    """

    def test_do_update_bot_presence_broadcasts_event(self) -> None:
        """Test that updating bot presence broadcasts an event."""
        bot = self.example_user("default_bot")
        BotPresence.objects.filter(bot=bot).delete()

        with patch(
            "zerver.actions.bot_presence.send_bot_presence_changed"
        ) as mock_send_presence:
            # captureOnCommitCallbacks ensures on_commit callbacks run during test
            with self.captureOnCommitCallbacks(execute=True):
                do_update_bot_presence(bot, is_connected=True)

            # The function is called via transaction.on_commit, verify the arguments
            mock_send_presence.assert_called_once()
            call_args = mock_send_presence.call_args
            called_bot = call_args[0][0]
            called_is_connected = call_args[0][1]
            called_last_connected_time = call_args[0][2]

            self.assertEqual(called_bot.id, bot.id)
            self.assertTrue(called_is_connected)
            self.assertIsNotNone(called_last_connected_time)

    def test_do_update_bot_presence_event_includes_timestamp(self) -> None:
        """Test that disconnect event includes the preserved timestamp."""
        bot = self.example_user("default_bot")
        BotPresence.objects.filter(bot=bot).delete()

        # First connect
        connect_time = timezone_now()
        with self.captureOnCommitCallbacks(execute=True):
            do_update_bot_presence(bot, is_connected=True, log_time=connect_time)

        # Disconnect and verify the callback gets the correct timestamp
        with patch(
            "zerver.actions.bot_presence.send_bot_presence_changed"
        ) as mock_send_presence:
            with self.captureOnCommitCallbacks(execute=True):
                do_update_bot_presence(bot, is_connected=False)

            mock_send_presence.assert_called_once()
            call_args = mock_send_presence.call_args
            called_is_connected = call_args[0][1]
            called_last_connected_time = call_args[0][2]

            self.assertFalse(called_is_connected)
            # Should include the connect time, not None
            self.assertIsNotNone(called_last_connected_time)
            self.assertAlmostEqual(
                called_last_connected_time, connect_time.timestamp(), delta=1.0
            )

    def test_update_bot_presence_api_broadcasts_event(self) -> None:
        """Test that the API broadcasts an event."""
        bot = self.example_user("default_bot")
        BotPresence.objects.filter(bot=bot).delete()

        with patch(
            "zerver.actions.bot_presence.send_bot_presence_changed"
        ) as mock_send_presence:
            with self.captureOnCommitCallbacks(execute=True):
                self.api_post(
                    bot,
                    "/api/v1/bots/me/presence",
                    {"is_connected": "true"},
                )

            mock_send_presence.assert_called_once()
            call_args = mock_send_presence.call_args
            called_bot = call_args[0][0]
            called_is_connected = call_args[0][1]

            self.assertEqual(called_bot.id, bot.id)
            self.assertTrue(called_is_connected)
