from __future__ import annotations
from fastapi import Depends
from .services.state import AppState, get_state

def state_dep() -> AppState:
    return get_state()
