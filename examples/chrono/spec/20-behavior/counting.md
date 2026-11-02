# Counting

## Counting contract {#CNT-001}
<!-- ndf: kind=req level=must layer=L1 status=stable since=0.1 refines=CHR-000 -->

Each tick while running MUST increment the count by one; stopped ticks
MUST leave it unchanged. Incrementing 99 MUST wrap to 00 ([[D-001]]).

## Counter mechanism {#CNT-MOD-010}
<!-- ndf: kind=req level=must layer=L2 status=stable since=0.1 refines=CNT-001 model=models/chrono.py -->

The model MUST use a modulo-100 integer counter. The linked executable
model is authoritative for event ordering under [[CTL-RST-001]] and
[[CTL-SS-001]], not for hardware timing or debounce.

## BCD display {#DSP-001}
<!-- ndf: kind=req level=must layer=L1 status=stable since=0.1 refines=CHR-000 -->

The display MUST expose the tens and units digits of the current count
as two BCD values, each in 0–9 ([[DEF-001]]).
