# Memory Blueprint "One dock": shots for Art (branch alto-bpdock-beta)

Headless Chromium, the PMA test plan, after Fit (key 0). The phone shots are synthetic: the `mobile` class is added after load, so the
Outside tab and Fit button show the computer's icons there. A real phone (Home Desktop: Safari + iPhone Simulator) shows text.

- `classic-light-1440`, `classic-dark-1440`, `classic-768`, `window-360`: the dock on a computer; the plan stands above it.
- `retro-1440`, `retro-768`: the Retro "WALK" bug fixed. Retro's name cartouche (#sk-mark) drew over the dock's zoom buttons
  and the "3" tab; it is now hidden while the blueprint is open (like the World map's Tour bar).
- `phone-390-before` / `phone-390-after`: **phone change, for Luke to see first.** The shipped phone layout's Fit ran the plan
  under the right rail's zoom buttons (the 30px gutter was narrower than the 58px rail). Now the right gutter is the rail's
  width and the left keeps 30px, so the plan keeps about its old size and moves left, clear of the rail. Nothing removed.
- `phone-preview-390`, `phone-preview-360`: the dock on a phone with `html.bl-dock-phone` (Luke's try-it switch, not on by
  default). The plan and the chips now stay above the dock there too.
