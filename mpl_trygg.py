"""
mpl_trygg.py
Gjer matplotlib sin mathtext-parser trådsikker.

Streamlit køyrer kvar økt/omkøyring i ein eigen tråd. Mathtext-parseren i
matplotlib (bygd på pyparsing) deler intern tilstand og er ikkje trådsikker:
når to tråder teiknar formlar ($f_\\mathrm{ck}$ osb.) samstundes, kan ein av
dei feile med «ValueError … ParseException». Det skjer typisk når ein byter
fane medan førre omkøyring framleis teiknar.

Løysing: all parsing av mathtext går gjennom éin felles lås.
Importer denne modulen før noko vert teikna (gjort øvst i app.py).
"""

import threading

import matplotlib.mathtext as _mathtext

_LAAS = threading.RLock()

if not getattr(_mathtext.MathTextParser.parse, "_trygg", False):
    _original_parse = _mathtext.MathTextParser.parse

    def _trygg_parse(self, *args, **kwargs):
        with _LAAS:
            return _original_parse(self, *args, **kwargs)

    _trygg_parse._trygg = True
    _mathtext.MathTextParser.parse = _trygg_parse
