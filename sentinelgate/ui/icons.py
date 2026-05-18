"""SVG icon primitives for SentinelGate's UI.

A single source of truth for every glyph the app renders. All icons are
1.5-stroke outlines using ``currentColor`` so they inherit the text color
of their container — this keeps the icon palette consistent across pills,
buttons, headers, and chips without per-callsite styling.

Design rationale (see ``skills/ui-ux-design-taste``):
    * Anti-emoji policy: emojis are banned in production UI surfaces.
    * Icons must be SVG primitives, not bitmap, so they scale crisply on
      Retina displays and high-DPI projectors used during demos.
    * Single stroke-width (1.5) for typographic consistency.

Sizing is controlled by CSS in ``app.py``:
    * ``.sg-hero-shield svg`` -> 44x44
    * ``.sg-pill svg`` -> 12x12
    * ``.sg-risk-label svg`` -> 12x12
    * ``.sg-flag-chip svg`` -> 11x11
    * ``.sg-icon`` -> inline-block helper for ad-hoc placements

Each public name returns a complete ``<svg>...</svg>`` string ready to be
interpolated into ``st.markdown(..., unsafe_allow_html=True)``. They are
strings (not functions) because they take no parameters — keep it simple.
"""

from __future__ import annotations


def _svg(body: str, size: int = 16, view: int = 24) -> str:
    """Wrap a path/group body in a viewBox-driven SVG container.

    ``size`` only sets the default width/height for ad-hoc placements;
    most call sites are sized by parent CSS (``.sg-pill svg``, etc.).
    """
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {view} {view}" fill="none" stroke="currentColor" '
        f'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" '
        f'class="sg-icon" aria-hidden="true" focusable="false">{body}</svg>'
    )


# ---------------------------------------------------------------------------
# Hero / branding
# ---------------------------------------------------------------------------

# Stylised security shield with an inner check — the brand mark.
SHIELD = _svg(
    '<path d="M12 2 L4 5 V11 C4 16.5 7.5 20.5 12 22 C16.5 20.5 20 16.5 20 11 V5 Z" />'
    '<path d="M9 12 L11 14 L15.5 9.5" />',
    size=44,
)

# Variant without the inner check, used inside the "inspecting" spinner where
# the shield is decorative rather than confirmatory.
SHIELD_PLAIN = _svg(
    '<path d="M12 2 L4 5 V11 C4 16.5 7.5 20.5 12 22 C16.5 20.5 20 16.5 20 11 V5 Z" />',
)


# ---------------------------------------------------------------------------
# Decision pills (Allow / Block / Agent / Compliance / Threat report)
# ---------------------------------------------------------------------------

# Circle with check — Allow pill.
CHECK_CIRCLE = _svg(
    '<circle cx="12" cy="12" r="9" />'
    '<path d="M8 12 L11 15 L16 9" />',
)

# Circle with diagonal slash — Block pill (universal "no" / "ban" mark).
BAN = _svg(
    '<circle cx="12" cy="12" r="9" />'
    '<path d="M6.5 6.5 L17.5 17.5" />',
)

# Person/agent silhouette — Agent pill.
USER = _svg(
    '<circle cx="12" cy="8" r="3.5" />'
    '<path d="M5 20 C5 16 8 14 12 14 C16 14 19 16 19 20" />',
)

# Clipboard with a check — Compliance citation.
CLIPBOARD_CHECK = _svg(
    '<path d="M9 4 H15 V6 H9 Z" />'
    '<path d="M6 6 H18 V20 H6 Z" />'
    '<path d="M9 13 L11 15 L15 11" />',
)

# Magnifying glass — Threat intelligence expander.
SEARCH = _svg(
    '<circle cx="11" cy="11" r="6.5" />'
    '<path d="M16 16 L20.5 20.5" />',
)


# ---------------------------------------------------------------------------
# Flag chips & status indicators
# ---------------------------------------------------------------------------

# Bare X — flag chips (a single rule violation).
X_MARK = _svg(
    '<path d="M6 6 L18 18" />'
    '<path d="M18 6 L6 18" />',
)

# Solid filled dot — "live" status (sidebar ACTIVE, Lobster Trap running).
# Filled by stroke + a tiny radius rather than fill="currentColor" so it
# inherits color exactly like the outlines do.
DOT_FILLED = _svg('<circle cx="12" cy="12" r="4" fill="currentColor" stroke="none" />')

# Hollow ring — "offline" status (Lobster Trap unreachable, fallback active).
DOT_HOLLOW = _svg('<circle cx="12" cy="12" r="4" />')

# Alert triangle — used in the API-key-missing st.error banner.
ALERT_TRIANGLE = _svg(
    '<path d="M12 3 L21 19 H3 Z" />'
    '<path d="M12 10 V14" />'
    '<circle cx="12" cy="17" r="0.6" fill="currentColor" stroke="none" />',
)


# ---------------------------------------------------------------------------
# Tab + page section icons
# ---------------------------------------------------------------------------

# Chat bubble — Chat & Inspect tab.
CHAT = _svg(
    '<path d="M4 5 H20 V16 H13 L9 20 V16 H4 Z" />'
)

# Gear/settings — Policy Manager tab.
GEAR = _svg(
    '<circle cx="12" cy="12" r="3" />'
    '<path d="M12 3 V5 M12 19 V21 M3 12 H5 M19 12 H21 '
    'M5.6 5.6 L7 7 M17 17 L18.4 18.4 M5.6 18.4 L7 17 M17 7 L18.4 5.6" />'
)

# Bar chart — Audit Dashboard tab.
CHART_BAR = _svg(
    '<path d="M4 20 H20" />'
    '<path d="M7 20 V13" />'
    '<path d="M12 20 V9" />'
    '<path d="M17 20 V15" />'
)

# Classical pillar / landmark — Compliance Policy Packs subheader.
LANDMARK = _svg(
    '<path d="M3 9 L12 4 L21 9" />'
    '<path d="M5 9 V18 M9 9 V18 M15 9 V18 M19 9 V18" />'
    '<path d="M3 20 H21" />'
)


# ---------------------------------------------------------------------------
# Button / action icons (used in markdown context only — st.button labels
# render plain text, so emoji removal there means dropping the icon)
# ---------------------------------------------------------------------------

# CPU / processor — the threat-intel spinner where Gemini does the work.
CPU = _svg(
    '<rect x="6" y="6" width="12" height="12" rx="2" />'
    '<rect x="9.5" y="9.5" width="5" height="5" />'
    '<path d="M9 3 V6 M15 3 V6 M9 18 V21 M15 18 V21 '
    'M3 9 H6 M3 15 H6 M18 9 H21 M18 15 H21" />'
)

# Lightning bolt — Load Attack Scenario.
BOLT = _svg('<path d="M13 3 L5 14 H11 L9 21 L18 9 H12 Z" />')

# Refresh / rotate — Reset Demo.
REFRESH = _svg(
    '<path d="M4 12 A8 8 0 0 1 18.5 7.5" />'
    '<path d="M18.5 4 V8 H14.5" />'
    '<path d="M20 12 A8 8 0 0 1 5.5 16.5" />'
    '<path d="M5.5 20 V16 H9.5" />'
)

# Plus — Add a new policy.
PLUS = _svg('<path d="M12 5 V19 M5 12 H19" />')

# Tray-with-down-arrow — Export CSV.
DOWNLOAD = _svg(
    '<path d="M12 4 V15" />'
    '<path d="M7 11 L12 16 L17 11" />'
    '<path d="M4 20 H20" />'
)


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

__all__ = [
    "ALERT_TRIANGLE",
    "BAN",
    "BOLT",
    "CHART_BAR",
    "CHAT",
    "CHECK_CIRCLE",
    "CLIPBOARD_CHECK",
    "CPU",
    "DOT_FILLED",
    "DOT_HOLLOW",
    "DOWNLOAD",
    "GEAR",
    "LANDMARK",
    "PLUS",
    "REFRESH",
    "SEARCH",
    "SHIELD",
    "SHIELD_PLAIN",
    "USER",
    "X_MARK",
]
