<script lang="ts">
    import {createEventDispatcher, onMount} from "svelte";

    import * as api from "../api/client";
    import {activePersonaId} from "../stores/personas";

    import PersonaPicker from "./PersonaPicker.svelte";

    interface Props {
        streamId: number;
        topic: string;
    }

    let {streamId, topic}: Props = $props();

    const dispatch = createEventDispatcher<{
        messageSent: {id: number};
    }>();

    let content = $state("");
    let textareaElement: HTMLTextAreaElement;
    let isSending = $state(false);
    let sendError = $state<string | null>(null);
    let typingTimeout: ReturnType<typeof setTimeout> | null = null;
    let isTyping = $state(false);

    function handlePersonaSelect(personaId: number | null) {
        activePersonaId.set(personaId);
    }

    function dismissError() {
        sendError = null;
    }

    async function sendMessage() {
        const trimmedContent = content.trim();
        if (!trimmedContent || isSending) return;

        isSending = true;
        sendError = null;
        stopTypingNotification();

        try {
            const result = await api.sendMessage({
                type: "stream",
                to: streamId,
                topic,
                content: trimmedContent,
                persona_id: $activePersonaId ?? undefined,
            });

            content = "";
            dispatch("messageSent", {id: result.id});
            autoResize();
        } catch (error) {
            console.error("Failed to send message:", error);
            sendError = "Failed to send message. Please try again.";
        } finally {
            isSending = false;
        }
    }

    function handleKeydown(event: KeyboardEvent) {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        } else if (event.key === "Escape") {
            event.preventDefault();
            textareaElement?.blur();
        } else if (event.key === "ArrowLeft") {
            // At start of textarea, move focus to sidebar
            if (textareaElement?.selectionStart === 0 && textareaElement?.selectionEnd === 0) {
                event.preventDefault();
                textareaElement?.blur();
                // Focus first focusable element in sidebar
                const sidebarLink = document.querySelector<HTMLElement>(".theater-sidebar a, .theater-sidebar button");
                sidebarLink?.focus();
            }
        }
    }

    function handleInput() {
        autoResize();
        startTypingNotification();
    }

    function autoResize() {
        if (textareaElement) {
            textareaElement.style.height = "auto";
            textareaElement.style.height = `${Math.min(textareaElement.scrollHeight, 200)}px`;
        }
    }

    function startTypingNotification() {
        if (!isTyping && content.trim()) {
            isTyping = true;
            api.sendTypingNotification("start", streamId, topic).catch(() => {});
        }

        // Reset timeout
        if (typingTimeout) {
            clearTimeout(typingTimeout);
        }
        typingTimeout = setTimeout(() => {
            stopTypingNotification();
        }, 5000);
    }

    function stopTypingNotification() {
        if (isTyping) {
            isTyping = false;
            api.sendTypingNotification("stop", streamId, topic).catch(() => {});
        }
        if (typingTimeout) {
            clearTimeout(typingTimeout);
            typingTimeout = null;
        }
    }

    onMount(() => {
        textareaElement?.focus();
        return () => stopTypingNotification();
    });

    // Refocus when scene changes
    $effect(() => {
        if (streamId && topic) {
            textareaElement?.focus();
        }
    });

    function handleGlobalKeydown(event: KeyboardEvent) {
        // Don't trigger if already in an input
        const target = event.target as HTMLElement;
        if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) {
            return;
        }

        // 'c' or '/' to focus compose
        if (event.key === "c" || event.key === "/") {
            event.preventDefault();
            textareaElement?.focus();
        }
    }
</script>

<svelte:window onkeydown={handleGlobalKeydown} />

<div class="prompter">
    {#if sendError}
        <div class="send-error" role="alert">
            <span class="error-text">{sendError}</span>
            <button class="dismiss-error" onclick={dismissError} type="button" aria-label="Dismiss error">
                <span aria-hidden="true">×</span>
            </button>
        </div>
    {/if}

    <div class="prompter-row">
        <PersonaPicker selectedPersonaId={$activePersonaId} onSelect={handlePersonaSelect} />

        <div class="prompter-input-wrapper">
            <textarea
                bind:this={textareaElement}
                bind:value={content}
                onkeydown={handleKeydown}
                oninput={handleInput}
                placeholder="Speak your lines..."
                rows="1"
                disabled={isSending}
                aria-label="Message content"
            ></textarea>
            <div class="prompter-hints-bar">
                <span class="prompter-hints" aria-hidden="true">
                    <kbd>Enter</kbd> send · <kbd>Esc</kbd> blur · <kbd>c</kbd> focus · <kbd>s</kbd> sidebar
                </span>
            </div>
        </div>

        <button
            class="send-button"
            onclick={sendMessage}
            disabled={!content.trim() || isSending}
            type="button"
            aria-label="Send message"
        >
            {#if isSending}
                <span class="sending-indicator"></span>
            {:else}
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                    <path d="M22 2L11 13" />
                    <path d="M22 2L15 22L11 13L2 9L22 2Z" />
                </svg>
            {/if}
        </button>
    </div>
</div>

<style>
    .prompter {
        padding: 1rem 1.5rem calc(1.25rem + var(--theater-safe-area-bottom, 0px));
        padding-left: calc(1.5rem + var(--theater-safe-area-left, 0px));
        padding-right: calc(1.5rem + var(--theater-safe-area-right, 0px));
        background: var(--theater-bg-elevated);
        border-top: 1px solid var(--theater-border);
    }

    .prompter-row {
        display: grid;
        grid-template-columns: auto 1fr auto;
        align-items: center;
        gap: 1rem;
        width: 100%;
    }

    .prompter-input-wrapper {
        position: relative;
        width: 100%;
        min-width: 0;
        display: flex;
        flex-direction: column;
        background: var(--theater-bg);
        border: 1px solid var(--theater-border);
        border-radius: 12px;
        transition: border-color var(--theater-transition-fast);
    }

    .prompter-input-wrapper:focus-within {
        border-color: var(--theater-accent);
    }

    textarea {
        width: 100%;
        padding: 0.875rem 1rem;
        background: transparent;
        border: none;
        border-radius: 12px 12px 0 0;
        color: var(--theater-text);
        font-family: var(--theater-font-narrative);
        font-size: 1rem;
        line-height: 1.5;
        resize: none;
        min-height: 60px;
        max-height: 180px;
        box-sizing: border-box;
    }

    textarea:focus {
        outline: none;
    }

    textarea::placeholder {
        color: var(--theater-muted);
        font-style: italic;
    }

    textarea:disabled {
        opacity: 0.6;
    }

    /* Subtle scrollbar for textarea */
    textarea::-webkit-scrollbar {
        width: 6px;
    }

    textarea::-webkit-scrollbar-track {
        background: transparent;
    }

    textarea::-webkit-scrollbar-thumb {
        background: var(--theater-border);
        border-radius: 3px;
    }

    textarea::-webkit-scrollbar-thumb:hover {
        background: var(--theater-muted);
    }

    .send-button {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 48px;
        height: 48px;
        background: var(--theater-accent);
        border: none;
        border-radius: 50%;
        color: white;
        cursor: pointer;
        transition: all var(--theater-transition-fast);
    }

    .send-button:hover:not(:disabled) {
        background: var(--theater-accent-hover);
    }

    .send-button:disabled {
        background: var(--theater-border);
        cursor: not-allowed;
        opacity: 0.6;
    }

    .sending-indicator {
        width: 20px;
        height: 20px;
        border: 2px solid transparent;
        border-top-color: white;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
    }

    @keyframes spin {
        to {
            transform: rotate(360deg);
        }
    }

    .send-error {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 0.75rem;
        padding: 0.5rem 0.75rem;
        background: rgba(220, 38, 38, 0.15);
        border: 1px solid rgba(220, 38, 38, 0.3);
        border-radius: 6px;
    }

    .error-text {
        font-family: var(--theater-font-ui);
        font-size: 0.85rem;
        color: #f87171;
    }

    .dismiss-error {
        background: none;
        border: none;
        color: #f87171;
        cursor: pointer;
        font-size: 1.2rem;
        line-height: 1;
        padding: 0 0.25rem;
        opacity: 0.7;
        transition: opacity var(--theater-transition-fast);
        min-height: auto;
        min-width: auto;
    }

    .dismiss-error:hover {
        opacity: 1;
    }

    .prompter-hints-bar {
        display: flex;
        justify-content: flex-end;
        padding: 0.35rem 0.75rem;
        border-top: 1px solid var(--theater-border);
        background: var(--theater-bg);
        border-radius: 0 0 11px 11px;
    }

    .prompter-hints {
        font-family: var(--theater-font-ui);
        font-size: 0.7rem;
        color: var(--theater-muted);
        opacity: 0.7;
    }

    .prompter-hints kbd {
        display: inline-block;
        padding: 0.1rem 0.3rem;
        background: var(--theater-bg-elevated);
        border: 1px solid var(--theater-border);
        border-radius: 3px;
        font-family: var(--theater-font-ui);
        font-size: 0.65rem;
    }

    /* Mobile optimizations */
    @media (max-width: 768px) {
        .prompter {
            padding: 0.75rem 1rem calc(1rem + var(--theater-safe-area-bottom, 0px));
            padding-left: calc(1rem + var(--theater-safe-area-left, 0px));
            padding-right: calc(1rem + var(--theater-safe-area-right, 0px));
        }

        .prompter-row {
            gap: 0.5rem;
        }

        .prompter-hints-bar {
            display: none;
        }

        .prompter-input-wrapper {
            border-radius: 8px;
        }

        textarea {
            padding: 0.75rem;
            min-height: 44px;
            border-radius: 8px;
            font-size: 16px; /* Prevent iOS zoom on focus */
        }

        .send-button {
            width: 44px;
            height: 44px;
        }
    }
</style>
