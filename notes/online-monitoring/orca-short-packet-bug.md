# `OrcaStreamer.load_packet_header` mis-frames short-form records (wrong-direction seek)

## Summary

`OrcaStreamer.load_packet_header` reads two 32-bit words (8 bytes) for every
packet header, then for a **short-form record** — which is a single word —
tries to put back the over-read second word with

```python
self.in_stream.seek(n_bytes_read - 4, 1)
```

With `n_bytes_read == 8` this is `seek(+4, 1)` — a **forward** seek, where a
**backward** one (`seek(-4, 1)`, i.e. `seek(4 - n_bytes_read, 1)`) is needed to
un-read the 4 bytes that belong to the next record. The stream is therefore left
8 bytes past the start of the next record instead of 4 bytes before it, so the
next and all following records are mis-framed.

## Ground truth

A short-form ORCA record is one word. From ORCA's own
`Source/Objects/Data Processing/Data Objects/ORDataTypeAssigner.h`:

```c
#define IsShortForm(x)   (((x)&0x80000000) >> 31)
#define ExtractLength(x) (IsShortForm(x) ? 1 : (ApplyLengthMask(x) ? ApplyLengthMask(x) : LengthFromNextField(x)))
```

`ExtractLength` returns `1` for a short-form record, matching
`orca_packet.get_n_words`. So the 8-byte read over-reads by exactly 4 bytes, and
the rewind must go backward by 4.

## Why it has gone unnoticed

The branch only runs for short-form records, and LEGEND ORCA data contains none
mid-stream — the legend-testdata file is 100% long-form packets
(`short=0, long=70, extended=0`). So the code path has never executed on the
test data, and the test suite has no coverage for it.

## Reproduction

```python
import io
import numpy as np
from daq2lh5.orca.orca_streamer import OrcaStreamer

def short(payload):   # bit 31 set -> short form, 1 word
    return [0x80000000 | (payload & 0x03FFFFFF)]
def long_(data_id, body):
    n = 1 + len(body)
    return [((data_id & 0x3FFF) << 18) | (n & 0x3FFFF)] + list(body)

# a short record followed by a 3-word long record
words = short(0x2A) + long_(5, [0xDEAD, 0xBEEF])
raw = np.array(words, dtype=np.uint32).tobytes()

s = OrcaStreamer(); s.in_stream = io.BytesIO(raw); s.n_bytes_read = 0; s.packet_id = -1
packets = []
while (p := s.load_packet()) is not None:
    packets.append([int(x) for x in p])

# expected: [[short], [long_w0, 0xDEAD, 0xBEEF]]
# actual:   the long record is mis-framed (stream left 8 bytes too far);
#           load_packet then reads a bogus length and errors out.
```

## Suggested fix

Read one header word, then read the second word only for the long/extended
format. This frames short/long/extended records correctly with no over-read and
no rewind (and, as a bonus, removes the seek so the forward read path works on
non-seekable streams). A regression test over synthetic short/long/extended
records reproduces the bug and verifies the fix.
