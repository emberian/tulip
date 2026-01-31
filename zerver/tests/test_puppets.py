import orjson

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message, Stream
from zerver.models.streams import PuppetHandler, StreamPuppet


class PuppetMessageTest(ZulipTestCase):
    """Tests for sending messages with puppet identities."""

    def test_send_puppet_message_to_puppet_enabled_stream(self) -> None:
        """Sending a puppet message to a puppet-enabled stream should succeed."""
        user = self.example_user("hamlet")
        self.login_user(user)
        stream = self.subscribe(user, "RPG")

        # Enable puppet mode on the stream
        stream.enable_puppet_mode = True
        stream.save()

        result = self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "to": orjson.dumps("RPG").decode(),
                "topic": "adventure",
                "content": "Hello, I am the wizard!",
                "puppet_display_name": "Gandalf",
                "puppet_avatar_url": "https://example.com/gandalf.png",
            },
        )
        self.assert_json_success(result)

        # Verify the message has puppet fields
        message = Message.objects.latest("id")
        self.assertEqual(message.puppet_display_name, "Gandalf")
        self.assertEqual(message.puppet_avatar_url, "https://example.com/gandalf.png")

    def test_puppet_message_api_response_shows_puppet_name(self) -> None:
        """API response should show puppet name as sender_full_name."""
        user = self.example_user("hamlet")
        self.login_user(user)
        stream = self.subscribe(user, "RPG")

        # Enable puppet mode on the stream
        stream.enable_puppet_mode = True
        stream.save()

        # Send a puppet message
        result = self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "to": orjson.dumps("RPG").decode(),
                "topic": "adventure",
                "content": "Hello, I am the wizard!",
                "puppet_display_name": "Gandalf",
                "puppet_avatar_url": "https://example.com/gandalf.png",
            },
        )
        self.assert_json_success(result)
        message_id = self.assert_json_success(result)["id"]

        # Fetch the message via API and verify sender_full_name is the puppet name
        result = self.client_get(
            "/json/messages",
            {
                "narrow": orjson.dumps([{"operator": "id", "operand": message_id}]).decode(),
                "anchor": message_id,
                "num_before": 0,
                "num_after": 0,
            },
        )
        data = self.assert_json_success(result)
        messages = data["messages"]
        self.assertEqual(len(messages), 1)

        msg = messages[0]
        # The sender_full_name should be the puppet name, not the actual user's name
        self.assertEqual(msg["sender_full_name"], "Gandalf")
        # The avatar_url should be the puppet avatar
        self.assertEqual(msg["avatar_url"], "https://example.com/gandalf.png")
        # But sender_id should still be the actual user's ID
        self.assertEqual(msg["sender_id"], user.id)

    def test_puppet_message_event_shows_puppet_name(self) -> None:
        """Real-time message event should show puppet name as sender_full_name."""
        user = self.example_user("hamlet")
        othello = self.example_user("othello")
        self.login_user(user)
        stream = self.subscribe(user, "RPG")
        self.subscribe(othello, "RPG")

        # Enable puppet mode on the stream
        stream.enable_puppet_mode = True
        stream.save()

        # Capture events for othello when message is sent
        with self.capture_send_event_calls(expected_num_events=1) as events:
            self.client_post(
                "/json/messages",
                {
                    "type": "stream",
                    "to": orjson.dumps("RPG").decode(),
                    "topic": "adventure",
                    "content": "Hello, I am the wizard!",
                    "puppet_display_name": "Gandalf",
                    "puppet_avatar_url": "https://example.com/gandalf.png",
                },
            )

        # Check the message event
        event = events[0]["event"]
        self.assertEqual(event["type"], "message")
        msg = event["message"]
        # The sender_full_name in the event should be the puppet name
        self.assertEqual(msg["sender_full_name"], "Gandalf")
        # The avatar_url should be the puppet avatar
        self.assertEqual(msg["avatar_url"], "https://example.com/gandalf.png")

    def test_send_puppet_message_to_non_puppet_stream(self) -> None:
        """Sending a puppet message to a non-puppet stream should fail."""
        user = self.example_user("hamlet")
        self.login_user(user)
        self.subscribe(user, "Denmark")

        result = self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "to": orjson.dumps("Denmark").decode(),
                "topic": "test",
                "content": "Hello",
                "puppet_display_name": "Character",
            },
        )
        self.assert_json_error(result, "Puppet mode is not enabled for this channel")

    def test_send_puppet_message_to_dm(self) -> None:
        """Sending a puppet message to a DM should fail."""
        user = self.example_user("hamlet")
        self.login_user(user)
        othello = self.example_user("othello")

        result = self.client_post(
            "/json/messages",
            {
                "type": "private",
                "to": orjson.dumps([othello.email]).decode(),
                "content": "Hello",
                "puppet_display_name": "Character",
            },
        )
        self.assert_json_error(result, "Puppet messages are only allowed in channels")

    def test_puppet_message_without_avatar(self) -> None:
        """Puppet messages should work without an avatar URL."""
        user = self.example_user("hamlet")
        self.login_user(user)
        stream = self.subscribe(user, "RPG")
        stream.enable_puppet_mode = True
        stream.save()

        result = self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "to": orjson.dumps("RPG").decode(),
                "topic": "adventure",
                "content": "Hello!",
                "puppet_display_name": "Frodo",
            },
        )
        self.assert_json_success(result)

        message = Message.objects.latest("id")
        self.assertEqual(message.puppet_display_name, "Frodo")
        self.assertIsNone(message.puppet_avatar_url)


class StreamPuppetRegistrationTest(ZulipTestCase):
    """Tests for automatic puppet registration when messages are sent."""

    def test_puppet_auto_registered_on_message_send(self) -> None:
        """Puppets should be automatically registered when a puppet message is sent."""
        user = self.example_user("hamlet")
        self.login_user(user)
        stream = self.subscribe(user, "RPG")
        stream.enable_puppet_mode = True
        stream.save()

        # Initially no puppets
        self.assertEqual(StreamPuppet.objects.filter(stream=stream).count(), 0)

        self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "to": orjson.dumps("RPG").decode(),
                "topic": "adventure",
                "content": "Hello!",
                "puppet_display_name": "Gandalf",
                "puppet_avatar_url": "https://example.com/gandalf.png",
            },
        )

        # Puppet should be registered
        puppets = StreamPuppet.objects.filter(stream=stream)
        self.assertEqual(puppets.count(), 1)
        puppet = puppets.first()
        assert puppet is not None
        self.assertEqual(puppet.name, "Gandalf")
        self.assertEqual(puppet.avatar_url, "https://example.com/gandalf.png")
        self.assertEqual(puppet.created_by, user)

    def test_puppet_not_duplicated(self) -> None:
        """Sending multiple messages with the same puppet name should not create duplicates."""
        user = self.example_user("hamlet")
        self.login_user(user)
        stream = self.subscribe(user, "RPG")
        stream.enable_puppet_mode = True
        stream.save()

        # Send two messages with the same puppet
        for _ in range(2):
            self.client_post(
                "/json/messages",
                {
                    "type": "stream",
                    "to": orjson.dumps("RPG").decode(),
                    "topic": "adventure",
                    "content": "Hello!",
                    "puppet_display_name": "Gandalf",
                },
            )

        # Should still be only one puppet
        self.assertEqual(StreamPuppet.objects.filter(stream=stream).count(), 1)

    def test_puppet_avatar_updated(self) -> None:
        """Puppet avatar should be updated when a new avatar is provided."""
        user = self.example_user("hamlet")
        self.login_user(user)
        stream = self.subscribe(user, "RPG")
        stream.enable_puppet_mode = True
        stream.save()

        # First message with avatar
        self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "to": orjson.dumps("RPG").decode(),
                "topic": "adventure",
                "content": "Hello!",
                "puppet_display_name": "Gandalf",
                "puppet_avatar_url": "https://example.com/old.png",
            },
        )

        # Second message with new avatar
        self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "to": orjson.dumps("RPG").decode(),
                "topic": "adventure",
                "content": "Hello again!",
                "puppet_display_name": "Gandalf",
                "puppet_avatar_url": "https://example.com/new.png",
            },
        )

        puppet = StreamPuppet.objects.get(stream=stream, name="Gandalf")
        self.assertEqual(puppet.avatar_url, "https://example.com/new.png")


class StreamPuppetsAPITest(ZulipTestCase):
    """Tests for the /streams/{id}/puppets API endpoint."""

    def test_get_stream_puppets(self) -> None:
        """Getting puppets for a puppet-enabled stream should return the puppet list."""
        user = self.example_user("hamlet")
        self.login_user(user)
        stream = self.subscribe(user, "RPG")
        stream.enable_puppet_mode = True
        stream.save()

        # Create some puppets
        StreamPuppet.objects.create(
            stream=stream,
            name="Gandalf",
            avatar_url="https://example.com/gandalf.png",
            created_by=user,
        )
        StreamPuppet.objects.create(
            stream=stream,
            name="Frodo",
            created_by=user,
        )

        result = self.client_get(f"/json/streams/{stream.id}/puppets")
        data = self.assert_json_success(result)
        puppets = data["puppets"]
        self.assertEqual(len(puppets), 2)

        puppet_names = {p["name"] for p in puppets}
        self.assertEqual(puppet_names, {"Gandalf", "Frodo"})

    def test_get_puppets_non_puppet_stream(self) -> None:
        """Getting puppets for a non-puppet stream should fail."""
        user = self.example_user("hamlet")
        self.login_user(user)
        stream = self.subscribe(user, "Denmark")

        result = self.client_get(f"/json/streams/{stream.id}/puppets")
        self.assert_json_error(result, "Puppet mode is not enabled for this channel")


class PuppetMentionTest(ZulipTestCase):
    """Tests for puppet mention rendering."""

    def test_puppet_mention_rendered(self) -> None:
        """@**PuppetName** should render as a puppet mention in puppet-enabled streams."""
        user = self.example_user("hamlet")
        self.login_user(user)
        stream = self.subscribe(user, "RPG")
        stream.enable_puppet_mode = True
        stream.save()

        # Create a puppet
        StreamPuppet.objects.create(
            stream=stream,
            name="Gandalf",
            created_by=user,
        )

        # Send a message mentioning the puppet
        result = self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "to": orjson.dumps("RPG").decode(),
                "topic": "adventure",
                "content": "Hello @**Gandalf**!",
            },
        )
        self.assert_json_success(result)

        message = Message.objects.latest("id")
        assert message.rendered_content is not None
        self.assertIn('class="puppet-mention"', message.rendered_content)
        self.assertIn('data-puppet-name="Gandalf"', message.rendered_content)

    def test_puppet_mention_not_rendered_in_non_puppet_stream(self) -> None:
        """@**Name** should not render as puppet mention in non-puppet streams."""
        user = self.example_user("hamlet")
        self.login_user(user)
        stream = self.subscribe(user, "Denmark")

        result = self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "to": orjson.dumps("Denmark").decode(),
                "topic": "test",
                "content": "Hello @**Gandalf**!",
            },
        )
        self.assert_json_success(result)

        message = Message.objects.latest("id")
        # Should not have puppet-mention class
        assert message.rendered_content is not None
        self.assertNotIn("puppet-mention", message.rendered_content)

    def test_silent_puppet_mention(self) -> None:
        """@_**PuppetName** should render as a silent puppet mention."""
        user = self.example_user("hamlet")
        self.login_user(user)
        stream = self.subscribe(user, "RPG")
        stream.enable_puppet_mode = True
        stream.save()

        StreamPuppet.objects.create(
            stream=stream,
            name="Gandalf",
            created_by=user,
        )

        result = self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "to": orjson.dumps("RPG").decode(),
                "topic": "adventure",
                "content": "Hello @_**Gandalf**!",
            },
        )
        self.assert_json_success(result)

        message = Message.objects.latest("id")
        assert message.rendered_content is not None
        self.assertIn('class="puppet-mention silent"', message.rendered_content)


class PuppetValidationTest(ZulipTestCase):
    """Tests for puppet message validation."""

    def test_puppet_avatar_url_must_be_https(self) -> None:
        """Puppet avatar URL must use https."""
        user = self.example_user("hamlet")
        self.login_user(user)
        stream = self.subscribe(user, "RPG")
        stream.enable_puppet_mode = True
        stream.save()

        # HTTP URL should be rejected
        result = self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "to": orjson.dumps("RPG").decode(),
                "topic": "adventure",
                "content": "Hello!",
                "puppet_display_name": "Gandalf",
                "puppet_avatar_url": "http://example.com/gandalf.png",
            },
        )
        self.assert_json_error_contains(result, "puppet_avatar_url")

        # HTTPS URL should work
        result = self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "to": orjson.dumps("RPG").decode(),
                "topic": "adventure",
                "content": "Hello!",
                "puppet_display_name": "Gandalf",
                "puppet_avatar_url": "https://example.com/gandalf.png",
            },
        )
        self.assert_json_success(result)

    def test_puppet_color_validation(self) -> None:
        """Puppet color must be valid hex format."""
        user = self.example_user("hamlet")
        self.login_user(user)
        stream = self.subscribe(user, "RPG")
        stream.enable_puppet_mode = True
        stream.save()

        # Invalid color should be rejected
        result = self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "to": orjson.dumps("RPG").decode(),
                "topic": "adventure",
                "content": "Hello!",
                "puppet_display_name": "Gandalf",
                "puppet_color": "red",
            },
        )
        self.assert_json_error_contains(result, "puppet_color")

        # Valid 6-digit hex should work
        result = self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "to": orjson.dumps("RPG").decode(),
                "topic": "adventure",
                "content": "Hello!",
                "puppet_display_name": "Gandalf",
                "puppet_color": "#FF5733",
            },
        )
        self.assert_json_success(result)

    def test_puppet_color_normalization(self) -> None:
        """3-digit hex colors should be normalized to 6-digit."""
        user = self.example_user("hamlet")
        self.login_user(user)
        stream = self.subscribe(user, "RPG")
        stream.enable_puppet_mode = True
        stream.save()

        # Send message with 3-digit hex color
        result = self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "to": orjson.dumps("RPG").decode(),
                "topic": "adventure",
                "content": "Hello!",
                "puppet_display_name": "Gandalf",
                "puppet_color": "#F00",
            },
        )
        self.assert_json_success(result)

        # Verify color was normalized
        puppet = StreamPuppet.objects.get(stream=stream, name="Gandalf")
        self.assertEqual(puppet.color, "#FF0000")

    def test_puppet_display_name_max_length(self) -> None:
        """Puppet display name cannot exceed 100 characters."""
        user = self.example_user("hamlet")
        self.login_user(user)
        stream = self.subscribe(user, "RPG")
        stream.enable_puppet_mode = True
        stream.save()

        # Name too long should be rejected
        result = self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "to": orjson.dumps("RPG").decode(),
                "topic": "adventure",
                "content": "Hello!",
                "puppet_display_name": "A" * 101,
            },
        )
        self.assert_json_error_contains(result, "puppet_display_name")


class PuppetHandlerFilteringTest(ZulipTestCase):
    """Tests for filtering deactivated users from puppet handlers."""

    def test_deactivated_user_excluded_from_handlers(self) -> None:
        """Deactivated users should not appear in handler listings."""
        from zerver.actions.stream_puppets import get_puppet_handler_user_ids
        from zerver.actions.users import do_deactivate_user

        user = self.example_user("hamlet")
        other_user = self.example_user("cordelia")
        stream = self.subscribe(user, "RPG")
        stream.enable_puppet_mode = True
        stream.save()

        # Create a puppet and add handlers
        puppet = StreamPuppet.objects.create(
            stream=stream,
            name="Gandalf",
            created_by=user,
        )
        PuppetHandler.objects.create(
            puppet=puppet,
            handler=user,
            handler_type=PuppetHandler.HANDLER_TYPE_CLAIMED,
        )
        PuppetHandler.objects.create(
            puppet=puppet,
            handler=other_user,
            handler_type=PuppetHandler.HANDLER_TYPE_CLAIMED,
        )

        # Both users should be returned initially
        handler_ids = get_puppet_handler_user_ids([puppet.id], stream)
        self.assertIn(user.id, handler_ids)
        self.assertIn(other_user.id, handler_ids)

        # Deactivate one user
        do_deactivate_user(other_user, acting_user=None)

        # Now only the active user should be returned
        handler_ids = get_puppet_handler_user_ids([puppet.id], stream)
        self.assertIn(user.id, handler_ids)
        self.assertNotIn(other_user.id, handler_ids)
