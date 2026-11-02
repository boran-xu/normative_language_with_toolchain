"""Normative event-level stopwatch model; see CNT-MOD-010.

This does not model clock division, synchronizers, or physical debounce.
"""


class Chrono:
    def __init__(self):
        self.count = 0
        self.running = False

    def step(self, *, reset=False, startstop=False, tick=False):
        """Apply one set of simultaneous events according to D-001."""
        if reset:
            self.count = 0
            self.running = False
            return
        if startstop:
            self.running = not self.running
        if tick and self.running:
            self.count = (self.count + 1) % 100

    @property
    def bcd(self):
        return divmod(self.count, 10)
