# Online monitoring: reading DAQ data from a live stream

Notes and artifacts from investigating live (socket) DAQ conversion with
`daq2lh5` — converting data off a running DAQ rather than from a finished file.

## Summary

`daq2lh5` can read DAQ data from a network stream, not just a file, so the same
conversion code runs online and offline. Demonstrated for the two LEGEND DAQs
designed to stream: FlashCam and ORCA.

- **FlashCam**: `FCStreamer.open_stream` gained a `timeout` (ms) forwarded to the
  FCIO stream. With `timeout=-1` the read blocks per record, so the existing
  iterator follows a live tmio TCP stream and ends cleanly when the writer
  closes. (branch `feature/follow-stream`)
- **ORCA**: the forward read path used `tell()` (per packet, for the random-access
  `packet_locs` index) and `seek()` (to skip unknown-id packets) — both fail on a
  non-seekable socket. Guarded both behind `in_stream.seekable()`: skip the
  bookkeeping / read-and-discard instead. File reading is unchanged.
  (branch `feature/orca-socket-source`)

Both changes are minimal and additive.

## Architecture notes

- Online means **stream over TCP**, not file-tailing: a growing file cannot
  signal "more coming" (EOF is terminal), but a socket blocks when starved.
- The DAQ already tees: ORCA's **Data Broadcaster** (server, port 44666) streams
  while the **Data File** object writes the archive — two sinks of the same data
  chain. Do not tee inside the converter.
- Keep the **archive** (raw file: source of truth, bulletproof, independent) and
  the **conversion** (derived, reprocessable, crash-safe) decoupled.
- ORCA streaming behavior:
  - **No client connected** → records are dropped; DAQ and file are unaffected.
  - **Late join, mid-run** → the Broadcaster replays the cached run header to each
    new client on connect, so a late consumer still learns the schema, then gets
    live data.
  - **Connect between runs** → no header until the next run starts (the reader
    blocks on the first packet).
  - **Broadcaster** = server (streams out); **Data Listener** = client (pulls in).

## Caveats / follow-ons

- FlashCam and ORCA only (Compass/Llama are file-only formats).
- Verified with replay rigs (see `fcio-tcp-replay.c`), not yet a live DAQ.
- A clean way to pass a socket peer to `open_stream`/`set_in_stream` is the
  obvious next step.
- A mid-run header update would not be re-read by `open_stream` (rare).

## Files here

- `orca-short-packet-bug.md` — a separate, pre-existing ORCA framing bug found
  along the way (a short-form record is mis-framed by a wrong-direction seek;
  latent because LEGEND ORCA data has no short-form records). Independent of the
  streaming work; file as an issue.
- `fcio-tcp-replay.c` — replays a real `.fcio` file as a live tmio TCP stream, the
  rig used to verify FlashCam socket reading end-to-end. Build against the `fcio`
  C library (which vendors `tmio`/`bufio`); usage in the file header.
