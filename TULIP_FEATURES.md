# Tulip Features

This document describes the features unique to the Tulip fork, covering APIs, UI changes, and bot development capabilities.

## Table of Contents

1. [Whispers](#whispers)
2. [Inline Spoilers](#inline-spoilers)
3. [User and Group Colors](#user-and-group-colors)
4. [Bot Commands and Autocomplete](#bot-commands-and-autocomplete)
5. [Bot Interactions](#bot-interactions)
6. [Puppeting](#puppeting)
7. [Personas](#personas)

---

## Whispers

Whispers are messages in a channel that are only visible to specific users or groups. Unlike direct messages, whispers appear in the channel context but are hidden from other subscribers.

### User Experience

- A whisper toggle button appears in the compose box (eye-slash icon)
- When enabled, a recipient input field appears where you can add users or groups
- Whisper messages display with a blue indicator showing "Whispered to: [recipients]"
- Clicking the whisper indicator on a received message opens a reply to the same recipients
- Whispers are hidden from push notifications and emails for non-recipients (shown as "(spoiler)" placeholder)

### API: Sending Whispers

**POST** `/api/v1/messages`

New parameters for channel messages:

| Parameter | Type | Description |
|-----------|------|-------------|
| `whisper_to_user_ids` | array[int] | User IDs who can see the whisper (plus sender) |
| `whisper_to_group_ids` | array[int] | Group IDs whose members can see the whisper |
| `whisper_to_puppet_ids` | array[int] | Puppet IDs whose handlers can see the whisper |

**Example:**

```bash
curl -X POST https://tulip.example.com/api/v1/messages \
  -u bot@example.com:API_KEY \
  -d 'type=stream' \
  -d 'to=general' \
  -d 'topic=Team Updates' \
  -d 'content=This is only visible to Alice and the moderators group' \
  -d 'whisper_to_user_ids=[123]' \
  -d 'whisper_to_group_ids=[456]'
```

### Message Object

Messages include a `whisper_recipients` field when whispered:

```json
{
  "id": 12345,
  "content": "Secret message",
  "whisper_recipients": {
    "user_ids": [123, 456],
    "group_ids": [789]
  }
}
```

### Whispering to Puppets

Whispers can target puppets in addition to users and groups. When a puppet is whispered to, the message is delivered to the bot that has claimed the puppet's handler.

```bash
curl -X POST https://tulip.example.com/api/v1/messages \
  -u user@example.com:API_KEY \
  -d 'type=stream' \
  -d 'to=game-chat' \
  -d 'topic=Adventure' \
  -d 'content=Psst, Gandalf, I have the ring' \
  -d 'whisper_to_puppet_ids=[42]'
```

### Notes

- Whispers only work in channel messages, not direct messages
- Group membership is evaluated dynamically - adding a user to a whispered group grants access to past whispers
- The sender always has access to their own whispers
- Puppet whispers require the puppet to exist in the target channel and have an active handler

---

## Inline Spoilers

Inline spoilers hide text within a message until clicked, using Discord-style `||text||` syntax.

### Syntax

```
I think ||the butler did it|| but I'm not sure.
```

Renders as hidden text that reveals on click.

### Behavior

- Text appears as a dark rectangle until clicked or hovered
- Click toggles the revealed state
- Multiple inline spoilers can appear in the same message
- In notifications, inline spoilers are replaced with "(spoiler)"

### CSS Classes

- `.spoiler-inline` - Base styling (hidden state)
- `.spoiler-inline.revealed` - Revealed state

### Difference from Block Spoilers

Block spoilers use fenced code syntax:
```
```spoiler Optional Header
Hidden content here
```
```

Inline spoilers are for hiding text within a paragraph without breaking flow.

---

## User and Group Colors

Users and groups can have custom display colors that affect how their names appear in mentions and the UI.

### Color Priority (Effective Color)

When displaying a user's color, the system follows this priority:

1. **Personal color** - If the user has set a personal color, use it
2. **Group color** - Otherwise, use the highest-priority group they belong to:
   - Owners (system group)
   - Administrators (system group)
   - Moderators (system group)
   - Members (system group)
   - Custom groups (ordered by creation date, newest first)
3. **None** - Use default styling

### API: Setting User Color

**PATCH** `/api/v1/settings`

```bash
curl -X PATCH https://tulip.example.com/api/v1/settings \
  -u user@example.com:API_KEY \
  -d 'color=#ff5733'
```

Valid formats: `#RGB` or `#RRGGBB`

### API: Setting Group Color

**PATCH** `/api/v1/user_groups/{group_id}`

```bash
curl -X PATCH https://tulip.example.com/api/v1/user_groups/123 \
  -u admin@example.com:API_KEY \
  -d 'color=#3498db'
```

### User Object Fields

| Field | Type | Description |
|-------|------|-------------|
| `color` | string\|null | User's personal color setting |
| `effective_color` | string\|null | Computed color considering group membership |

### Events

When colors change, a `realm_user` event is sent with `color` and `effective_color` fields.

---

## Bot Commands and Autocomplete

Bots can register slash commands that appear in the compose box typeahead with autocomplete support.

### User Experience

1. Type `/` in the compose box to see available commands
2. Select a command to see its options
3. Options can have static choices or dynamic autocomplete
4. Submitted commands appear as styled widgets showing the invocation

### Registering Commands

**POST** `/json/bot_commands/register`

```json
{
  "name": "weather",
  "description": "Get weather forecast",
  "options": [
    {
      "name": "location",
      "type": "string",
      "description": "City name",
      "required": true
    },
    {
      "name": "units",
      "type": "string",
      "description": "Temperature units",
      "choices": [
        {"name": "Celsius", "value": "c"},
        {"name": "Fahrenheit", "value": "f"}
      ]
    }
  ]
}
```

### Dynamic Autocomplete

For options without static choices, Tulip requests suggestions from your bot:

**Request to bot webhook:**

```json
{
  "type": "autocomplete",
  "command": "inventory",
  "option": "item",
  "partial": "sw",
  "user": {"id": 123, "email": "alice@example.com"}
}
```

**Bot response:**

```json
{
  "choices": [
    {"value": "sword_iron", "label": "Iron Sword"},
    {"value": "sword_steel", "label": "Steel Sword"}
  ]
}
```

### Command Invocation Widget

When a user submits a command, a styled widget displays showing:
- Bot avatar and name
- Command name (e.g., `/weather`)
- Arguments with names and values
- Status indicator (pending, responding, complete, error)

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/json/bot_commands` | List all registered commands |
| `POST` | `/json/bot_commands/register` | Register a new command |
| `DELETE` | `/json/bot_commands/{id}` | Delete a command |
| `GET` | `/json/bot_commands/{bot_id}/autocomplete` | Get dynamic suggestions |

---

## Bot Interactions

Bots can send interactive widgets (buttons, select menus, forms) and receive events when users interact with them.

### Widget Types

#### Rich Embed

Discord-style embeds for displaying formatted information:

```json
{
  "widget_type": "rich_embed",
  "extra_data": {
    "title": "Status Report",
    "description": "All systems operational",
    "color": 3066993,
    "fields": [
      {"name": "CPU", "value": "45%", "inline": true},
      {"name": "Memory", "value": "2.1 GB", "inline": true}
    ]
  }
}
```

#### Interactive

Buttons and select menus that trigger events:

```json
{
  "widget_type": "interactive",
  "extra_data": {
    "content": "Choose an option:",
    "components": [
      {
        "type": "action_row",
        "components": [
          {"type": "button", "label": "Approve", "style": "success", "custom_id": "approve"},
          {"type": "button", "label": "Reject", "style": "danger", "custom_id": "reject"}
        ]
      }
    ]
  }
}
```

#### Freeform (Trusted Bots Only)

Custom HTML/CSS/JS widgets for advanced use cases.

### Receiving Interactions

When users interact with widgets, your bot receives a webhook:

```json
{
  "type": "interaction",
  "interaction_type": "button_click",
  "custom_id": "approve",
  "message": {"id": 12345, "topic": "Approvals"},
  "user": {"id": 456, "full_name": "Alice"}
}
```

### Responding to Interactions

Return JSON to send a response:

```json
{
  "content": "Request approved!",
  "ephemeral": true
}
```

Response options:
- `content` - Message text
- `ephemeral` - Only visible to the interacting user
- `visible_user_ids` - Only visible to specific users
- `widget_content` - Include a new widget

See [ADVANCED_BOTS.md](ADVANCED_BOTS.md) for complete widget documentation.

---

## Puppeting

Puppeting allows bots to send messages that appear to come from other identities (names, avatars, colors). Useful for bridges, game bots, and notification systems.

### Enabling Puppet Mode

Puppet mode must be enabled per-channel by an administrator in channel settings.

### Sending Puppet Messages

**POST** `/api/v1/messages`

| Parameter | Type | Description |
|-----------|------|-------------|
| `puppet_display_name` | string | Name to display (max 100 chars) |
| `puppet_avatar_url` | string | Avatar URL to display |
| `puppet_color` | string | Hex color for the puppet's name |

**Example:**

```bash
curl -X POST https://tulip.example.com/api/v1/messages \
  -u bot@example.com:API_KEY \
  -d 'type=stream' \
  -d 'to=game-chat' \
  -d 'topic=Adventure' \
  -d 'content=You shall not pass!' \
  -d 'puppet_display_name=Gandalf' \
  -d 'puppet_avatar_url=https://example.com/gandalf.png' \
  -d 'puppet_color=#808080'
```

### Puppet Presence

Active puppets appear in the right sidebar under "Puppets" so users know which puppet identities are present in the channel.

### API: Get Channel Puppets

**GET** `/json/streams/{stream_id}/puppets`

Returns puppets that have sent messages in the channel:

```json
{
  "puppets": [
    {
      "id": 1,
      "name": "Gandalf",
      "avatar_url": "https://example.com/gandalf.png",
      "color": "#808080"
    }
  ]
}
```

### Puppet Typeahead

In channels with puppet mode enabled, typing `@` shows puppets in the mention typeahead alongside users.

### Restrictions

- Puppet messages can only be sent to channels (not DMs)
- The channel must have puppet mode enabled
- Only bot accounts can send puppet messages
- Hovering over a puppet message reveals the actual sending bot

---

## Personas

Personas are user-owned character identities for roleplay and other creative uses. Unlike bot-controlled puppets (which are stream-scoped), personas are personal and portable - they belong to a user and can be used in any channel.

### Key Differences from Puppets

| Feature | Personas | Puppets |
|---------|----------|---------|
| Ownership | Belongs to a user | Controlled by a bot |
| Scope | Can be used anywhere | Scoped to a single channel |
| Creation | Created by the user | Created by bot messages |
| Identity | Represents the user | Represents an external identity |

### User Experience

- Access persona settings via Settings > My Characters
- Create up to 20 personas per account
- Each persona has a name, optional avatar, optional color, and optional bio
- In the compose box, click the persona selector to choose which identity to send as
- Messages sent as a persona display the persona's name, avatar, and color
- Hovering over a persona message reveals the actual sender

### Mentioning Personas

Personas can be @-mentioned like users. When a persona is mentioned, the persona's owner receives a notification.

```
Hey @Gandalf, what do you think about this quest?
```

The mention renders with special styling and notifies the user who owns the "Gandalf" persona.

### API: Managing Personas

**GET** `/json/users/me/personas`

List all active personas for the current user.

**POST** `/json/users/me/personas`

Create a new persona.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Persona name (max 100 chars) |
| `avatar_url` | string | No | Avatar image URL |
| `color` | string | No | Hex color (#RGB or #RRGGBB) |
| `bio` | string | No | Short bio (max 500 chars) |

**PATCH** `/json/users/me/personas/{persona_id}`

Update an existing persona.

**DELETE** `/json/users/me/personas/{persona_id}`

Soft-delete a persona (marks as inactive).

### API: Sending as a Persona

**POST** `/api/v1/messages`

| Parameter | Type | Description |
|-----------|------|-------------|
| `persona_id` | int | ID of the persona to send as |

**Example:**

```bash
curl -X POST https://tulip.example.com/api/v1/messages \
  -u user@example.com:API_KEY \
  -d 'type=stream' \
  -d 'to=roleplay' \
  -d 'topic=Adventure' \
  -d 'content=You shall not pass!' \
  -d 'persona_id=42'
```

### API: Realm Personas (for Typeahead)

**GET** `/json/realm/personas`

Get all active personas in the realm for @-mention typeahead.

### Message Object

Messages sent with a persona include these fields:

```json
{
  "id": 12345,
  "content": "You shall not pass!",
  "persona_id": 42,
  "persona_display_name": "Gandalf",
  "persona_avatar_url": "https://example.com/gandalf.png",
  "persona_color": "#808080"
}
```

### Events

**user_persona** - Sent when a user's persona is added, updated, or removed.

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
  "persona": {...}
}

// Persona removed
{
  "type": "user_persona",
  "op": "remove",
  "persona_id": 42
}
```

### Restrictions

- Maximum 20 personas per user
- Persona names must be unique per user
- Personas are soft-deleted to preserve message history

---

## Summary of New API Parameters

### Message Sending (`POST /api/v1/messages`)

| Parameter | Type | Description |
|-----------|------|-------------|
| `whisper_to_user_ids` | array[int] | Whisper recipients (user IDs) |
| `whisper_to_group_ids` | array[int] | Whisper recipients (group IDs) |
| `whisper_to_puppet_ids` | array[int] | Whisper recipients (puppet IDs) |
| `puppet_display_name` | string | Puppet display name |
| `puppet_avatar_url` | string | Puppet avatar URL |
| `puppet_color` | string | Puppet name color |
| `persona_id` | int | Persona ID to send message as |
| `widget_content` | string (JSON) | Interactive widget definition |

### User Settings (`PATCH /api/v1/settings`)

| Parameter | Type | Description |
|-----------|------|-------------|
| `color` | string | Personal display color (#RGB or #RRGGBB) |

### User Groups (`PATCH /api/v1/user_groups/{id}`)

| Parameter | Type | Description |
|-----------|------|-------------|
| `color` | string | Group display color |
