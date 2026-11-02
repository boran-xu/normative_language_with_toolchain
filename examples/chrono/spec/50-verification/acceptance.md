# Acceptance criteria

These criteria have executable tests in `models/test_chrono.py`.
Their links describe verification intent; a coverage link alone does not
mean a test ran or passed.

## Control sequencing {#VER-CTL-001}
<!-- ndf: kind=verif level=must layer=L3 status=stable since=0.1 verifies=CTL-SS-001,CTL-RST-001 -->

The model MUST pass directed start, stop, resume, and reset sequences.
The tests MUST exercise every combination of reset, start/stop, and tick
from every count and both running states, checking the priority rule in
[[D-001]].

## Wrap and hold {#VER-CNT-002}
<!-- ndf: kind=verif level=must layer=L3 status=stable since=0.1 verifies=CNT-001,CNT-MOD-010 -->

From reset, the model MUST reach 99 after 99 running ticks, then 00 after
the hundredth tick while remaining running. Stopped ticks MUST hold the
count. A deterministic randomized test MUST compare 10,000 steps with an
independent transition table.

## BCD encoding {#VER-DSP-003}
<!-- ndf: kind=verif level=must layer=L3 status=stable since=0.1 verifies=DSP-001 -->

For every count from 00 through 99, both BCD digits MUST be in 0–9 and
their decoded value MUST equal the count.

No criterion yet verifies [[CTL-DEB-001]]; [[Q-001]] records that gap.
