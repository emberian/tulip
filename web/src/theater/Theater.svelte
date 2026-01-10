<script lang="ts">
    import {onMount, onDestroy} from "svelte";

    import Stage from "./components/Stage.svelte";
    import CastList from "./components/CastList.svelte";
    import SceneSelector from "./components/SceneSelector.svelte";
    import Prompter from "./components/Prompter.svelte";

    import {personas} from "./stores/personas";
    import {presence, type CastMember, type PresenceStatus} from "./stores/presence";
    import {users} from "./stores/users";
    import {navigation} from "./stores/navigation";
    import {initializeEventHandler, cleanupEventHandler} from "./events/handler";
    import * as api from "./api/client";

    // Types for page params data
    interface RealmUser {
        user_id: number;
        full_name: string;
        avatar_url: string | null;
    }

    interface PresenceData {
        [userId: string]: {
            active_timestamp?: number;
            idle_timestamp?: number;
        };
    }

    interface Props {
        pageParams: Record<string, unknown>;
    }

    let {pageParams}: Props = $props();

    // Extract state data from page params (using $derived to avoid Svelte warning)
    let stateData = $derived(pageParams.state_data as Record<string, unknown> | undefined);
    let queueId = $derived(stateData?.queue_id as string | undefined);
    let lastEventId = $derived((stateData?.last_event_id as number) ?? -1);
    let subscriptions = $derived(
        stateData?.subscriptions as
            | Array<{
                  stream_id: number;
                  name: string;
                  color: string;
              }>
            | undefined,
    );

    // Start with sidebar collapsed on mobile
    const isMobile = typeof window !== "undefined" && window.innerWidth < 768;
    let sidebarCollapsed = $state(isMobile);
    let personaError = $state(false);

    // Get current stream name for display
    let currentStreamName = $derived(
        $navigation.streams.find((s) => s.stream_id === $navigation.currentStreamId)?.name ?? "",
    );

    // Check if we have a valid scene selected
    let hasActiveScene = $derived(
        $navigation.currentStreamId !== null && $navigation.currentTopic !== null,
    );

    function dismissPersonaError() {
        personaError = false;
    }

    async function retryLoadPersonas() {
        personaError = false;
        try {
            const personaList = await api.fetchPersonas();
            personas.set(personaList);
        } catch (error) {
            console.error("Failed to load personas:", error);
            personaError = true;
        }
    }

    // Handle browser back/forward
    function handlePopstate() {
        navigation.handlePopstate();
    }

    onMount(async () => {
        // Initialize navigation with subscriptions
        if (subscriptions) {
            navigation.setStreams(subscriptions);
        }

        // Restore navigation from URL hash (if present)
        navigation.initFromUrl();

        // Listen for browser back/forward
        window.addEventListener("popstate", handlePopstate);

        // Initialize presence from page params
        initializePresence();

        // Load user's personas
        try {
            const personaList = await api.fetchPersonas();
            personas.set(personaList);
        } catch (error) {
            console.error("Failed to load personas:", error);
            personaError = true;
        }

        // Start event polling
        if (queueId) {
            initializeEventHandler(queueId, lastEventId);
        }
    });

    function initializePresence(): void {
        // Get realm users from page params (raw state_data has these at top level, not nested)
        const realmUsers = (stateData?.realm_users as RealmUser[] | undefined) ?? [];

        // Initialize users store for whisper recipient lookup
        users.initialize(realmUsers);

        // Get presence data (also at top level in raw state_data)
        const presences = (stateData?.presences as PresenceData | undefined) ?? {};

        // Current time for calculating presence status
        const now = Date.now() / 1000;
        const ACTIVE_THRESHOLD = 140; // seconds
        const IDLE_THRESHOLD = 450; // seconds

        // Build cast members from realm users with presence status
        const castMembers: CastMember[] = realmUsers.map((user) => {
            const userPresence = presences[String(user.user_id)];
            let status: PresenceStatus = "offline";

            if (userPresence) {
                const activeTime = userPresence.active_timestamp ?? 0;
                const idleTime = userPresence.idle_timestamp ?? 0;
                const lastActive = Math.max(activeTime, idleTime);
                const timeSinceActive = now - lastActive;

                if (timeSinceActive < ACTIVE_THRESHOLD) {
                    status = activeTime >= idleTime ? "active" : "idle";
                } else if (timeSinceActive < IDLE_THRESHOLD) {
                    status = "idle";
                }
            }

            return {
                user_id: user.user_id,
                full_name: user.full_name,
                avatar_url: user.avatar_url,
                status,
            };
        });

        presence.initialize(castMembers);
    }

    onDestroy(() => {
        cleanupEventHandler();
        window.removeEventListener("popstate", handlePopstate);
    });

    function handleSceneChange(event: CustomEvent<{streamId: number; topic: string}>) {
        navigation.setCurrentScene(event.detail.streamId, event.detail.topic);
        // Close sidebar on mobile after selecting a scene
        if (typeof window !== "undefined" && window.innerWidth < 768) {
            sidebarCollapsed = true;
        }
    }

    function toggleSidebar() {
        sidebarCollapsed = !sidebarCollapsed;
    }

    function handleGlobalKeydown(event: KeyboardEvent) {
        // Don't intercept if user is in an input
        const target = event.target as HTMLElement;
        if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) {
            return;
        }

        switch (event.key) {
            case "Escape":
                // Close sidebar on mobile (if open)
                if (!sidebarCollapsed && typeof window !== "undefined" && window.innerWidth < 768) {
                    event.preventDefault();
                    sidebarCollapsed = true;
                }
                break;
            case "s":
                // Toggle sidebar
                event.preventDefault();
                toggleSidebar();
                break;
            case "ArrowRight":
                // Focus prompter from anywhere
                if (hasActiveScene) {
                    event.preventDefault();
                    const textarea = document.querySelector<HTMLTextAreaElement>(".prompter textarea");
                    textarea?.focus();
                }
                break;
        }
    }
</script>

<svelte:window onkeydown={handleGlobalKeydown} />

<a href="#theater-stage-content" class="theater-skip-link">Skip to content</a>

{#if personaError}
    <div class="persona-error-banner" role="alert">
        <span>Failed to load personas. You can still chat as yourself.</span>
        <div class="banner-actions">
            <button class="banner-btn" onclick={retryLoadPersonas}>Retry</button>
            <button class="banner-dismiss" onclick={dismissPersonaError} aria-label="Dismiss error">
                <span aria-hidden="true">×</span>
            </button>
        </div>
    </div>
{/if}

<div class="theater" class:sidebar-collapsed={sidebarCollapsed} class:sidebar-open={!sidebarCollapsed}>
    <!-- Mobile-only: hamburger button (visible when sidebar closed) -->
    <button
        class="mobile-menu-btn"
        onclick={toggleSidebar}
        aria-label="Open menu"
        type="button"
    >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M3 12h18M3 6h18M3 18h18"/>
        </svg>
    </button>

    <!-- Mobile-only: backdrop when sidebar open -->
    <button
        class="sidebar-backdrop"
        class:visible={!sidebarCollapsed}
        onclick={toggleSidebar}
        aria-label="Close sidebar"
        type="button"
        tabindex="-1"
    ></button>

    <aside class="theater-sidebar" aria-label="Theater sidebar">
        <div class="sidebar-header">
            <div class="header-left">
                <a href="/" class="back-link" aria-label="Back to main app">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                        <path d="M19 12H5M12 19l-7-7 7-7"/>
                    </svg>
                </a>
                <h1 class="theater-title">Theater</h1>
            </div>
            <!-- Desktop: chevron collapse/expand button -->
            <button
                class="collapse-btn desktop-only"
                onclick={toggleSidebar}
                aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
                aria-expanded={!sidebarCollapsed}
            >
                <span aria-hidden="true">{sidebarCollapsed ? "›" : "‹"}</span>
            </button>
            <!-- Mobile: close button -->
            <button
                class="close-btn mobile-only"
                onclick={toggleSidebar}
                aria-label="Close menu"
                type="button"
            >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                    <path d="M18 6L6 18M6 6l12 12"/>
                </svg>
            </button>
        </div>

        <!-- Desktop: expand button shown when collapsed -->
        <button
            class="expand-btn desktop-only"
            onclick={toggleSidebar}
            aria-label="Expand sidebar"
            type="button"
        >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <path d="M9 18l6-6-6-6"/>
            </svg>
        </button>

        <div class="sidebar-content">
            <SceneSelector
                streams={$navigation.streams}
                selectedStreamId={$navigation.currentStreamId}
                selectedTopic={$navigation.currentTopic}
                on:sceneChange={handleSceneChange}
            />
            <CastList members={$presence} />
        </div>
    </aside>

    <main class="theater-stage" id="theater-stage-content" aria-label="Stage area">
        {#if hasActiveScene}
            <Stage
                streamId={$navigation.currentStreamId!}
                topic={$navigation.currentTopic!}
                streamName={currentStreamName}
            />
            <Prompter
                streamId={$navigation.currentStreamId!}
                topic={$navigation.currentTopic!}
            />
        {:else}
            <div class="theater-welcome" role="status">
                <div class="welcome-content">
                    <h2>Welcome to the Theater</h2>
                    <p>Select a scene from the sidebar to begin.</p>
                </div>
            </div>
        {/if}
    </main>
</div>

<style>
    /* ===== BASE LAYOUT (Desktop) ===== */
    .theater {
        display: grid;
        grid-template-columns: 280px 1fr;
        height: 100vh;
        background: var(--theater-bg);
        color: var(--theater-text);
    }

    .theater.sidebar-collapsed {
        grid-template-columns: 48px 1fr;
    }

    /* ===== SIDEBAR ===== */
    .theater-sidebar {
        background: var(--theater-sidebar-bg);
        border-right: 1px solid var(--theater-border);
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }

    .sidebar-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1rem;
        border-bottom: 1px solid var(--theater-border);
        flex-shrink: 0;
    }

    .header-left {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        min-width: 0;
    }

    .back-link {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        border-radius: 6px;
        color: var(--theater-muted);
        transition: all var(--theater-transition-fast);
        flex-shrink: 0;
    }

    .back-link:hover {
        background: var(--theater-bg-elevated);
        color: var(--theater-text);
    }

    .theater-title {
        font-size: 1.25rem;
        font-weight: 600;
        margin: 0;
        font-family: var(--theater-font-ui);
    }

    .sidebar-content {
        display: flex;
        flex-direction: column;
        flex: 1;
        overflow: hidden;
    }

    /* Desktop collapsed state */
    .sidebar-collapsed .theater-title {
        display: none;
    }

    .sidebar-collapsed .sidebar-content {
        display: none;
    }

    .sidebar-collapsed .header-left {
        width: 100%;
        justify-content: center;
    }

    .sidebar-collapsed .collapse-btn {
        display: none;
    }

    .sidebar-collapsed .sidebar-header {
        justify-content: center;
        padding: 1rem 0.5rem;
    }

    /* ===== EXPAND BUTTON (Desktop only, when collapsed) ===== */
    .expand-btn {
        display: none;
    }

    .sidebar-collapsed .expand-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        margin: 0.5rem auto;
        background: none;
        border: 1px solid var(--theater-border);
        border-radius: 6px;
        color: var(--theater-muted);
        cursor: pointer;
        transition: all var(--theater-transition-fast);
    }

    .sidebar-collapsed .expand-btn:hover {
        color: var(--theater-text);
        background: var(--theater-bg-elevated);
        border-color: var(--theater-accent);
    }

    /* ===== COLLAPSE BUTTON (Desktop only) ===== */
    .collapse-btn {
        background: none;
        border: none;
        color: var(--theater-muted);
        cursor: pointer;
        font-size: 1.25rem;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        transition: all var(--theater-transition-fast);
    }

    .collapse-btn:hover {
        color: var(--theater-text);
        background: var(--theater-bg-elevated);
    }

    /* ===== MOBILE MENU BUTTON (hidden on desktop) ===== */
    .mobile-menu-btn {
        display: none;
    }

    /* ===== CLOSE BUTTON (Mobile only, hidden on desktop) ===== */
    .close-btn {
        display: none;
    }

    /* ===== SIDEBAR BACKDROP (hidden on desktop) ===== */
    .sidebar-backdrop {
        display: none;
    }

    /* ===== STAGE ===== */
    .theater-stage {
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }

    .theater-welcome {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .welcome-content {
        text-align: center;
        color: var(--theater-muted);
    }

    .welcome-content h2 {
        font-family: var(--theater-font-display);
        font-size: 2rem;
        font-weight: 400;
        margin-bottom: 0.5rem;
        color: var(--theater-text);
    }

    .welcome-content p {
        font-family: var(--theater-font-narrative);
        font-size: 1.1rem;
        font-style: italic;
    }

    /* ===== PERSONA ERROR BANNER ===== */
    .persona-error-banner {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.75rem 1.5rem;
        background: rgba(220, 38, 38, 0.9);
        color: white;
        font-family: var(--theater-font-ui);
        font-size: 0.9rem;
        z-index: 200;
    }

    .banner-actions {
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }

    .banner-btn {
        padding: 0.3rem 0.75rem;
        background: rgba(255, 255, 255, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 4px;
        color: white;
        cursor: pointer;
        font-size: 0.85rem;
        transition: background var(--theater-transition-fast);
    }

    .banner-btn:hover {
        background: rgba(255, 255, 255, 0.3);
    }

    .banner-dismiss {
        background: none;
        border: none;
        color: white;
        cursor: pointer;
        font-size: 1.25rem;
        opacity: 0.7;
        padding: 0;
        line-height: 1;
    }

    .banner-dismiss:hover {
        opacity: 1;
    }

    /* ===== MOBILE STYLES ===== */
    @media (max-width: 768px) {
        /* Grid is always single column on mobile */
        .theater {
            grid-template-columns: 1fr;
        }

        .theater.sidebar-collapsed {
            grid-template-columns: 1fr;
        }

        /* Mobile menu button - fixed position, visible when sidebar closed */
        .mobile-menu-btn {
            display: flex;
            align-items: center;
            justify-content: center;
            position: fixed;
            top: 0.75rem;
            left: 0.75rem;
            z-index: 50;
            width: 44px;
            height: 44px;
            background: var(--theater-bg-elevated);
            border: 1px solid var(--theater-border);
            border-radius: 8px;
            color: var(--theater-text);
            cursor: pointer;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
            -webkit-tap-highlight-color: transparent;
        }

        .mobile-menu-btn:active {
            background: var(--theater-bg);
        }

        /* Hide hamburger when sidebar is open */
        .theater.sidebar-open .mobile-menu-btn {
            display: none;
        }

        /* Backdrop - covers content when sidebar open */
        .sidebar-backdrop {
            display: block;
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0);
            z-index: 90;
            border: none;
            cursor: pointer;
            pointer-events: none;
            transition: background var(--theater-transition-normal);
            -webkit-tap-highlight-color: transparent;
        }

        .sidebar-backdrop.visible {
            background: rgba(0, 0, 0, 0.6);
            pointer-events: auto;
        }

        /* Sidebar as drawer on mobile */
        .theater-sidebar {
            position: fixed;
            left: 0;
            top: 0;
            bottom: 0;
            width: min(300px, 85vw);
            z-index: 100;
            transform: translateX(-100%);
            transition: transform var(--theater-transition-normal);
        }

        .theater.sidebar-open .theater-sidebar {
            transform: translateX(0);
        }

        /* Always show sidebar content on mobile (visibility controlled by transform) */
        .theater .sidebar-content {
            display: flex;
        }

        .theater .theater-title {
            display: block;
        }

        .theater .header-left {
            width: auto;
            justify-content: flex-start;
        }

        .theater .sidebar-header {
            justify-content: space-between;
            padding: 1rem;
        }

        /* Hide desktop collapse/expand buttons on mobile */
        .collapse-btn.desktop-only,
        .expand-btn.desktop-only {
            display: none !important;
        }

        /* Show mobile close button */
        .close-btn.mobile-only {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 44px;
            height: 44px;
            background: none;
            border: none;
            color: var(--theater-muted);
            cursor: pointer;
            border-radius: 8px;
            -webkit-tap-highlight-color: transparent;
        }

        .close-btn.mobile-only:hover {
            color: var(--theater-text);
            background: var(--theater-bg-elevated);
        }

        /* Stage needs top padding for the hamburger button */
        .theater-stage {
            padding-top: 60px;
        }

        /* When sidebar is open, no need for extra padding */
        .theater.sidebar-open .theater-stage {
            padding-top: 0;
        }
    }

    /* Utility classes */
    .desktop-only {
        /* Visible by default, hidden in mobile media query */
    }

    .mobile-only {
        display: none;
    }

    @media (max-width: 768px) {
        .desktop-only {
            display: none !important;
        }

        .mobile-only {
            display: flex;
        }
    }
</style>
