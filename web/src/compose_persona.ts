import $ from "jquery";

import render_compose_persona_menu from "../templates/compose_persona_menu.hbs";

import * as compose_state from "./compose_state.ts";
import * as personas from "./personas.ts";
import * as popover_menus from "./popover_menus.ts";
import * as ui_util from "./ui_util.ts";

export function get_current_persona_id(): number | null {
    return personas.get_compose_persona_id();
}

export function set_current_persona_id(persona_id: number | null): void {
    // Update the sticky selection for the current stream
    const stream_id = compose_state.stream_id();
    personas.set_compose_persona_id(persona_id, stream_id);
    update_selector_display();
}

function update_selector_display(): void {
    const $selector = $("#compose-persona-selector");
    const $button = $selector.find(".persona-selector-button");
    const $avatar = $button.find(".persona-avatar");
    const $name = $button.find(".persona-name");

    const current_persona_id = personas.get_compose_persona_id();

    if (current_persona_id === null) {
        // Posting as yourself
        $avatar.html('<i class="fa fa-user" aria-hidden="true"></i>');
        $name.text("Yourself");
        $name.css("color", "");
        $button.removeClass("using-persona");
    } else {
        // Posting as a persona
        const my_personas = personas.get_my_personas();
        const persona = my_personas.find((p) => p.id === current_persona_id);
        if (persona) {
            if (persona.avatar_url) {
                $avatar.html(`<img src="${persona.avatar_url}" alt="" class="persona-avatar-img" />`);
            } else {
                const initial = persona.name.charAt(0).toUpperCase();
                const style = persona.color ? `style="background-color: ${persona.color}"` : "";
                $avatar.html(`<span class="persona-avatar-initial" ${style}>${initial}</span>`);
            }
            $name.text(persona.name);
            if (persona.color) {
                $name.css("color", persona.color);
            } else {
                $name.css("color", "");
            }
            $button.addClass("using-persona");
        } else {
            // Persona no longer exists, reset to yourself
            set_current_persona_id(null);
        }
    }
}

export function show_selector(): void {
    const $selector = $("#compose-persona-selector");
    $selector.show();
}

export function hide_selector(): void {
    const $selector = $("#compose-persona-selector");
    $selector.hide();
}

export function update_for_stream(stream_id: number | undefined): void {
    if (stream_id === undefined) {
        // DM - reset persona to "Yourself" and show selector if user has personas
        // We don't want personas to accidentally carry over to DMs
        personas.set_compose_persona_id(null, undefined);
        update_selector_display();

        const my_personas = personas.get_my_personas();
        if (my_personas.length > 0) {
            show_selector();
        } else {
            hide_selector();
        }
        return;
    }

    // Check if user has any personas
    if (!personas.has_fetched_my_personas()) {
        personas.fetch_my_personas(() => {
            update_for_stream(stream_id);
        });
        return;
    }

    const my_personas = personas.get_my_personas();
    if (my_personas.length === 0) {
        hide_selector();
        return;
    }

    show_selector();

    // Restore sticky selection for this stream
    const sticky_persona = personas.get_sticky_persona_for_stream(stream_id);
    if (sticky_persona !== null) {
        // Set it without updating sticky (it's already sticky)
        personas.set_compose_persona_id(sticky_persona, stream_id);
    }
    update_selector_display();
}

function show_persona_menu(reference_element: HTMLElement): void {
    const my_personas = personas.get_my_personas();
    const current_persona_id = personas.get_compose_persona_id();

    const menu_items = [
        {
            id: null,
            name: "Yourself",
            avatar_url: null,
            color: null,
            is_yourself: true,
            is_selected: current_persona_id === null,
        },
        ...my_personas.map((p) => ({
            id: p.id,
            name: p.name,
            avatar_url: p.avatar_url,
            color: p.color,
            is_yourself: false,
            is_selected: current_persona_id === p.id,
            name_initial: p.name.charAt(0).toUpperCase(),
        })),
    ];

    const html = render_compose_persona_menu({personas: menu_items});

    popover_menus.toggle_popover_menu(reference_element, {
        theme: "popover-menu",
        placement: "top-start",
        onCreate(instance) {
            instance.setContent(ui_util.parse_html(html));
            $(instance.popper).addClass("persona-menu-popover");
        },
        onShow(instance) {
            const $content = $(instance.popper);

            $content.on("click", ".persona-menu-item", function (e) {
                e.preventDefault();
                const persona_id = $(this).attr("data-persona-id");
                if (persona_id === "null" || persona_id === undefined) {
                    set_current_persona_id(null);
                } else {
                    set_current_persona_id(Number.parseInt(persona_id, 10));
                }
                instance.hide();
            });
        },
        onHidden(instance) {
            instance.destroy();
        },
    });
}

// Callback for when personas change (via events)
function on_personas_changed(): void {
    // Update the selector display in case the selected persona was modified or deleted
    update_selector_display();

    // Also update visibility based on whether user now has any personas
    const stream_id = compose_state.stream_id();
    update_for_stream(stream_id);
}

export function cycle_persona(): void {
    // Cycle through personas: Yourself -> Persona 1 -> Persona 2 -> ... -> Yourself
    const my_personas = personas.get_my_personas();
    if (my_personas.length === 0) {
        return;
    }

    const current_persona_id = personas.get_compose_persona_id();

    if (current_persona_id === null) {
        // Currently "Yourself", switch to first persona
        set_current_persona_id(my_personas[0]!.id);
    } else {
        // Find current index and move to next
        const current_index = my_personas.findIndex((p) => p.id === current_persona_id);
        if (current_index === -1 || current_index === my_personas.length - 1) {
            // Not found or at last persona, go back to "Yourself"
            set_current_persona_id(null);
        } else {
            // Move to next persona
            set_current_persona_id(my_personas[current_index + 1]!.id);
        }
    }
}

export function initialize(): void {
    // Register callback for persona changes
    personas.register_change_callback(on_personas_changed);

    // Fetch personas on init
    personas.fetch_my_personas();

    // Handle clicks on the persona selector button
    $("body").on("click", ".persona-selector-button", function (e) {
        e.preventDefault();
        e.stopPropagation();
        show_persona_menu(this);
    });

    // Reset persona selection when compose closes
    $(document).on("compose_canceled.zulip", () => {
        // Don't reset - keep the sticky selection
    });

    // Update selector when compose is started or stream changes
    $(document).on("compose_started.zulip narrow_changed.zulip", () => {
        const stream_id = compose_state.stream_id();
        update_for_stream(stream_id);
    });
}
