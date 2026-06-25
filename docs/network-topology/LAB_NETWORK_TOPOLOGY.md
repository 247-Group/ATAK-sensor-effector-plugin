# RACK Sensor & Effector — Lab Network Topology (RPDT-16)

**Sprint 1.** Destination: repo `/docs/network-topology/`. Status: **§4 decided (bridge), lab TAK 5.7
live.** Remaining live-verify items in §5. Companion: `INTEGRATION_BRIEF_ECHODYNE.md`,
`INTEGRATION_BRIEF_BOSCH.md`.

## 1. Nodes

| Node | Role | Where it lives | Lab IP | Access |
|------|------|----------------|--------|--------|
| Jackal (firewall) | WireGuard server, PF gateway | Solar Storm edge | WG 10.247.5.1 / ext 38.97.126.66:61394 udp | n/a |
| Hyperion | GPU host (ARM64 Ampere, ~4× L40S) | Solar Storm N4 | 10.247.4.254 | SSH; **Chris** owns |
| FRITH | GPU box, Ollama (36 models) | Solar Storm N4 | 10.247.4.3 (Ollama :11434) | SSH-forward (Chris's model) |
| Phobos | GPU guest VM (passthrough) | on Hyperion | 10.247.4.4 (Ollama :11434) | SSH ed25519 |
| **Solar Storm TAK (VM 100)** | sprint dev C2 / CoT hub (the existing SS TAK, upgraded — not a new "lab" box) | **"TAKServer-RHEL8", Pluto/N3** | **10.247.3.2** (ext 38.97.126.70) | mTLS 8089/8443, enroll 8446 |
| Mike's L40 box (RPDT-14) | training/host env (FRITH clone) | Solar Storm N4 | TBD (Chris provisioning) | machine-key SSH |
| PacStar 451 / Jetson Nano | edge compute (sensor host) | PacStar tactical net | 10.100.0.x | IPMI 10.100.0.11 |
| Tab Active5 Pro | EUD (ATAK) | client | DHCP / WG client | enroll vs lab TAK 8446 |
| Echodyne EchoGuard `MESA-002788` | radar (PROVEN via TUT) | PacStar 444 PoE | **10.100.0.201** | TCP 23 + 29982 (see brief) |
| Bosch 7100i | PTZ camera (planned effector) | PacStar PoE | 10.100.0.149 (or VLAN2 10.100.2.x — conflict) | RTSP 554 / ONVIF 80/443 |
| TUT host | sensor→CoT bridge (247 Universal TAK Translator) | bridges PacStar ↔ lab | on 10.100.0.x; forwards to lab TAK | also hosted `tut.247tak.com:443` |
| Engineer laptops (remote) | dev | remote | WG 10.247.5.x peers | WireGuard → Warpgate |

## 2. Solar Storm segments
N1 10.247.1.0/24 (Betty) · N2 10.247.2.0/24 (Mars) · N3 10.247.3.0/24 (Pluto) ·
N4 10.247.4.0/24 (Hyperion/GPU) · WireGuard 10.247.5.0/24 (Jackal). WG AllowedIPs 10.247.0.0/16 →
a connected engineer reaches GPU (N4) and the lab TAK (N3). (Ref: `SOLAR_STORM_SSP.md`, `WIREGUARD_ACCESS_GUIDE.md`.)

## 3. Link / port map

| From → To | Port/Proto | Purpose |
|-----------|-----------|---------|
| Engineer → Jackal | UDP 61394 (WireGuard) | remote access into the lab |
| Engineer → Warpgate (38.97.126.77) | HTTPS/SSH (Google OAuth) | bastion dev access |
| EUD/engineer → Lab TAK (10.247.3.2) | TCP 8089 (mTLS), 8443 (admin), 8446 (enroll) | CoT / enrollment |
| Lab TAK ↔ other TAK (if federated) | TCP 9001 (federation, mTLS) | COP sync (federation currently off) |
| TUT host → Echodyne | TCP 23 (BNET CLI, held open) + 29982 (track stream) | radar tracks |
| **TUT host → Lab TAK** | TCP 8089 (CoT) | **georeferenced tracks → CoT → TAK** |
| Relay/TUT host → Bosch | TCP 554 (RTSP), 80/443 (ONVIF), 1756 (RCP+) | video + PTZ (planned) |
| Consumer → FRITH Ollama | SSH `-L 11434:localhost:11434` (Chris's model) | LLM inference |
| Engineer → GPU (Phobos/Hyperion) | SSH; Ollama API 11434 | AI dev/inference |

## 4. ✅ DECISION — bridge the sensors, don't relocate
Echodyne, Bosch, and the PacStar/Jetson stay on the **PacStar tactical net 10.100.0.0/24** (in the kit).
We **bridge at the TUT-host layer**, not at the network layer: the TUT host sits on the sensor segment,
talks to the radar/camera locally (23/29982, RTSP/ONVIF), and forwards **CoT to the lab TAK (10.247.3.2:8089)**
— and video to GV Streamer. **No re-IP of sensors onto Solar Storm, no L2 bridge of the tactical net into
the lab.** This keeps the kit deployable as-is and matches how Echodyne→TUT→TAK already worked on
2026-05-08. (Supersedes the old relocate-vs-bridge open item; consistent with both integration briefs.)

## 5. To verify live before final commit
- **Lab TAK:** ✅ VM 100 upgraded 5.4 → **5.7-RELEASE43** on 2026-06-19; 8089/8443/8446 listening, schema
  migrated. Open: federation stays off unless needed; run a Tab Active5 enrollment test.
- **GPU/L40 access:** Chris cloning FRITH → dedicated L40 box for Mike (RPDT-14, in motion). Consumer
  Ollama via SSH-forward (Chris's model).
- **Bosch:** resolve subnet conflict (10.100.0.149 vs VLAN2 10.100.2.x) + confirm PTZ-variant part number.
- **TUT host:** confirm which box runs the lab TUT instance and its sensor-segment + lab-TAK reachability.

## 6. Decision — in-place VM upgrade (not Docker)
We used the **existing Solar Storm TAK VM (VM 100)** and upgraded it **5.4 → 5.7-RELEASE43 in place**,
rather than deploying a fresh TAK 5.7 in Docker on the GPU server as RPDT-15's wording suggested.
**Rationale (engineer's call, 2026-06-19, Jon Hayles):** the VM was already configured, federated, and
cert/CoreConfig/DB intact — an in-place RPM upgrade preserved all of it at lowest risk. A Docker rebuild
would have meant migrating certs/config/DB into containers for **no operational benefit** on a single
long-lived server; Docker's wins (reproducible images, fast version pin/rollback, fresh multi-instance)
don't apply to an already-dialed-in box, and TAK doesn't need the GPU, so co-location buys nothing.
"Docker" in the ticket was a modern default, not a technical requirement.

*(Diagram: `LAB_NETWORK_TOPOLOGY.drawio` — matches the `RACK_Network_Diagram.drawio` color system. This table is the data layer.)*
