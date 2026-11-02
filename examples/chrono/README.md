# Executable stopwatch example

This project applies NDF to a two-digit stopwatch. The event-level Python
model and acceptance tests are runnable. Physical button conditioning is
deliberately unfinished and appears as both an open question and a
verification coverage gap. No hardware implementation is claimed.

From the repository root:

```sh
python3 ndf.py --root examples/chrono/spec check
python3 ndf.py --root examples/chrono/spec trace CHR-000
python3 ndf.py --root examples/chrono/spec coverage
python3 ndf.py --root examples/chrono/spec status
python3 ndf.py --root examples/chrono/spec options
python3 -m unittest discover -s examples/chrono/spec/models -v
```

The manifest uses JSON syntax, which is also valid YAML. There are six
L1 must clauses: five behavioral requirements and `DEF-001`, a definition.
Four have verification links; `CTL-DEB-001` and `DEF-001` remain unverified.
Coverage includes definitions tagged L1/must, so authors must review the
reported gaps rather than treating every gap as a missing behavioral test.
Coverage counts verification links, not successful test executions.

`D-001` records rollover and event-priority choices. `Q-001` records the
remaining physical-input question; `PRM-DEB-001` lists candidate durations.
The tests exercise all 1,600 combinations of model count, running state,
and simultaneous event inputs, plus a fixed-seed 10,000-step sequence.
