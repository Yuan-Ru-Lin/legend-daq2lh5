import io

import numpy as np

from daq2lh5.orca.orca_streamer import OrcaStreamer


class _NonSeekable(io.RawIOBase):
    """Wrap bytes as a forward-only (non-seekable) readable stream."""

    def __init__(self, data):
        self._b = io.BytesIO(data)

    def readinto(self, buf):
        return self._b.readinto(buf)

    def readable(self):
        return True

    def seekable(self):
        return False


def _make_long(data_id, body):
    n = 1 + len(body)
    return [((data_id & 0x3FFF) << 18) | (n & 0x3FFFF)] + list(body)


def _read_all(stream, decoder_ids):
    s = OrcaStreamer()
    s.in_stream = stream
    s.n_bytes_read = 0
    s.packet_id = -1
    s.decoder_id_dict = {((d & 0x3FFF) << 18): object() for d in decoder_ids}
    out = []
    while True:
        p = s.load_packet(skip_unknown_ids=True)
        if p is None:
            break
        out.append([int(x) for x in p])
    return out


def test_load_packet_on_non_seekable_stream():
    # a non-seekable stream (e.g. a socket) supports neither tell() nor seek();
    # reading must still work and match the seekable result. The middle packet
    # has an unknown data id, exercising the skip-unknown path (read-and-discard
    # instead of seek), and the following known packet must remain aligned.
    packets = [
        _make_long(5, [0xA1, 0xA2]),
        _make_long(99, [0xB0, 0xB1, 0xB2]),  # unknown id -> skipped
        _make_long(5, [0xC1]),
    ]
    raw = np.array([w for p in packets for w in p], dtype=np.uint32).tobytes()

    seekable = _read_all(io.BytesIO(raw), decoder_ids=[5])
    non_seekable = _read_all(_NonSeekable(raw), decoder_ids=[5])

    assert seekable == non_seekable
    # known packets framed in full, unknown one reduced to its header
    assert non_seekable[0] == [(5 << 18) | 3, 0xA1, 0xA2]
    assert non_seekable[2] == [(5 << 18) | 2, 0xC1]
