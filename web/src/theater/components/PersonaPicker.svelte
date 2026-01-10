<script lang="ts">
    import {tick} from "svelte";
    import {personas, type Persona} from "../stores/personas";

    interface Props {
        selectedPersonaId: number | null;
        onSelect: (personaId: number | null) => void;
    }

    let {selectedPersonaId, onSelect}: Props = $props();

    let isOpen = $state(false);
    let dropdownRef: HTMLElement;
    let listboxRef: HTMLElement;
    let toggleRef: HTMLElement;
    let focusedIndex = $state(-1);

    let userPersonas = $derived($personas);

    // Build options list: null (yourself) + all personas
    let allOptions = $derived<(Persona | null)[]>([null, ...userPersonas]);

    let selectedPersona = $derived(
        selectedPersonaId ? userPersonas.find((p) => p.id === selectedPersonaId) : null,
    );

    async function toggleDropdown() {
        isOpen = !isOpen;
        if (isOpen) {
            // Focus the currently selected option
            focusedIndex = allOptions.findIndex((opt) =>
                opt === null ? selectedPersonaId === null : opt.id === selectedPersonaId,
            );
            // Focus listbox after it renders
            await tick();
            listboxRef?.focus();
        }
    }

    function selectPersona(persona: Persona | null) {
        onSelect(persona?.id ?? null);
        isOpen = false;
        toggleRef?.focus();
    }

    function handleClickOutside(event: MouseEvent) {
        if (dropdownRef && !dropdownRef.contains(event.target as Node)) {
            isOpen = false;
        }
    }

    function handleKeydown(event: KeyboardEvent) {
        if (!isOpen) {
            if (event.key === "ArrowDown" || event.key === "ArrowUp" || event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                isOpen = true;
                focusedIndex = allOptions.findIndex((opt) =>
                    opt === null ? selectedPersonaId === null : opt.id === selectedPersonaId,
                );
            }
            return;
        }

        switch (event.key) {
            case "ArrowDown":
                event.preventDefault();
                focusedIndex = Math.min(focusedIndex + 1, allOptions.length - 1);
                break;
            case "ArrowUp":
                event.preventDefault();
                focusedIndex = Math.max(focusedIndex - 1, 0);
                break;
            case "Enter":
            case " ":
                event.preventDefault();
                if (focusedIndex >= 0 && focusedIndex < allOptions.length) {
                    selectPersona(allOptions[focusedIndex]);
                }
                break;
            case "Escape":
                event.preventDefault();
                isOpen = false;
                toggleRef?.focus();
                break;
            case "Home":
                event.preventDefault();
                focusedIndex = 0;
                break;
            case "End":
                event.preventDefault();
                focusedIndex = allOptions.length - 1;
                break;
        }
    }

    function getInitials(name: string): string {
        return name
            .split(" ")
            .map((word) => word[0])
            .join("")
            .toUpperCase()
            .slice(0, 2);
    }

    function getOptionId(index: number): string {
        return `persona-option-${index}`;
    }
</script>

<svelte:window onclick={handleClickOutside} />

<div class="persona-picker" bind:this={dropdownRef}>
    <button
        bind:this={toggleRef}
        class="picker-toggle"
        onclick={toggleDropdown}
        onkeydown={handleKeydown}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-label="Speaking as {selectedPersona?.name ?? 'yourself'}"
        aria-controls="persona-listbox"
    >
        {#if selectedPersona}
            {#if selectedPersona.avatar_url}
                <img
                    class="persona-avatar"
                    src={selectedPersona.avatar_url}
                    alt=""
                    aria-hidden="true"
                />
            {:else}
                <div
                    class="persona-avatar-placeholder"
                    style={selectedPersona.color ? `background: ${selectedPersona.color}` : ""}
                    aria-hidden="true"
                >
                    {getInitials(selectedPersona.name)}
                </div>
            {/if}
            <span class="persona-name" style={selectedPersona.color ? `color: ${selectedPersona.color}` : ""}>
                {selectedPersona.name}
            </span>
        {:else}
            <span class="persona-name self">Speaking as yourself</span>
        {/if}
        <span class="picker-caret" aria-hidden="true">{isOpen ? "▲" : "▼"}</span>
    </button>

    {#if isOpen}
        <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
        <ul
            bind:this={listboxRef}
            class="picker-dropdown"
            role="listbox"
            id="persona-listbox"
            aria-label="Select persona"
            aria-activedescendant={focusedIndex >= 0 ? getOptionId(focusedIndex) : undefined}
            tabindex="0"
            onkeydown={handleKeydown}
        >
            <!-- svelte-ignore a11y_click_events_have_key_events -->
            <li
                id={getOptionId(0)}
                class="persona-option"
                class:active={selectedPersonaId === null}
                class:focused={focusedIndex === 0}
                role="option"
                aria-selected={selectedPersonaId === null}
                onclick={() => selectPersona(null)}
            >
                <span class="option-name">Yourself</span>
            </li>

            {#if userPersonas.length > 0}
                <li class="dropdown-divider" role="separator" aria-hidden="true"></li>
                {#each userPersonas as persona, index}
                    {@const optionIndex = index + 1}
                    <!-- svelte-ignore a11y_click_events_have_key_events -->
                    <li
                        id={getOptionId(optionIndex)}
                        class="persona-option"
                        class:active={selectedPersonaId === persona.id}
                        class:focused={focusedIndex === optionIndex}
                        role="option"
                        aria-selected={selectedPersonaId === persona.id}
                        onclick={() => selectPersona(persona)}
                    >
                        {#if persona.avatar_url}
                            <img
                                class="option-avatar"
                                src={persona.avatar_url}
                                alt=""
                                aria-hidden="true"
                            />
                        {:else}
                            <div
                                class="option-avatar-placeholder"
                                style={persona.color ? `background: ${persona.color}` : ""}
                                aria-hidden="true"
                            >
                                {getInitials(persona.name)}
                            </div>
                        {/if}
                        <span
                            class="option-name"
                            style={persona.color ? `color: ${persona.color}` : ""}
                        >
                            {persona.name}
                        </span>
                    </li>
                {/each}
            {/if}
        </ul>
    {/if}
</div>

<style>
    .persona-picker {
        position: relative;
    }

    .picker-toggle {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 0.75rem;
        background: var(--theater-bg-elevated);
        border: 1px solid var(--theater-border);
        border-radius: 6px;
        color: var(--theater-text);
        cursor: pointer;
        font-family: var(--theater-font-ui);
        font-size: 0.85rem;
        transition: all var(--theater-transition-fast);
    }

    .picker-toggle:hover {
        border-color: var(--theater-accent);
    }

    .persona-avatar,
    .persona-avatar-placeholder {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        flex-shrink: 0;
    }

    .persona-avatar {
        object-fit: cover;
    }

    .persona-avatar-placeholder {
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--theater-muted);
        font-size: 0.6rem;
        font-weight: 600;
        color: var(--theater-bg);
    }

    .persona-name {
        max-width: 120px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .persona-name.self {
        color: var(--theater-muted);
        font-style: italic;
    }

    .picker-caret {
        font-size: 0.6rem;
        color: var(--theater-muted);
        margin-left: auto;
    }

    .picker-dropdown {
        position: absolute;
        bottom: 100%;
        left: 0;
        margin-bottom: 0.5rem;
        min-width: 180px;
        background: var(--theater-bg-elevated);
        border: 1px solid var(--theater-border);
        border-radius: 8px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
        overflow: hidden;
        z-index: 100;
        list-style: none;
        padding: 0;
        margin: 0 0 0.5rem 0;
    }

    .persona-option {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        width: 100%;
        padding: 0.6rem 0.75rem;
        background: none;
        border: none;
        color: var(--theater-text);
        cursor: pointer;
        font-family: var(--theater-font-ui);
        font-size: 0.85rem;
        text-align: left;
        transition: background var(--theater-transition-fast);
    }

    .persona-option:hover,
    .persona-option.focused {
        background: var(--theater-bg);
    }

    .persona-option.active {
        background: var(--theater-bg);
    }

    .persona-option.focused {
        outline: 2px solid var(--theater-accent);
        outline-offset: -2px;
    }

    .option-avatar,
    .option-avatar-placeholder {
        width: 20px;
        height: 20px;
        border-radius: 50%;
        flex-shrink: 0;
    }

    .option-avatar {
        object-fit: cover;
    }

    .option-avatar-placeholder {
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--theater-muted);
        font-size: 0.5rem;
        font-weight: 600;
        color: var(--theater-bg);
    }

    .option-name {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .dropdown-divider {
        height: 1px;
        background: var(--theater-border);
        margin: 0.25rem 0;
    }

    /* Mobile optimizations - compact toggle, full dropdown */
    @media (max-width: 768px) {
        .picker-toggle {
            padding: 0.4rem;
            border-radius: 50%;
            min-width: 44px;
            min-height: 44px;
            justify-content: center;
        }

        .persona-name,
        .picker-caret {
            display: none;
        }

        .persona-avatar,
        .persona-avatar-placeholder {
            width: 32px;
            height: 32px;
        }

        .persona-avatar-placeholder {
            font-size: 0.7rem;
        }

        /* Show user icon when speaking as self */
        .picker-toggle:has(.persona-name.self) {
            background: var(--theater-bg);
        }

        .picker-dropdown {
            min-width: 200px;
            max-width: calc(100vw - 2rem);
        }
    }
</style>
