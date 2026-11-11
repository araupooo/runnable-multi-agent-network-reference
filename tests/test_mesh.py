# test_mesh.py — Integration tests for the three-agent mesh.
#
# Covers: (T1) normal cooperation end-to-end, (T2) tampered message
# rejected, (T3) failed authentication (unknown key) rejected, (T4)
# agent-identity spoofing rejected, (T5) replayed message rejected,
# (T6) wrong recipient rejected, (T7) unauthorised sender for a message
# type rejected, (T8) unknown agent rejected.  Attack tests send raw
# frames over real TCP sockets to the live agents — they exercise the
# same verification path as production traffic.
#
# Usage: python3 tests/test_mesh.py
# Exit code 0 iff every test passes.

import copy
import json
import os
import socket
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import ed25519
import mesh
from mesh import RejectError, canonical, recv_frame, send_frame


def raw_send(port, payload: bytes):
    """Send one raw frame to an agent port; return the reply bytes."""
    with socket.create_connection(("127.0.0.1", port), timeout=10) as conn:
        conn.settimeout(10)
        send_frame(conn, payload)
        return recv_frame(conn)


def raw_envelope(m, sender_name, recipient, msg_type, payload, seed, pk):
    """Build a correctly signed envelope from a given identity."""
    env = {"version": 1, "sender": sender_name, "recipient": recipient,
           "type": msg_type, "seq": 999001, "ts_ms": int(time.time() * 1000),
           "payload": payload}
    env["sig"] = ed25519.sign(canonical(env), pk, seed).hex()
    return env


def check(name, cond, detail=""):
    print(f"{name}: {'PASS' if cond else 'FAIL'} {detail}".rstrip())
    return cond


def main():
    failures = 0
    m = mesh.Mesh()
    m.start()
    try:
        planner = m.agents["planner"]
        worker = m.agents["worker"]
        auditor = m.agents["auditor"]

        # T1 — normal cooperation end-to-end (3 jobs, incl. edge n=1).
        for job_id, n in (("t1-a", 1000), ("t1-b", 1), ("t1-c", 137)):
            total, verified = m.client.submit_job(job_id, n)
            ok = total == mesh.closed_form_sum_squares(n) and verified
            if not check(f"T1 normal-cooperation {job_id} n={n}",
                         ok, f"total={total} verified={verified}"):
                failures += 1

        # Capture one valid envelope for replay (T5) by signing a fresh
        # task.assign as the planner through the public API path: build it
        # manually with the planner's real identity.
        assign = raw_envelope(
            m, "planner", "worker", "task.assign",
            {"job_id": "t5", "lo": 1, "hi": 10},
            m.seeds["planner"], m.registry["planner"])

        # T5 — replay: deliver the same valid envelope twice.  The first
        # delivery is accepted (worker computes), the second must be
        # rejected as a stale sequence number.
        reply1 = raw_send(19002, canonical(assign))
        first_ok = b'"error"' not in reply1
        reply2 = raw_send(19002, canonical(assign))
        replay = json.loads(reply2.decode())
        if not check("T5 replay-rejected",
                     first_ok and replay.get("error") == "stale_seq",
                     f"first_accepted={first_ok} second={replay}"):
            failures += 1

        # T2 — tampered message: take the valid envelope, flip a digit in
        # the payload, keep the original signature.
        tampered = copy.deepcopy(assign)
        tampered["payload"] = {"job_id": "t2", "lo": 1, "hi": 11}
        tampered["seq"] = 999002
        reply = json.loads(raw_send(19002, canonical(tampered)).decode())
        if not check("T2 tampered-message-rejected",
                     reply.get("error") == "bad_signature", f"reply={reply}"):
            failures += 1

        # T3 — failed authentication: envelope signed with an attacker
        # keypair that is not in the registry.
        atk_seed = os.urandom(32)
        atk_pk, _ = ed25519.keygen(atk_seed)
        forged = raw_envelope(m, "attacker", "worker", "task.assign",
                              {"job_id": "t3", "lo": 1, "hi": 10},
                              atk_seed, atk_pk)
        reply = json.loads(raw_send(19002, canonical(forged)).decode())
        if not check("T3 unknown-key-rejected",
                     reply.get("error") == "unknown_sender", f"reply={reply}"):
            failures += 1

        # T4 — identity spoofing: envelope claims sender "worker" and
        # uses a real message type (task.assign.reply, worker -> planner)
        # but is signed with the auditor's key, so the signature does
        # not match the worker's registered public key.
        spoof = raw_envelope(m, "worker", "planner", "task.assign.reply",
                             {"job_id": "t4", "lo": 1, "hi": 10,
                              "partial": 385},
                             m.seeds["auditor"], m.registry["auditor"])
        reply = json.loads(raw_send(19001, canonical(spoof)).decode())
        if not check("T4 identity-spoofing-rejected",
                     reply.get("error") == "bad_signature", f"reply={reply}"):
            failures += 1

        # T6 — wrong recipient: a valid planner-signed task.assign
        # delivered to the auditor instead of the worker.
        wrong = raw_envelope(m, "planner", "worker", "task.assign",
                             {"job_id": "t6", "lo": 1, "hi": 10},
                             m.seeds["planner"], m.registry["planner"])
        reply = json.loads(raw_send(19003, canonical(wrong)).decode())
        if not check("T6 wrong-recipient-rejected",
                     reply.get("error") == "wrong_recipient", f"reply={reply}"):
            failures += 1

        # T7 — unauthorised sender for type: the auditor (a known agent)
        # tries to send task.assign, which only the planner may send.
        unauth = raw_envelope(m, "auditor", "worker", "task.assign",
                              {"job_id": "t7", "lo": 1, "hi": 10},
                              m.seeds["auditor"], m.registry["auditor"])
        reply = json.loads(raw_send(19002, canonical(unauth)).decode())
        if not check("T7 unauthorised-sender-rejected",
                     reply.get("error") == "unauthorised_sender",
                     f"reply={reply}"):
            failures += 1

        # T8 — unknown agent name: envelope claims sender "mallory"
        # (not in the registry) signed with a fresh key.
        mallory_seed = os.urandom(32)
        mallory_pk, _ = ed25519.keygen(mallory_seed)
        unknown = raw_envelope(m, "mallory", "worker", "task.assign",
                               {"job_id": "t8", "lo": 1, "hi": 10},
                               mallory_seed, mallory_pk)
        reply = json.loads(raw_send(19002, canonical(unknown)).decode())
        if not check("T8 unknown-agent-rejected",
                     reply.get("error") == "unknown_sender", f"reply={reply}"):
            failures += 1

        # T9 — malformed frame: not JSON at all.
        reply = json.loads(raw_send(19002, b"this is not json").decode())
        if not check("T9 malformed-frame-rejected",
                     reply.get("error") == "malformed", f"reply={reply}"):
            failures += 1

        # Stats: no legitimate message was rejected; every attack was.
        total_rejected = sum(a.stats["rejected"]
                             for a in m.agents.values())
        print(f"stats planner: sent={planner.stats['sent']} "
              f"received={planner.stats['received']} "
              f"rejected={planner.stats['rejected']}")
        print(f"stats worker: sent={worker.stats['sent']} "
              f"received={worker.stats['received']} "
              f"rejected={worker.stats['rejected']}")
        print(f"stats auditor: sent={auditor.stats['sent']} "
              f"received={auditor.stats['received']} "
              f"rejected={auditor.stats['rejected']}")
        print(f"stats client: sent={m.client.stats['sent']} "
              f"received={m.client.stats['received']}")
        # 8 attack deliveries were rejected (T2,T3,T4,T5-replay,T6,T7,T8,T9).
        if not check("T10 rejection-count", total_rejected == 8,
                     f"total_rejected={total_rejected} expected=8"):
            failures += 1
    finally:
        m.stop()
    print(f"RESULT: {'PASS' if failures == 0 else 'FAIL'} "
          f"integration failures={failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
