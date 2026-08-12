"""Strategy interface note.

A strategy is simply anything matching `reference_engine.SignalFn`:
`Callable[[SimulationCursor], Action]`. Not a class hierarchy — the
contract already lives in reference_engine.py. Strategies below are
implemented as classes with `__call__` only when they need to memoize a
parameter (e.g. EMA periods) across calls, never to track "am I currently
in a position". That state belongs to the engine alone (see
reference_engine.py's no-pyramiding rule): a strategy that tried to track
its own position independently would risk desyncing from what the engine
actually filled (e.g. a BUY signal ignored because a prior position was
still open). Every strategy here is a pure function of `cursor.history` —
same inputs, same decision, always.
"""
