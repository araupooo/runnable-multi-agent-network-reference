# mesh.py — Three-agent service mesh reference (Python 3 standard library only).
#
# Agents: planner, worker, auditor.  They communicate only over localhost
# TCP.  Every message is a signed JSON envelope (canonical JSON per the
# JSON Canonicalization Scheme subset described in RFC 8785: sorted keys,
# no insignificant whitespace, UTF-8; signed content contains only
# strings, integers, booleans, null, lists and objects — no floats).
# Each agent holds an Ed25519 keypair generated at runtime (RFC 8032,
# see src/ed25519.py); private keys are never written to disk.
#
# Envelope fields: version, sender, recipient, type, seq, ts_ms, payload,
# sig (hex of the 64-byte Ed25519 signature over the canonical bytes of
# the envelope without "sig").  Receivers enforce, in order:
#   1. well-formed JSON frame, version == 1, recipient == self;
#   2. sender is in the public-key registry (unknown sender rejected);
#   3. signature verifies against the registered public key of the
#      claimed sender (tampering and identity spoofing rejected);
#   4. sender is authorised for this message type;
#   5. seq passes the replay check: a sliding window of the last
#      REPLAY_WINDOW sequence numbers per sender.  A message is
#      accepted if its seq is new and not older than the window floor;
#      exact duplicates and anything below the window are rejected.
#      (A strictly-increasing check would break under concurrency: one
#      agent sending from several threads can deliver messages out of
#      order.  The window plus a seen-set keeps replay protection while
#      tolerating reordering within the window.)
REPLAY_WINDOW = 128
#
# Cooperative workflow (job: sum of squares 1^2 + ... + n^2):
#   client -> planner : job.request  {job_id, n}
#   planner -> worker: task.assign  {job_id, lo, hi}   (two halves)
#   worker -> planner: task.assign.reply {job_id, lo, hi, partial}
#   planner -> auditor: audit.request {job_id, parts: [...]}
#   auditor -> planner: audit.request.reply {job_id, verified, total}
#   planner -> client : job.request.reply {job_id, total, verified}
# The client checks the total against the closed form n(n+1)(2n+1)/6.
#
# Deployment model (honest scope): single-process reference; each agent
# is an independent thread with its own keypair, sequence counters and
# TCP listener, and agents share nothing except the public-key registry
# (the analogue of a key directory in a real deployment).  Production
# deployment would run each agent as its own process/host with the same
# protocol.  Transport is plaintext localhost TCP: messages are
# authenticated and integrity-protected, but NOT encrypted — a local
# observer can read message contents (see docs/threat-model.md).

import hashlib
import json
import os
import socket
import socketserver
import struct
import threading
import time

import ed25519

VERSION = 1
MAX_FRAME = 1024 * 1024  # 1 MiB
SOCKET_TIMEOUT = 10.0

# agent name -> TCP port on 127.0.0.1
PORTS = {"planner": 19001, "worker": 19002, "auditor": 19003}
AGENTS = ("planner", "worker", "auditor")

# message type -> set of senders allowed to send it (replies included: a
# reply may only come from the agent that handled the request).
# "job.request" additionally accepts any registered sender whose name
# starts with "client-" (extra benchmark clients, see Mesh.add_client).
ALLOWED_SENDERS = {
    "job.request": {"client"},
    "job.request.reply": {"planner"},
    "task.assign": {"planner"},
    "task.assign.reply": {"worker"},
    "audit.request": {"planner"},
    "audit.request.reply": {"auditor"},
}


class RejectError(Exception):
    """A message was rejected; .reason is a short machine-readable code."""

    def __init__(self, reason, detail=""):
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


def canonical(obj) -> bytes:
    """Canonical JSON bytes (RFC 8785 subset: sorted keys, no spaces)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _recv_exact(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connection closed mid-frame")
        buf += chunk
    return buf


def send_frame(conn, payload: bytes):
    conn.sendall(struct.pack(">I", len(payload)) + payload)


def recv_frame(conn):
    raw_len = _recv_exact(conn, 4)
    (length,) = struct.unpack(">I", raw_len)
    if length > MAX_FRAME:
        raise RejectError("oversize_frame", f"{length} bytes")
    return _recv_exact(conn, length)


class Agent:
    """One mesh agent: identity, TCP listener, signed-message handling."""

    def __init__(self, name, seed, registry, port):
        self.name = name
        self.seed = seed
        self.public_key, _ = ed25519.keygen(seed)
        # Shared registry object (the mesh key directory): all agents see
        # new entries added via Mesh.add_client.
        self.registry = registry
        self.port = port
        self.seq = 0
        # sender -> {"high": highest seq accepted, "seen": set of seqs
        #   inside the replay window}
        self.seen = {}
        self.lock = threading.Lock()
        self.stats = {"sent": 0, "received": 0, "rejected": 0}
        self.rejections = []  # (reason, sender, type) for audit
        self.server = None
        self.thread = None

    # -- identity / signing -------------------------------------------------
    def sign_envelope(self, recipient, msg_type, payload):
        with self.lock:
            self.seq += 1
            seq = self.seq
        env = {
            "version": VERSION,
            "sender": self.name,
            "recipient": recipient,
            "type": msg_type,
            "seq": seq,
            "ts_ms": int(time.time() * 1000),
            "payload": payload,
        }
        sig = ed25519.sign(canonical(env), self.public_key, self.seed)
        env["sig"] = sig.hex()
        return env

    def verify_envelope(self, env):
        """Verify a received envelope; returns payload or raises RejectError."""
        if not isinstance(env, dict):
            raise RejectError("malformed", "envelope is not an object")
        if env.get("version") != VERSION:
            raise RejectError("bad_version", repr(env.get("version")))
        sender = env.get("sender")
        recipient = env.get("recipient")
        msg_type = env.get("type")
        if recipient != self.name:
            raise RejectError("wrong_recipient",
                              f"to={recipient} expected={self.name}")
        if sender not in self.registry:
            raise RejectError("unknown_sender", repr(sender))
        if msg_type not in ALLOWED_SENDERS:
            raise RejectError("unknown_type", repr(msg_type))
        allowed = ALLOWED_SENDERS[msg_type]
        if sender not in allowed and not (
                msg_type == "job.request" and sender.startswith("client-")):
            raise RejectError("unauthorised_sender",
                              f"{sender} may not send {msg_type}")
        sig_hex = env.get("sig")
        if not isinstance(sig_hex, str):
            raise RejectError("missing_signature")
        try:
            sig = bytes.fromhex(sig_hex)
        except ValueError:
            raise RejectError("bad_signature_encoding")
        unsigned = {k: v for k, v in env.items() if k != "sig"}
        if not ed25519.verify(sig, canonical(unsigned), self.registry[sender]):
            raise RejectError("bad_signature",
                              f"sender={sender} type={msg_type}")
        seq = env.get("seq")
        if not isinstance(seq, int) or isinstance(seq, bool):
            raise RejectError("bad_seq", repr(seq))
        with self.lock:
            state = self.seen.setdefault(sender, {"high": 0, "seen": set()})
            if seq <= state["high"] - REPLAY_WINDOW:
                raise RejectError(
                    "stale_seq",
                    f"sender={sender} seq={seq} below window "
                    f"high={state['high']}")
            if seq in state["seen"]:
                raise RejectError(
                    "stale_seq",
                    f"sender={sender} seq={seq} duplicate")
            state["seen"].add(seq)
            if seq > state["high"]:
                state["high"] = seq
                floor = state["high"] - REPLAY_WINDOW
                state["seen"] = {s for s in state["seen"] if s > floor}
        return env["payload"]

    # -- transport ----------------------------------------------------------
    def start(self):
        agent = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                try:
                    raw = recv_frame(self.request)
                except ConnectionError:
                    # Client connected and closed without sending a frame
                    # (e.g. a liveness probe).  Nothing to reject.
                    return
                except RejectError as exc:
                    agent._record_reject(exc.reason, "?", "?")
                    try:
                        send_frame(self.request, json.dumps(
                            {"error": exc.reason,
                             "detail": exc.detail}).encode())
                    except OSError:
                        pass
                    return
                try:
                    env = json.loads(raw.decode("utf-8"))
                except Exception as exc:  # noqa: BLE001
                    agent._record_reject("malformed", "?", "?")
                    try:
                        send_frame(self.request, json.dumps(
                            {"error": "malformed",
                             "detail": str(exc)}).encode())
                    except OSError:
                        pass
                    return
                try:
                    payload = agent.verify_envelope(env)
                    agent.stats["received"] += 1
                    reply_payload = agent.dispatch(env["type"], payload,
                                                   env["sender"])
                    reply = agent.sign_envelope(env["sender"],
                                                env["type"] + ".reply",
                                                reply_payload)
                    agent.stats["sent"] += 1
                    send_frame(self.request, canonical(reply))
                except RejectError as exc:
                    agent._record_reject(exc.reason, env.get("sender"),
                                         env.get("type"))
                    try:
                        send_frame(self.request, json.dumps(
                            {"error": exc.reason,
                             "detail": exc.detail}).encode())
                    except OSError:
                        pass
                except OSError:
                    pass

        class Server(socketserver.ThreadingTCPServer):
            daemon_threads = True
            allow_reuse_address = True

        self.server = Server(("127.0.0.1", self.port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()

    def stop(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None

    def _record_reject(self, reason, sender, msg_type):
        with self.lock:
            self.stats["rejected"] += 1
            self.rejections.append((reason, sender, msg_type))

    def request(self, recipient, msg_type, payload):
        """Send a signed request to another agent; return reply payload."""
        env = self.sign_envelope(recipient, msg_type, payload)
        self.stats["sent"] += 1
        with socket.create_connection(("127.0.0.1", PORTS[recipient]),
                                     timeout=SOCKET_TIMEOUT) as conn:
            conn.settimeout(SOCKET_TIMEOUT)
            send_frame(conn, canonical(env))
            raw = recv_frame(conn)
        reply = json.loads(raw.decode("utf-8"))
        if "error" in reply:
            raise RejectError(reply["error"], reply.get("detail", ""))
        reply_payload = self.verify_envelope(reply)
        self.stats["received"] += 1
        return reply_payload

    # -- workflow handlers --------------------------------------------------
    def dispatch(self, msg_type, payload, sender):
        handler = getattr(self, "on_" + msg_type.replace(".", "_"), None)
        if handler is None:
            raise RejectError("unknown_type", msg_type)
        return handler(payload, sender)

    # planner
    def on_job_request(self, payload, sender):
        job_id = payload["job_id"]
        n = payload["n"]
        if not isinstance(n, int) or n < 1:
            raise RejectError("bad_payload", "n must be a positive integer")
        mid = n // 2
        parts = []
        for lo, hi in ((1, mid), (mid + 1, n)):
            res = self.request("worker", "task.assign",
                               {"job_id": job_id, "lo": lo, "hi": hi})
            parts.append(res)
        audit = self.request("auditor", "audit.request",
                             {"job_id": job_id, "parts": parts})
        return {"job_id": job_id, "total": audit["total"],
                "verified": audit["verified"]}

    # worker
    def on_task_assign(self, payload, sender):
        lo, hi = payload["lo"], payload["hi"]
        partial = sum(i * i for i in range(lo, hi + 1))
        return {"job_id": payload["job_id"], "lo": lo, "hi": hi,
                "partial": partial}

    # auditor
    def on_audit_request(self, payload, sender):
        total = 0
        verified = True
        for part in payload["parts"]:
            expect = sum(i * i for i in range(part["lo"], part["hi"] + 1))
            if expect != part["partial"]:
                verified = False
            total += part["partial"]
        return {"job_id": payload["job_id"], "verified": verified,
                "total": total}


class Mesh:
    """Starts the three agents with runtime-generated keypairs."""

    def __init__(self, port_base=19001):
        self.seeds = {name: os.urandom(32) for name in AGENTS}
        self.registry = {}
        for name, seed in self.seeds.items():
            pk, _ = ed25519.keygen(seed)
            self.registry[name] = pk
        # The client is a known sender (planner accepts job.request from it).
        self.client_seed = os.urandom(32)
        client_pk, _ = ed25519.keygen(self.client_seed)
        self.registry["client"] = client_pk
        self.agents = {}
        for i, name in enumerate(AGENTS):
            self.agents[name] = Agent(name, self.seeds[name], self.registry,
                                      port_base + i)
        self.client = Client("client", self.client_seed, self.registry)

    def add_client(self, name):
        """Register an extra client identity (own keypair, own seq space).

        Each concurrent benchmark client needs its own identity: replies
        from the planner carry per-sender sequence numbers, so sharing
        one client identity across threads would make out-of-order
        replies look like replays.
        """
        seed = os.urandom(32)
        pk, _ = ed25519.keygen(seed)
        self.registry[name] = pk
        return Client(name, seed, self.registry)

    def start(self):
        for agent in self.agents.values():
            agent.start()
        # Wait until all listeners accept connections.
        for name, agent in self.agents.items():
            deadline = time.time() + 10
            while True:
                try:
                    with socket.create_connection(
                            ("127.0.0.1", agent.port), timeout=1):
                        break
                except OSError:
                    if time.time() > deadline:
                        raise RuntimeError(f"agent {name} did not start")
                    time.sleep(0.05)

    def stop(self):
        for agent in self.agents.values():
            agent.stop()

    def public_keys_hex(self):
        return {name: pk.hex() for name, pk in self.registry.items()}


class Client:
    """A mesh client: own Ed25519 identity, talks to the planner only."""

    def __init__(self, name, seed, registry):
        self.name = name
        self.seed = seed
        self.public_key, _ = ed25519.keygen(seed)
        # Shared registry object (the mesh key directory).
        self.registry = registry
        self.seq = 0
        self.last_seen = {}
        self.lock = threading.Lock()
        self.stats = {"sent": 0, "received": 0, "rejected": 0}

    def _sign(self, recipient, msg_type, payload):
        with self.lock:
            self.seq += 1
            seq = self.seq
        env = {"version": VERSION, "sender": self.name, "recipient": recipient,
               "type": msg_type, "seq": seq, "ts_ms": int(time.time() * 1000),
               "payload": payload}
        env["sig"] = ed25519.sign(canonical(env), self.public_key,
                                  self.seed).hex()
        return env

    def _verify(self, env):
        unsigned = {k: v for k, v in env.items() if k != "sig"}
        sender = env.get("sender")
        if sender != "planner":
            raise RejectError("unknown_sender", repr(sender))
        if env.get("type") != "job.request.reply":
            raise RejectError("unknown_type", repr(env.get("type")))
        if env.get("recipient") != self.name:
            raise RejectError("wrong_recipient")
        if not ed25519.verify(bytes.fromhex(env["sig"]), canonical(unsigned),
                              self.registry[sender]):
            raise RejectError("bad_signature")
        seq = env.get("seq")
        with self.lock:
            if seq <= self.last_seen.get(sender, 0):
                raise RejectError("stale_seq")
            self.last_seen[sender] = seq
        return env["payload"]

    def submit_job(self, job_id, n):
        """Submit a sum-of-squares job; returns (total, verified)."""
        env = self._sign("planner", "job.request", {"job_id": job_id, "n": n})
        self.stats["sent"] += 1
        with socket.create_connection(("127.0.0.1", PORTS["planner"]),
                                     timeout=SOCKET_TIMEOUT) as conn:
            conn.settimeout(SOCKET_TIMEOUT)
            send_frame(conn, canonical(env))
            raw = recv_frame(conn)
        reply = json.loads(raw.decode("utf-8"))
        if "error" in reply:
            raise RejectError(reply["error"], reply.get("detail", ""))
        payload = self._verify(reply)
        self.stats["received"] += 1
        return payload["total"], payload["verified"]


def closed_form_sum_squares(n):
    return n * (n + 1) * (2 * n + 1) // 6
