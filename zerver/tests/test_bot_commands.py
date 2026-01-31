from typing import TYPE_CHECKING

import orjson

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import BotCommand, UserProfile

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class BotCommandsTestCase(ZulipTestCase):
    def test_list_bot_commands(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        # Initially no commands
        result = self.client_get("/json/bot_commands")
        self.assert_json_success(result)
        data = orjson.loads(result.content)
        self.assertEqual(data["commands"], [])

        # Create a bot and register a command
        bot = self.create_test_bot("test", user, bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)
        BotCommand.objects.create(
            bot_profile=bot,
            realm=user.realm,
            name="weather",
            description="Get weather info",
            options_schema=[],
        )

        # Now should see the command
        result = self.client_get("/json/bot_commands")
        self.assert_json_success(result)
        data = orjson.loads(result.content)
        self.assertEqual(len(data["commands"]), 1)
        self.assertEqual(data["commands"][0]["name"], "weather")
        self.assertEqual(data["commands"][0]["description"], "Get weather info")

    def test_register_bot_command(self) -> None:
        user = self.example_user("hamlet")
        bot = self.create_test_bot("test", user, bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)

        # Bot can register a command (use API auth since bots can't login)
        result = self.api_post(
            bot,
            "/api/v1/bot_commands",
            {
                "name": "weather",
                "description": "Get weather info",
            },
        )
        self.assert_json_success(result)
        data = orjson.loads(result.content)
        self.assertEqual(data["name"], "weather")
        self.assertTrue(data["created"])

        # Verify it was created
        command = BotCommand.objects.get(realm=user.realm, name="weather")
        self.assertEqual(command.bot_profile, bot)
        self.assertEqual(command.description, "Get weather info")

    def test_register_bot_command_non_bot_fails(self) -> None:
        user = self.example_user("hamlet")

        result = self.api_post(
            user,
            "/api/v1/bot_commands",
            {
                "name": "weather",
                "description": "Get weather info",
            },
        )
        self.assert_json_error(result, "Only bots can register commands")

    def test_register_bot_command_updates_existing(self) -> None:
        user = self.example_user("hamlet")
        bot = self.create_test_bot("test", user, bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)

        # First registration
        result = self.api_post(
            bot,
            "/api/v1/bot_commands",
            {
                "name": "weather",
                "description": "Get weather info",
            },
        )
        self.assert_json_success(result)
        data = orjson.loads(result.content)
        self.assertTrue(data["created"])

        # Update the command
        result = self.api_post(
            bot,
            "/api/v1/bot_commands",
            {
                "name": "weather",
                "description": "Get updated weather info",
            },
        )
        self.assert_json_success(result)
        data = orjson.loads(result.content)
        self.assertFalse(data["created"])

        # Verify it was updated
        command = BotCommand.objects.get(realm=user.realm, name="weather")
        self.assertEqual(command.description, "Get updated weather info")

    def test_delete_bot_command(self) -> None:
        user = self.example_user("hamlet")
        bot = self.create_test_bot("test", user, bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)

        command = BotCommand.objects.create(
            bot_profile=bot,
            realm=user.realm,
            name="weather",
            description="Get weather info",
            options_schema=[],
        )

        # Bot can delete its own command (use API auth)
        result = self.api_delete(bot, f"/api/v1/bot_commands/{command.id}")
        self.assert_json_success(result)

        # Verify it was deleted
        self.assertFalse(BotCommand.objects.filter(id=command.id).exists())

    def test_delete_bot_command_admin(self) -> None:
        user = self.example_user("hamlet")
        admin = self.example_user("iago")
        bot = self.create_test_bot("test", user, bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)

        command = BotCommand.objects.create(
            bot_profile=bot,
            realm=user.realm,
            name="weather",
            description="Get weather info",
            options_schema=[],
        )

        # Admin can delete any command
        result = self.api_delete(admin, f"/api/v1/bot_commands/{command.id}")
        self.assert_json_success(result)

        # Verify it was deleted
        self.assertFalse(BotCommand.objects.filter(id=command.id).exists())

    def test_delete_bot_command_permission_denied(self) -> None:
        user = self.example_user("hamlet")
        other_user = self.example_user("cordelia")
        bot = self.create_test_bot("test", user, bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)

        command = BotCommand.objects.create(
            bot_profile=bot,
            realm=user.realm,
            name="weather",
            description="Get weather info",
            options_schema=[],
        )

        # Non-admin, non-owner cannot delete
        result = self.api_delete(other_user, f"/api/v1/bot_commands/{command.id}")
        self.assert_json_error(result, "Permission denied")

        # Verify it still exists
        self.assertTrue(BotCommand.objects.filter(id=command.id).exists())

    def test_delete_bot_command_not_found(self) -> None:
        user = self.example_user("hamlet")

        result = self.api_delete(user, "/api/v1/bot_commands/99999")
        self.assert_json_error(result, "Command not found")

    def test_register_command_prevents_takeover(self) -> None:
        """Another bot cannot overwrite an existing command from a different bot."""
        user = self.example_user("hamlet")
        bot1 = self.create_test_bot(
            "weatherbot", user, full_name="Weather Bot", bot_type=UserProfile.OUTGOING_WEBHOOK_BOT
        )
        bot2 = self.create_test_bot(
            "gamebot", user, full_name="Game Bot", bot_type=UserProfile.OUTGOING_WEBHOOK_BOT
        )

        # Bot1 registers the command
        result = self.api_post(
            bot1,
            "/api/v1/bot_commands",
            {
                "name": "weather",
                "description": "Get weather info",
            },
        )
        self.assert_json_success(result)

        # Bot2 tries to register the same command name - should fail
        result = self.api_post(
            bot2,
            "/api/v1/bot_commands",
            {
                "name": "weather",
                "description": "My weather command",
            },
        )
        self.assert_json_error(result, "Command '/weather' is already registered by another bot")

        # Verify bot1 still owns the command
        command = BotCommand.objects.get(realm=user.realm, name="weather")
        self.assertEqual(command.bot_profile, bot1)
        self.assertEqual(command.description, "Get weather info")

    def test_register_command_name_validation(self) -> None:
        """Command names must follow the required format."""
        user = self.example_user("hamlet")
        bot = self.create_test_bot("test", user, bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)

        # Invalid: starts with number
        result = self.api_post(
            bot,
            "/api/v1/bot_commands",
            {"name": "1weather", "description": "Test"},
        )
        self.assert_json_error_contains(result, "Invalid command name")

        # Invalid: contains spaces
        result = self.api_post(
            bot,
            "/api/v1/bot_commands",
            {"name": "my weather", "description": "Test"},
        )
        self.assert_json_error_contains(result, "Invalid command name")

        # Invalid: uppercase
        result = self.api_post(
            bot,
            "/api/v1/bot_commands",
            {"name": "Weather", "description": "Test"},
        )
        self.assert_json_error_contains(result, "Invalid command name")

        # Invalid: too long (over 32 chars)
        result = self.api_post(
            bot,
            "/api/v1/bot_commands",
            {"name": "a" * 33, "description": "Test"},
        )
        self.assert_json_error_contains(result, "Invalid command name")

        # Valid: lowercase with hyphens and underscores
        result = self.api_post(
            bot,
            "/api/v1/bot_commands",
            {"name": "my-weather_cmd", "description": "Test"},
        )
        self.assert_json_success(result)

    def test_register_command_options_schema_validation(self) -> None:
        """Options schema must have valid structure."""
        user = self.example_user("hamlet")
        bot = self.create_test_bot("test", user, bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)

        # Invalid: option missing name
        result = self.api_post(
            bot,
            "/api/v1/bot_commands",
            {
                "name": "weather",
                "description": "Test",
                "options": orjson.dumps([{"type": "string"}]).decode(),
            },
        )
        self.assert_json_error_contains(result, "must have a 'name' string")

        # Invalid: option missing type
        result = self.api_post(
            bot,
            "/api/v1/bot_commands",
            {
                "name": "weather2",
                "description": "Test",
                "options": orjson.dumps([{"name": "location"}]).decode(),
            },
        )
        self.assert_json_error_contains(result, "must have a valid 'type'")

        # Invalid: invalid option type
        result = self.api_post(
            bot,
            "/api/v1/bot_commands",
            {
                "name": "weather3",
                "description": "Test",
                "options": orjson.dumps([{"name": "location", "type": "invalid"}]).decode(),
            },
        )
        self.assert_json_error_contains(result, "must have a valid 'type'")

        # Invalid: duplicate option name
        result = self.api_post(
            bot,
            "/api/v1/bot_commands",
            {
                "name": "weather4",
                "description": "Test",
                "options": orjson.dumps([
                    {"name": "location", "type": "string"},
                    {"name": "location", "type": "integer"},
                ]).decode(),
            },
        )
        self.assert_json_error_contains(result, "Duplicate option name")

        # Valid schema
        result = self.api_post(
            bot,
            "/api/v1/bot_commands",
            {
                "name": "weather5",
                "description": "Test",
                "options": orjson.dumps([
                    {"name": "location", "type": "string", "description": "City name"},
                    {"name": "units", "type": "string", "choices": ["celsius", "fahrenheit"]},
                ]).decode(),
            },
        )
        self.assert_json_success(result)
