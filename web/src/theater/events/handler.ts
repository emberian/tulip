/**
 * Event handler for Theater Mode
 * Long-polls /json/events for real-time updates
 */

import {messages, toTheaterMessage} from "../stores/messages";
import {presence, type PresenceStatus} from "../stores/presence";
import {typing} from "../stores/typing";

let eventQueueId: string | null = null;
let lastEventId = -1;
let isPolling = false;
let abortController: AbortController | null = null;
let retryCount = 0;
const MAX_RETRY_DELAY_MS = 60000; // 1 minute max

// Get CSRF token from cookie
function getCsrfToken(): string {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match?.[1] ?? "";
}

export function initializeEventHandler(queueId: string, initialEventId: number): void {
    eventQueueId = queueId;
    lastEventId = initialEventId;
    startPolling();
}

export function cleanupEventHandler(): void {
    isPolling = false;
    retryCount = 0;
    if (abortController) {
        abortController.abort();
        abortController = null;
    }
    // Clean up event queue on the server
    // Use keepalive to ensure request completes even during page unload
    if (eventQueueId) {
        fetch("/json/events", {
            method: "DELETE",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRFToken": getCsrfToken(),
            },
            body: `queue_id=${encodeURIComponent(eventQueueId)}`,
            credentials: "same-origin",
            keepalive: true,
        }).catch(() => {
            // Ignore errors during cleanup
        });
        eventQueueId = null;
    }
}

function startPolling(): void {
    if (!eventQueueId || isPolling) return;
    isPolling = true;
    poll();
}

async function poll(): Promise<void> {
    if (!isPolling || !eventQueueId) return;

    abortController = new AbortController();

    try {
        const params = new URLSearchParams({
            queue_id: eventQueueId,
            last_event_id: String(lastEventId),
            client_gravatar: "true",
            slim_presence: "true",
        });

        const response = await fetch(`/json/events?${params.toString()}`, {
            method: "GET",
            credentials: "same-origin",
            signal: abortController.signal,
        });

        if (!response.ok) {
            if (response.status === 400) {
                // Bad event queue - reload
                console.error("Event queue expired, reloading...");
                window.location.reload();
                return;
            }
            if (response.status === 401 || response.status === 403) {
                // Authentication expired - redirect to login
                console.error("Session expired, redirecting to login...");
                isPolling = false;
                window.location.href = "/login/";
                return;
            }
            throw new Error(`Event poll failed: ${response.status}`);
        }

        // Success - reset retry count
        retryCount = 0;

        const data = (await response.json()) as {events?: Array<Record<string, unknown>>};

        if (data.events) {
            for (const event of data.events) {
                const eventId = event["id"] as number;
                lastEventId = Math.max(lastEventId, eventId);
                dispatchEvent(event);
            }
        }

        // Continue polling immediately
        if (isPolling) {
            poll();
        }
    } catch (error) {
        if (error instanceof Error && error.name === "AbortError") {
            return;
        }
        console.error("Event poll error:", error);
        // Retry with exponential backoff
        if (isPolling) {
            const delay = Math.min(5000 * Math.pow(2, retryCount), MAX_RETRY_DELAY_MS);
            retryCount++;
            console.log(`Retrying in ${delay}ms (attempt ${retryCount})`);
            setTimeout(poll, delay);
        }
    }
}

function dispatchEvent(event: Record<string, unknown>): void {
    const eventType = event["type"] as string;

    switch (eventType) {
        case "message":
            handleMessageEvent(event);
            break;
        case "update_message":
            handleUpdateMessageEvent(event);
            break;
        case "delete_message":
            handleDeleteMessageEvent(event);
            break;
        case "typing":
            handleTypingEvent(event);
            break;
        case "presence":
            handlePresenceEvent(event);
            break;
        case "reaction":
            // Theater mode doesn't prominently show reactions, but we could track them
            break;
        default:
            // Ignore other event types for now
            break;
    }
}

function handleMessageEvent(event: Record<string, unknown>): void {
    const msg = event["message"] as Record<string, unknown>;
    const theaterMsg = toTheaterMessage(msg);
    messages.addMessage(theaterMsg);
}

function handleUpdateMessageEvent(event: Record<string, unknown>): void {
    const messageId = event["message_id"] as number;
    const updates: Partial<{content: string; rendered_content: string; topic: string}> = {};

    if (event["rendered_content"] !== undefined) {
        updates.rendered_content = event["rendered_content"] as string;
    }
    if (event["content"] !== undefined) {
        updates.content = event["content"] as string;
    }
    if (event["subject"] !== undefined || event["topic"] !== undefined) {
        updates.topic = (event["subject"] ?? event["topic"]) as string;
    }

    if (Object.keys(updates).length > 0) {
        messages.updateMessage(messageId, updates);
    }
}

function handleDeleteMessageEvent(event: Record<string, unknown>): void {
    const messageIds = event["message_ids"] as number[];
    for (const id of messageIds) {
        messages.removeMessage(id);
    }
}

function handleTypingEvent(event: Record<string, unknown>): void {
    const messageType = event["message_type"] as string;
    if (messageType !== "stream") return;

    const streamId = event["stream_id"] as number;
    const topic = event["topic"] as string;
    const op = event["op"] as string;
    const sender = event["sender"] as {user_id: number; full_name?: string} | undefined;

    if (!sender) return;

    const key = `${streamId}:${topic}`;
    const typist = {
        user_id: sender.user_id,
        full_name: sender.full_name ?? "Someone",
    };

    if (op === "start") {
        typing.addTypist(key, typist);
    } else {
        typing.removeTypist(key, sender.user_id);
    }
}

function handlePresenceEvent(event: Record<string, unknown>): void {
    const presenceData = event["presence"] as Record<string, {status: string}> | undefined;
    if (!presenceData) return;

    for (const [userIdStr, data] of Object.entries(presenceData)) {
        const userId = Number.parseInt(userIdStr, 10);
        const status = (data.status as PresenceStatus) || "offline";
        presence.setPresence(userId, status);
    }
}
