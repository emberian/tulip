# Tulip API Reference

This document provides a complete reference for all API endpoints and parameters added or modified in the Tulip fork.

## Table of Contents

1. [Messages API](#messages-api)
   - [Send Message](#send-message)
2. [Personas API](#personas-api)
   - [List Personas](#list-personas)
   - [Create Persona](#create-persona)
   - [Update Persona](#update-persona)
   - [Delete Persona](#delete-persona)
   - [Get Realm Personas](#get-realm-personas)
3. [Bot Commands API](#bot-commands-api)
   - [List Commands](#list-commands)
   - [Register Command](#register-command)
   - [Delete Command](#delete-command)
   - [Get Autocomplete](#get-autocomplete)
   - [Invoke Command](#invoke-command)
3. [Bot Interactions API](#bot-interactions-api)
   - [Handle Interaction](#handle-interaction)
4. [Bot Presence API](#bot-presence-api)
   - [Update Presence](#update-presence)
5. [Streams API](#streams-api)
   - [Get Stream Puppets](#get-stream-puppets)
6. [User Settings API](#user-settings-api)
   - [Update User Color](#update-user-color)
7. [User Groups API](#user-groups-api)
   - [Update Group Color](#update-group-color)
8. [Webhook Payloads](#webhook-payloads)
   - [Interaction Webhook](#interaction-webhook)
   - [Autocomplete Webhook](#autocomplete-webhook)
   - [Command Invocation Webhook](#command-invocation-webhook)
9. [Events](#events)

---

## Messages API

### Send Message

**POST** `/api/v1/messages`

Extended with new parameters for whispers and puppeting.

#### New Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `whisper_to_user_ids` | array[int] | No | User IDs who can see this whisper (channel messages only) |
| `whisper_to_group_ids` | array[int] | No | Group IDs whose members can see this whisper |
| `whisper_to_puppet_ids` | array[int] | No | Puppet IDs whose handlers can see this whisper |
| `puppet_display_name` | string | No | Display name for puppet message (max 100 chars) |
| `puppet_avatar_url` | string | No | Avatar URL for puppet message |
| `puppet_color` | string | No | Hex color for puppet name (#RGB or #RRGGBB) |
| `persona_id` | int | No | ID of the persona to send message as |
| `widget_content` | string (JSON) | No | Widget definition for interactive messages |

#### Whisper Example

```bash
curl -X POST https://tulip.example.com/api/v1/messages \
  -u bot@example.com:API_KEY \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'type=stream' \
  -d 'to=general' \
  -d 'topic=Updates' \
  -d 'content=This is a secret message' \
  -d 'whisper_to_user_ids=[10, 11]' \
  -d 'whisper_to_group_ids=[20]'
```

#### Puppet Example

```bash
curl -X POST https://tulip.example.com/api/v1/messages \
  -u bot@example.com:API_KEY \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'type=stream' \
  -d 'to=game-chat' \
  -d 'topic=Adventure' \
  -d 'content=Hello, traveler!' \
  -d 'puppet_display_name=Mysterious NPC' \
  -d 'puppet_avatar_url=https://example.com/npc.png' \
  -d 'puppet_color=#8e44ad'
```

#### Widget Example

```bash
curl -X POST https://tulip.example.com/api/v1/messages \
  -u bot@example.com:API_KEY \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'type=stream' \
  -d 'to=general' \
  -d 'topic=Approvals' \
  -d 'content=Please review:' \
  --data-urlencode 'widget_content={"widget_type":"interactive","extra_data":{"content":"Approve request?","components":[{"type":"action_row","components":[{"type":"button","label":"Approve","style":"success","custom_id":"approve_123"}]}]}}'
```

#### Response

```json
{
  "result": "success",
  "id": 12345,
  "msg": ""
}
```

#### Message Object (in events/fetches)

Messages may include these new fields:

```json
{
  "id": 12345,
  "content": "...",
  "whisper_recipients": {
    "user_ids": [10, 11],
    "group_ids": [20],
    "puppet_ids": [42]
  },
  "puppet_display_name": "Mysterious NPC",
  "puppet_avatar_url": "https://example.com/npc.png",
  "puppet_color": "#8e44ad",
  "persona_id": 42,
  "persona_display_name": "Gandalf",
  "persona_avatar_url": "https://example.com/gandalf.png",
  "persona_color": "#808080"
}
```

---

## Personas API

Personas are user-owned character identities. Unlike bot-controlled puppets, personas are portable and can be used anywhere.

### List Personas

**GET** `/json/users/me/personas`

List all active personas for the current user.

#### Response

```json
{
  "result": "success",
  "personas": [
    {
      "id": 42,
      "name": "Gandalf",
      "avatar_url": "https://example.com/gandalf.png",
      "color": "#808080",
      "bio": "A wizard is never late",
      "is_active": true,
      "date_created": 1704793200
    }
  ]
}
```

---

### Create Persona

**POST** `/json/users/me/personas`

Create a new persona.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Persona name (1-100 chars) |
| `avatar_url` | string | No | Avatar image URL (max 500 chars) |
| `color` | string | No | Hex color (#RGB or #RRGGBB) |
| `bio` | string | No | Short bio (max 500 chars) |

#### Example

```bash
curl -X POST https://tulip.example.com/json/users/me/personas \
  -u user@example.com:API_KEY \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Gandalf",
    "avatar_url": "https://example.com/gandalf.png",
    "color": "#808080",
    "bio": "A wizard is never late"
  }'
```

#### Response

```json
{
  "result": "success",
  "persona": {
    "id": 42,
    "name": "Gandalf",
    "avatar_url": "https://example.com/gandalf.png",
    "color": "#808080",
    "bio": "A wizard is never late",
    "is_active": true,
    "date_created": 1704793200
  }
}
```

#### Errors

| Error | Description |
|-------|-------------|
| 400 | "You have reached the maximum number of personas (20)." |
| 400 | "You already have a persona with this name." |

---

### Update Persona

**PATCH** `/json/users/me/personas/{persona_id}`

Update an existing persona.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | No | New persona name |
| `avatar_url` | string | No | New avatar URL (empty string to clear) |
| `color` | string | No | New hex color (empty string to clear) |
| `bio` | string | No | New bio |

#### Example

```bash
curl -X PATCH https://tulip.example.com/json/users/me/personas/42 \
  -u user@example.com:API_KEY \
  -H "Content-Type: application/json" \
  -d '{"bio": "A wizard is never late, nor is he early"}'
```

#### Response

```json
{
  "result": "success",
  "persona": {
    "id": 42,
    "name": "Gandalf",
    "avatar_url": "https://example.com/gandalf.png",
    "color": "#808080",
    "bio": "A wizard is never late, nor is he early",
    "is_active": true,
    "date_created": 1704793200
  }
}
```

---

### Delete Persona

**DELETE** `/json/users/me/personas/{persona_id}`

Soft-delete a persona (marks as inactive). Personas are soft-deleted to preserve message history.

#### Response

```json
{
  "result": "success"
}
```

---

### Get Realm Personas

**GET** `/json/realm/personas`

Get all active personas in the realm for @-mention typeahead.

#### Response

```json
{
  "result": "success",
  "personas": [
    {
      "id": 42,
      "name": "Gandalf",
      "avatar_url": "https://example.com/gandalf.png",
      "color": "#808080",
      "user_id": 123,
      "user_full_name": "Alice"
    }
  ]
}
```

---

## Bot Commands API

### List Commands

**GET** `/json/bot_commands`

List all bot commands registered in the realm.

#### Response

```json
{
  "result": "success",
  "commands": [
    {
      "id": 1,
      "name": "weather",
      "description": "Get weather forecast",
      "options": [
        {
          "name": "location",
          "type": "string",
          "description": "City name",
          "required": true
        }
      ],
      "bot_id": 123,
      "bot_name": "Weather Bot"
    }
  ]
}
```

---

### Register Command

**POST** `/json/bot_commands`

Register a new slash command. Only callable by bots.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Command name (without leading /) |
| `description` | string | Yes | Description shown in typeahead |
| `options` | array | No | Command options schema |

#### Options Schema

Each option object can have:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Option name |
| `type` | string | Yes | Data type: `string`, `number`, `boolean` |
| `description` | string | No | Help text |
| `required` | boolean | No | Whether option is required |
| `choices` | array | No | Static choices: `[{name, value}]` |

#### Example

```bash
curl -X POST https://tulip.example.com/json/bot_commands \
  -u bot@example.com:API_KEY \
  -H "Content-Type: application/json" \
  -d '{
    "name": "roll",
    "description": "Roll dice",
    "options": [
      {
        "name": "dice",
        "type": "string",
        "description": "Dice notation (e.g., 2d6)",
        "required": true
      },
      {
        "name": "modifier",
        "type": "number",
        "description": "Bonus to add"
      }
    ]
  }'
```

#### Response

```json
{
  "result": "success",
  "id": 42,
  "name": "roll",
  "created": true
}
```

---

### Delete Command

**DELETE** `/json/bot_commands/{command_id}`

Delete a registered command. Only the owning bot or realm admins can delete.

#### Response

```json
{
  "result": "success"
}
```

---

### Get Autocomplete

**GET** `/json/bot_commands/{bot_id}/autocomplete`

Fetch dynamic autocomplete suggestions for a command option.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `command_name` | string | Yes | Command being typed |
| `option_name` | string | Yes | Option needing suggestions |
| `partial_value` | string | No | Partial value user has typed |
| `context` | string (JSON) | No | Additional context (stream_id, topic, etc.) |

#### Example

```bash
curl -G https://tulip.example.com/json/bot_commands/123/autocomplete \
  -u user@example.com:API_KEY \
  -d 'command_name=inventory' \
  -d 'option_name=item' \
  -d 'partial_value=sw'
```

#### Response

```json
{
  "result": "success",
  "choices": [
    {"value": "sword_iron", "label": "Iron Sword"},
    {"value": "sword_steel", "label": "Steel Sword"}
  ]
}
```

---

### Invoke Command

**POST** `/json/bot_commands/invoke`

Invoke a bot slash command. Creates a message showing the invocation and routes to the bot.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `command_name` | string | Yes | Command name (without /) |
| `arguments` | object | No | `{option_name: value}` mapping |
| `stream_id` | int | No* | Stream ID for channel messages |
| `topic` | string | No* | Topic for channel messages |
| `to` | array[int] | No* | User IDs for direct messages |
| `idempotency_key` | string | No | Prevent duplicate submissions |

*Either (`stream_id` + `topic`) or `to` is required.

#### Example

```bash
curl -X POST https://tulip.example.com/json/bot_commands/invoke \
  -u user@example.com:API_KEY \
  -H "Content-Type: application/json" \
  -d '{
    "command_name": "weather",
    "arguments": {"location": "San Francisco", "units": "f"},
    "stream_id": 5,
    "topic": "Weather"
  }'
```

#### Response

```json
{
  "result": "success",
  "message_id": 12345,
  "interaction_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## Bot Interactions API

### Handle Interaction

**POST** `/json/bot_interactions`

Handle an interaction event from a bot widget (button click, menu selection, etc.).

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `message_id` | int | Yes | ID of message containing the widget |
| `interaction_type` | string | Yes | Type: `button_click`, `select_menu`, `modal_submit`, `freeform` |
| `custom_id` | string | Yes | Custom identifier for the interactive element |
| `data` | string (JSON) | No | Additional interaction data |

#### Interaction Types

| Type | Description | `data` Contents |
|------|-------------|-----------------|
| `button_click` | User clicked a button | `{}` |
| `select_menu` | User selected menu option(s) | `{"values": ["selected"]}` |
| `modal_submit` | User submitted a modal form | `{"fields": {"field_id": "value"}}` |
| `freeform` | Custom widget interaction | Bot-defined |

#### Example

```bash
curl -X POST https://tulip.example.com/json/bot_interactions \
  -u user@example.com:API_KEY \
  -H "Content-Type: application/json" \
  -d '{
    "message_id": 12345,
    "interaction_type": "button_click",
    "custom_id": "approve_request_123",
    "data": "{}"
  }'
```

#### Response

```json
{
  "result": "success",
  "interaction_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## Bot Presence API

### Update Presence

**POST** `/api/v1/bots/me/presence`

Update the bot's online/offline status. Only callable by bots.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `is_connected` | boolean | Yes | `true` for online, `false` for offline |

#### Example

```bash
curl -X POST https://tulip.example.com/api/v1/bots/me/presence \
  -u bot@example.com:API_KEY \
  -d 'is_connected=true'
```

#### Response

```json
{
  "result": "success"
}
```

---

## Streams API

### Get Stream Puppets

**GET** `/json/streams/{stream_id}/puppets`

Get puppet identities that have sent messages in a channel.

#### Requirements

- Channel must have puppet mode enabled
- User must have access to the channel

#### Response

```json
{
  "result": "success",
  "puppets": [
    {
      "id": 1,
      "name": "Gandalf",
      "avatar_url": "https://example.com/gandalf.png",
      "color": "#808080"
    },
    {
      "id": 2,
      "name": "Frodo",
      "avatar_url": null,
      "color": null
    }
  ]
}
```

---

## User Settings API

### Update User Color

**PATCH** `/api/v1/settings`

Set the user's personal display color.

#### New Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `color` | string | Hex color (#RGB or #RRGGBB), or null to clear |

#### Example

```bash
curl -X PATCH https://tulip.example.com/api/v1/settings \
  -u user@example.com:API_KEY \
  -d 'color=#e74c3c'
```

---

## User Groups API

### Update Group Color

**PATCH** `/api/v1/user_groups/{group_id}`

Set a user group's display color.

#### New Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `color` | string | Hex color (#RGB or #RRGGBB) |

#### Example

```bash
curl -X PATCH https://tulip.example.com/api/v1/user_groups/123 \
  -u admin@example.com:API_KEY \
  -d 'color=#3498db'
```

---

## Webhook Payloads

When bots receive events, they are delivered as HTTP POST requests to the bot's webhook URL.

### Interaction Webhook

Sent when a user interacts with a widget.

```json
{
  "type": "interaction",
  "token": "bot-service-token",
  "bot_email": "mybot@example.com",
  "bot_full_name": "My Bot",
  "interaction_id": "550e8400-e29b-41d4-a716-446655440000",
  "interaction_type": "button_click",
  "custom_id": "approve_123",
  "data": {},
  "message": {
    "id": 12345,
    "sender_id": 100,
    "content": "...",
    "topic": "Approvals",
    "stream_id": 5
  },
  "user": {
    "id": 456,
    "email": "alice@example.com",
    "full_name": "Alice"
  }
}
```

#### Webhook Response Options

```json
// Public reply
{"content": "Request approved!"}

// Ephemeral (only visible to interacting user)
{"ephemeral": true, "content": "You approved the request."}

// Visible to specific users
{"visible_user_ids": [456, 789], "content": "Private message."}

// With new widget
{
  "content": "Updated:",
  "widget_content": {
    "widget_type": "rich_embed",
    "extra_data": {"title": "Approved", "color": 3066993}
  }
}

// Acknowledge without response
{}
```

---

### Autocomplete Webhook

Sent when the client needs dynamic autocomplete suggestions.

```json
{
  "type": "autocomplete",
  "token": "bot-service-token",
  "command": "inventory",
  "option": "item",
  "partial": "sw",
  "context": {
    "stream_id": 5,
    "topic": "Game"
  },
  "user": {
    "id": 123,
    "email": "alice@example.com",
    "full_name": "Alice"
  }
}
```

#### Expected Response

```json
{
  "choices": [
    {"value": "sword_iron", "label": "Iron Sword"},
    {"value": "sword_steel", "label": "Steel Sword"}
  ]
}
```

---

### Command Invocation Webhook

Sent when a user invokes a slash command.

```json
{
  "type": "command_invocation",
  "bot_user_id": 100,
  "user_profile_id": 456,
  "message_id": 12345,
  "interaction_id": "550e8400-e29b-41d4-a716-446655440000",
  "command": "weather",
  "arguments": {
    "location": "San Francisco",
    "units": "f"
  },
  "context": {
    "stream_id": 5,
    "topic": "Weather"
  },
  "user": {
    "id": 456,
    "email": "alice@example.com",
    "full_name": "Alice"
  }
}
```

---

## Events

New event types sent via the real-time events system.

### bot_command

Sent when commands are added or removed.

```json
// Command added/updated
{
  "type": "bot_command",
  "op": "add",
  "command": {
    "id": 42,
    "name": "weather",
    "description": "Get weather forecast",
    "options": [...],
    "bot_id": 123,
    "bot_name": "Weather Bot"
  }
}

// Command removed
{
  "type": "bot_command",
  "op": "remove",
  "command_id": 42
}
```

### bot_presence

Sent when a bot's presence status changes.

```json
{
  "type": "bot_presence",
  "bot_id": 123,
  "is_connected": true,
  "last_connected_time": 1704793200.0,
  "server_timestamp": 1704793200.5
}
```

### realm_user (color update)

Sent when a user's color changes.

```json
{
  "type": "realm_user",
  "op": "update",
  "person": {
    "user_id": 456,
    "color": "#e74c3c",
    "effective_color": "#e74c3c"
  }
}
```

### user_group (color update)

Sent when a group's color changes.

```json
{
  "type": "user_group",
  "op": "update",
  "group_id": 123,
  "data": {
    "color": "#3498db"
  }
}
```

### user_persona

Sent when a user's persona is added, updated, or removed. Only delivered to the persona's owner.

```json
// Persona added
{
  "type": "user_persona",
  "op": "add",
  "persona": {
    "id": 42,
    "name": "Gandalf",
    "avatar_url": "https://example.com/gandalf.png",
    "color": "#808080",
    "bio": "A wizard is never late",
    "is_active": true,
    "date_created": 1704793200
  }
}

// Persona updated
{
  "type": "user_persona",
  "op": "update",
  "persona": {
    "id": 42,
    "name": "Gandalf",
    "avatar_url": "https://example.com/gandalf.png",
    "color": "#808080",
    "bio": "A wizard is never late, nor is he early",
    "is_active": true,
    "date_created": 1704793200
  }
}

// Persona removed
{
  "type": "user_persona",
  "op": "remove",
  "persona_id": 42
}
```

---

## Widget Types Reference

For complete widget documentation including rich embeds, interactive components, modals, and freeform widgets, see [ADVANCED_BOTS.md](ADVANCED_BOTS.md).

### Quick Reference

| Widget Type | Description | Trusted Required |
|-------------|-------------|------------------|
| `rich_embed` | Discord-style embed cards | No |
| `interactive` | Buttons and select menus | No |
| `freeform` | Custom HTML/CSS/JS | Yes |
| `command_invocation` | Slash command display (internal) | N/A |
