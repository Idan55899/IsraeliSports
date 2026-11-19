from ilfootball.core.ratelimit import HostRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make(clock: FakeClock) -> HostRateLimiter:
    return HostRateLimiter(lambda host: 3.0, jitter=0.0, clock=clock.time, sleep=clock.sleep)


def test_first_request_does_not_wait():
    clock = FakeClock()
    assert make(clock).wait("a.com") == 0.0
    assert clock.sleeps == []


def test_second_request_waits_remaining_interval():
    clock = FakeClock()
    limiter = make(clock)
    limiter.wait("a.com")
    clock.now += 1.0
    assert limiter.wait("a.com") == 2.0


def test_hosts_are_independent():
    clock = FakeClock()
    limiter = make(clock)
    limiter.wait("a.com")
    assert limiter.wait("b.com") == 0.0
