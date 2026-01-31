/**
 * Presence store - who's in the scene
 */

import {writable, derived} from "svelte/store";

import {users} from "./users";

export type PresenceStatus = "active" | "idle" | "offline";

export interface CastMember {
    user_id: number;
    full_name: string;
    avatar_url: string | null;
    status: PresenceStatus;
    // If the user has an active persona, show it
    active_persona?: {
        id: number;
        name: string;
        avatar_url: string | null;
    };
}

function createPresenceStore() {
    const {subscribe, set, update} = writable<Map<number, CastMember>>(new Map());

    return {
        subscribe,
        setPresence(userId: number, status: PresenceStatus) {
            update((map) => {
                const member = map.get(userId);
                if (member) {
                    const newMap = new Map(map);
                    newMap.set(userId, {...member, status});
                    return newMap;
                }
                // User not in cast list - look up in users store and add them
                const userInfo = users.getUser(userId);
                if (userInfo) {
                    const newMap = new Map(map);
                    newMap.set(userId, {
                        user_id: userId,
                        full_name: userInfo.full_name,
                        avatar_url: userInfo.avatar_url,
                        status,
                    });
                    return newMap;
                }
                return map;
            });
        },
        addMember(member: CastMember) {
            update((map) => {
                const newMap = new Map(map);
                newMap.set(member.user_id, member);
                return newMap;
            });
        },
        updateMember(userId: number, updates: Partial<CastMember>) {
            update((map) => {
                const member = map.get(userId);
                if (member) {
                    const newMap = new Map(map);
                    newMap.set(userId, {...member, ...updates});
                    return newMap;
                }
                return map;
            });
        },
        removeMember(userId: number) {
            update((map) => {
                const newMap = new Map(map);
                newMap.delete(userId);
                return newMap;
            });
        },
        initialize(members: CastMember[]) {
            set(new Map(members.map((m) => [m.user_id, m])));
        },
        clear() {
            set(new Map());
        },
    };
}

export const presence = createPresenceStore();

/**
 * Derived: only active/idle members (the "cast on stage")
 */
export const activeCast = derived(presence, ($presence) =>
    Array.from($presence.values())
        .filter((m) => m.status !== "offline")
        .sort((a, b) => a.full_name.localeCompare(b.full_name)),
);

/**
 * Derived: array of all members for iteration
 */
export const allMembers = derived(presence, ($presence) =>
    Array.from($presence.values()).sort((a, b) => {
        // Sort active first, then idle, then offline
        const statusOrder = {active: 0, idle: 1, offline: 2};
        const statusDiff = statusOrder[a.status] - statusOrder[b.status];
        if (statusDiff !== 0) return statusDiff;
        return a.full_name.localeCompare(b.full_name);
    }),
);
