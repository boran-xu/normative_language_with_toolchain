# Controls

## Start and stop {#CTL-SS-001}
<!-- ndf: kind=req level=must layer=L1 status=stable since=0.1 refines=CHR-000 -->

A start/stop event MUST toggle running. Stopping MUST preserve the count.
When start/stop and tick coincide, the new running state MUST determine
whether to count that tick ([[D-001]]).

## Reset {#CTL-RST-001}
<!-- ndf: kind=req level=must layer=L1 status=stable since=0.1 refines=CHR-000 -->

Reset MUST set the count to zero and running to false. Reset MUST take
priority over start/stop and tick in the same step ([[D-001]]).

## Physical button conditioning {#CTL-DEB-001}
<!-- ndf: kind=req level=must layer=L1 status=draft since=0.1 refines=CHR-000 -->

Each physical button press MUST yield one conditioned event. The debounce
interval is ⟨TBD: resolve [[Q-001]]⟩. The event-level model does not implement
electrical conditioning.
