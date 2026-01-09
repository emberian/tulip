import * as z from "zod/mini";

import * as channel from "./channel.ts";

// Puppet data for typeahead
export type StreamPuppet = {
    id: number;
    name: string;
    avatar_url: string | null;
    color: string | null;
};

const stream_puppets_response_schema = z.object({
    puppets: z.array(
        z.object({
            id: z.number(),
            name: z.string(),
            avatar_url: z.nullable(z.string()),
            color: z.nullable(z.string()),
        }),
    ),
});

// Cache of puppets per stream
const stream_puppets_cache: Map<number, StreamPuppet[]> = new Map();

// Track which streams we've fetched puppets for
const fetched_streams: Set<number> = new Set();

// Track in-flight requests to avoid duplicate fetches
const pending_fetches: Set<number> = new Set();

export function get_puppets_for_stream(stream_id: number): StreamPuppet[] {
    return stream_puppets_cache.get(stream_id) ?? [];
}

export function has_fetched_puppets(stream_id: number): boolean {
    return fetched_streams.has(stream_id);
}

export function fetch_puppets_for_stream(stream_id: number): void {
    if (fetched_streams.has(stream_id) || pending_fetches.has(stream_id)) {
        return;
    }

    pending_fetches.add(stream_id);
    void channel.get({
        url: `/json/streams/${stream_id}/puppets`,
        success(raw_data) {
            const data = stream_puppets_response_schema.parse(raw_data);
            stream_puppets_cache.set(stream_id, data.puppets);
            fetched_streams.add(stream_id);
            pending_fetches.delete(stream_id);
        },
        error() {
            // Stream might not have puppet mode enabled, or other error
            // Just mark as fetched with empty list
            stream_puppets_cache.set(stream_id, []);
            fetched_streams.add(stream_id);
            pending_fetches.delete(stream_id);
        },
    });
}

export function clear_cache(): void {
    stream_puppets_cache.clear();
    fetched_streams.clear();
}

// Add a puppet to the cache (called when we send a puppet message)
export function add_puppet_to_cache(
    stream_id: number,
    puppet: StreamPuppet,
): void {
    const existing = stream_puppets_cache.get(stream_id) ?? [];
    // Check if puppet already exists
    const exists = existing.some((p) => p.name === puppet.name);
    if (!exists) {
        existing.push(puppet);
        stream_puppets_cache.set(stream_id, existing);
    }
}
