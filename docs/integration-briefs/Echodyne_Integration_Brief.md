# Echodyne EchoGuard — Integration Brief

Counter-UAS / ground-surveillance radar (EchoGuard, SW 17.1.4). Provides the air picture that cues the
sensor→effector plugin. Tracks reach the TAK Server as CoT through the TUT translator.

## Addressing
EchoGuard at **10.100.0.201** on the PacStar sensor network (10.100.0.0/24, PoE off the PacStar 444).
A bridge host on this segment reaches the radar and forwards CoT to the TAK Server.

## Required network ports
| Port | Protocol | Direction | Purpose |
|------|----------|-----------|---------|
| TCP 23 | BNET CLI (ASCII) | client ↔ radar | control session; must stay open for the duration of a tracking run |
| TCP 29982 | binary | radar → client | fused track stream — the TAK feed |

The radar streams on 29982 **only while** a CLI session on 23 is open and tracking has been started
(`MODE:SWT:START`); closing the 23 session stops the stream. Ports 29979 (status), 29980 (RV-map),
29981 (detections) and 29984 (measurements) are available but not used for the TAK feed.

## Authentication
None on the data path or the standard control commands used here — no TLS, login, or token. (A
super-user password gates certain privileged config writes, not the track stream or SWT control.)
Security is by network isolation: the radar stays on the isolated sensor segment, reachable only by the
bridge host, never exposed on backhaul.

## Message format
Binary, little-endian. Track packets must be the **128-byte-per-track** legacy format. The radar/RadarUI
default is the 424-byte extended packet, so the connector actively sets `OUTPUT:EXTENDEDPACKET:ENABLE FALSE`
at start (the extended packet is not parsed). Each track carries
position (range/azimuth/elevation), velocity, confidence, RCS, and UAV/unknown probability. Positions
are **radar-relative, not geodetic** — the bridge georeferences them against the radar's surveyed
location and orientation before producing CoT.

## Polling vs push
Push (streaming). After `MODE:SWT:START` the radar streams tracks continuously at a user-set rate
(0–10 Hz) until `MODE:SWT:STOP`. No polling.

## Expected latency
Track output is configurable up to 10 Hz (a 100 ms reporting interval). End-to-end latency to TAK
depends on the bridge and transport and is measured on the bench rather than quoted from spec.

## Integration path
EchoGuard (TCP 29982) → **TUT** (247 Universal TAK Translator) → CoT → TAK Server. TUT opens the control
session, decodes the track packets, georeferences to WGS-84, and publishes CoT. Demonstrated end-to-end:
466 CoT events / 19 unique tracks streamed to the RACK TAK server and WinTAK in a single run.
