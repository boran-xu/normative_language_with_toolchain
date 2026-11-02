"""Acceptance tests linked by VER-CTL-001, VER-CNT-002, VER-DSP-003."""

import itertools
import random
import unittest

from chrono import Chrono


# Explicit control transition table, keyed by (running, startstop, tick).
# Values are (next running, increment); reset is a separate dominant case.
TRANSITIONS = {
    (False, False, False): (False, 0),
    (False, False, True): (False, 0),
    (False, True, False): (True, 0),
    (False, True, True): (True, 1),
    (True, False, False): (True, 0),
    (True, False, True): (True, 1),
    (True, True, False): (False, 0),
    (True, True, True): (False, 0),
}


class ChronoAcceptance(unittest.TestCase):
    def test_VER_CTL_001_start_stop_resume_and_reset(self):
        clock = Chrono()
        clock.step(tick=True)
        self.assertEqual((clock.count, clock.running), (0, False))
        clock.step(startstop=True)
        for _ in range(17):
            clock.step(tick=True)
        clock.step(startstop=True)
        for _ in range(20):
            clock.step(tick=True)
        self.assertEqual((clock.count, clock.running), (17, False))
        clock.step(startstop=True, tick=True)
        self.assertEqual((clock.count, clock.running), (18, True))
        clock.step(reset=True)
        self.assertEqual((clock.count, clock.running), (0, False))

    def test_VER_CNT_002_wrap(self):
        clock = Chrono()
        clock.step(startstop=True)
        for _ in range(99):
            clock.step(tick=True)
        self.assertEqual((clock.count, clock.running), (99, True))
        clock.step(tick=True)
        self.assertEqual((clock.count, clock.running), (0, True))

    def test_VER_CTL_001_every_state_and_simultaneous_event_combination(self):
        for count, running, reset, startstop, tick in itertools.product(
            range(100), (False, True), (False, True), (False, True), (False, True)
        ):
            with self.subTest(count=count, running=running, reset=reset,
                              startstop=startstop, tick=tick):
                clock = Chrono()
                clock.count, clock.running = count, running
                if reset:
                    expected = (0, False)
                else:
                    next_running, increment = TRANSITIONS[running, startstop, tick]
                    next_count = count + increment
                    expected = (0 if next_count == 100 else next_count, next_running)
                clock.step(reset=reset, startstop=startstop, tick=tick)
                self.assertEqual((clock.count, clock.running), expected)

    def test_VER_CTL_001_random_sequences_against_transition_table(self):
        clock = Chrono()
        expected_count, expected_running = 0, False
        rng = random.Random(1701)
        for step in range(10_000):
            reset, startstop, tick = (rng.choice((False, True)) for _ in range(3))
            if reset:
                expected_count, expected_running = 0, False
            else:
                expected_running, increment = TRANSITIONS[
                    expected_running, startstop, tick
                ]
                expected_count += increment
                if expected_count == 100:
                    expected_count = 0
            clock.step(reset=reset, startstop=startstop, tick=tick)
            self.assertEqual((clock.count, clock.running),
                             (expected_count, expected_running), f"step {step}")

    def test_VER_DSP_003_bcd_for_every_count(self):
        clock = Chrono()
        clock.step(startstop=True)
        for count in range(100):
            tens, units = clock.bcd
            self.assertTrue(0 <= tens <= 9 and 0 <= units <= 9)
            self.assertEqual(10 * tens + units, count)
            clock.step(tick=True)


if __name__ == "__main__":
    unittest.main()
