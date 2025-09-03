from decimal import Decimal, ROUND_DOWN, ROUND_UP

def round_step(value: float, step: float, precision: int = 8) -> float:
    if step == 0:
        return float(value)
    v = Decimal(str(value)); s = Decimal(str(step))
    q = (v // s) * s
    return float(q.quantize(Decimal(10) ** -precision, rounding=ROUND_DOWN))

def round_step_up(value: float, step: float, precision: int = 8) -> float:
    v = Decimal(str(value)); s = Decimal(str(step))
    if s == 0:
        return float(v)
    if (v % s) == 0:
        q = v
    else:
        q = ((v // s) + 1) * s
    return float(q.quantize(Decimal(10) ** -precision, rounding=ROUND_UP))
