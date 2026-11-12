"""Touch sizes on a phone (chunk 7 of ORG/phone-ui-audit-1111.md, rows H2 and F2's buttons): 44 pt to touch, nothing changed to see.

The controls below are drawn 28 to 34 px (the homepage's corner buttons and tile share button, a card's symbol buttons, the Focus button, the step bar's
buttons, the Overview's close bar). On a touch screen each takes an invisible ::after (or ::before where ::after is its tooltip) that reaches out to
44 pt, so the finger's target grows and the drawing does not move. Only where the pointer is coarse: a mouse keeps the exact shapes.
The clef (MENU, 27 x 34) is an <svg>, which takes no pseudo-element: it is listed in the audit follow-ups, not changed here.
The CSS rides in the phone shell's <head> block (phone_shell.head_block), so it is on every timeline page and the homepage."""

_HIT = "content:'';position:absolute;"
CSS = ("@media (pointer:coarse){"
       # already positioned (absolute corner / tile buttons): 34 -> 46, 30 -> 44
       ":is(#mode-toggle,#bg-toggle,#info-icon)::after{" + _HIT + "inset:-6px;}"
       "#account-btn::before{" + _HIT + "inset:-6px;}"                             # (the homepage blanks its ::after, once a tooltip)
       ".slab-share::after{" + _HIT + "inset:-7px;}"
       "#af-btn::before{" + _HIT + "inset:-5px;}"                                  # (::after is its tooltip)
       # in the flow: made a positioning box first (no offsets, so nothing moves)
       ":is(.csym-btn,.esym-btn,#summary-close-bar button){position:relative;}"
       ".csym-btn::after{" + _HIT + "inset:-5px;}"
       ".esym-btn::after{" + _HIT + "inset:-7px -8px;}"
       "#summary-close-bar button::after{" + _HIT + "inset:-9px 0;}"
       # the step bar's rail: 12 px tall, its thumb 10 px
       "#lanes-nav .lnv-rail::after{" + _HIT + "inset:-16px 0;}"
       "}")
