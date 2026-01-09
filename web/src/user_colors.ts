import * as people from "./people.ts";
import type {StreamPuppet} from "./stream_puppets.ts";

/**
 * Get the effective color for a user.
 * Returns the user's personal color if set, or null.
 * The backend has already computed the effective color (personal > group > default),
 * so we just return what's in the user object.
 */
export function get_user_color(user_id: number): string | null {
    const person = people.maybe_get_user_by_id(user_id);
    return person?.color ?? null;
}

/**
 * Get the effective color for a puppet mention.
 * Priority: Puppet's color > Sender's effective color > null
 */
export function get_puppet_color(puppet: StreamPuppet, sender_id: number): string | null {
    if (puppet.color) {
        return puppet.color;
    }
    return get_user_color(sender_id);
}

/**
 * Get the effective color for a puppet by name and sender.
 * This is used when we don't have the full puppet object but know the sender.
 */
export function get_puppet_color_for_sender(
    puppet_color: string | null | undefined,
    sender_id: number,
): string | null {
    if (puppet_color) {
        return puppet_color;
    }
    return get_user_color(sender_id);
}
