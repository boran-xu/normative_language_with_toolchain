# Stopwatch

## Intent {#CHR-000}
<!-- ndf: kind=arch level=must layer=L0 status=stable since=0.1 -->

The stopwatch measures elapsed whole seconds while running, controlled
by reset and start/stop inputs, with a two-digit decimal count.
This example models event-level behavior; physical switch conditioning
is explicitly unfinished ([[Q-001]]).

## Tick definition {#DEF-001}
<!-- ndf: kind=def level=must layer=L1 status=stable since=0.1 -->

A tick is one elapsed second. A button event is a conditioned, one-step
event, not a raw electrical input. BCD means one decimal digit per nibble.
