"""The wire format. Everything the library computes, and nothing rounded.

THIS MODULE IS WHERE THE PROJECT'S INVARIANTS EITHER SURVIVE THE NETWORK OR DIE
QUIETLY. Four of them, and each has an obvious encoding that breaks it:

  MISSING IS NOT ZERO. `None` means no record and `0` means somebody counted.
  JSON has `null` and `0` and keeps them apart, so the only way to lose this is
  to reach for a display helper on the way out. `interface.model._plain` turns
  None into `""` because it paints cells; using it here would fuse the two on
  the wire and no test downstream could tell them apart again.

  A RATIONAL IS NOT A FLOAT. Cover is `Fraction(73, 2)` exactly. `float()` is
  the one-character version of this whole file going wrong, and it would move
  rounding out of the renderer, where the project puts it, into transport,
  where nobody would look for it. So a rational crosses as its numerator and
  denominator and the display layer divides.

  UNBOUNDED IS AN ANSWER. Cover with nothing consuming it is settled, not
  absent. Encoding it as null would put an answered dimension in the caller's
  unknown pile.

  A PAIR IS NOT A RATIONAL. `wait_out_days` carries `(quoted, p95)`, which is a
  two-element sequence of ints, and so is a naive `[numerator, denominator]`.
  `render._measure` dodges that collision by ordering its branches; an API
  cannot, because the caller sees only the payload. So every non-plain value is
  TAGGED: a pair is a JSON array, a rational is an object with a `type`.

NO PROSE IS ENCODED FROM STORAGE. Sentences in a response are produced by
`render()` at request time, exactly as the Streamlit surface produces them. The
run store keeps inputs and never a rendered string, so a wording change reaches
a run recorded last month. That is CLAUDE.md's rule about the decision log,
applied to the transport layer it would otherwise leak through.
"""
from dataclasses import fields, is_dataclass
from fractions import Fraction

from .. import scoring

EXACT = "exact"
UNBOUNDED = "unbounded"

# Properties that are part of the answer but are not dataclass fields, named per
# type rather than discovered. Discovery by `dir()` would sweep up whatever a
# future property happens to be called, including one added for the painter's
# convenience, and the wire format would then change without anybody editing it.
#
# Keyed by class name to keep this module free of imports it does not need: the
# interface and concentration layers import scoring, and scoring must not learn
# about either.
EXTRA_PROPERTIES = {
    "DimensionScore": ("autonomy", "is_settled"),
    "ConcentrationScore": ("autonomy", "is_settled"),
    "Row": ("is_actionable",),
    "Evidence": ("absent_finished_goods", "sources_used"),
    "Citation": ("locator",),
    "Cluster": ("size", "is_concentrated", "autonomy"),
    "Coverage": ("is_empty",),
    "Transformation": ("changes_supplier_count",),
}


def encode(value):
    """Any value the library produces, as JSON-ready data. Never as prose.

    Deliberately recursive and deliberately total: an unrecognised type reaches
    the `str()` at the foot and is visible in the payload as a string, rather
    than raising and taking a 296-part response down over one field. The tests
    assert the shape of every type that actually occurs, so an unrecognised one
    is a gap in this map rather than an outage.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        # bool BEFORE int is not needed here because both pass through, but the
        # order matters if anybody ever adds a branch: `isinstance(True, int)`.
        return value
    if value is scoring.UNBOUNDED:
        return {"type": UNBOUNDED}
    if isinstance(value, Fraction):
        # NO FLOAT. The display layer divides these; transport does not.
        return {"type": EXACT, "numerator": value.numerator,
                "denominator": value.denominator}
    if isinstance(value, dict):
        return {str(key): encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        ordered = sorted(value, key=str) if isinstance(
            value, (set, frozenset)) else value
        return [encode(item) for item in ordered]
    if is_dataclass(value):
        out = {field.name: encode(getattr(value, field.name))
               for field in fields(value)}
        for name in _extra_properties_for(value):
            attribute = getattr(value, name)
            out[name] = encode(attribute() if callable(attribute)
                               else attribute)
        return out
    return str(value)


def _extra_properties_for(value):
    """Extras for this class or the nearest ancestor that declares them.

    `ConcentrationScore` subclasses `DimensionScore` and PINS `autonomy` rather
    than deriving it, so it is named in its own right above. The walk exists so
    that a future subclass inherits its parent's extras instead of silently
    dropping them, which would drop an autonomy level from a payload.
    """
    for klass in type(value).__mro__:
        if klass.__name__ in EXTRA_PROPERTIES:
            return EXTRA_PROPERTIES[klass.__name__]
    return ()
