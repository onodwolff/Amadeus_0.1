from backend.app.services.utils import round_step, round_step_up


def test_round_step():
    assert round_step(1.2345, 0.01) == 1.23
    assert round_step(1.2345, 0.1) == 1.2


def test_round_step_up():
    assert round_step_up(1.2345, 0.01) == 1.24
    assert round_step_up(1.23, 0.01) == 1.23
    assert round_step_up(1.23, 0) == 1.23
