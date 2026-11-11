# ed25519.py — Pure-Python Ed25519 (RFC 8032), standard library only.
#
# Implements Ed25519 signing and verification per RFC 8032 sections 5.1.5
# (key generation), 5.1.6 (sign) and 5.1.7 (verify), using extended
# twisted-Edwards coordinates so that point operations need no modular
# inversion in the inner loop (formulas from Hisil-Wong-Carter-Dawson,
# "add-2008-hwcd" / "dbl-2008-hwcd", as used by the reference
# implementations).  Validated against the RFC 8032 section 7.1 test
# vectors in tests/test_ed25519_vectors.py.
#
# WARNING: reference implementation.  Not constant-time (Python big-int
# arithmetic is not constant-time), and not intended for production use.
# It exists so this reference mesh can have real public-key agent
# identities with zero third-party dependencies.

import hashlib

# Curve parameters (RFC 8032 section 5.1.1).
q = (1 << 255) - 19
L = (1 << 252) + 27742317777372353535851937790883648493
# d = -121665 / 121666 (mod q)
d = (-121665 * pow(121666, q - 2, q)) % q
# sqrt(-1) mod q
I = pow(2, (q - 1) // 4, q)


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _xrecover(y: int) -> int:
    """Recover the x-coordinate for a given y (RFC 8032 section 5.1.3)."""
    xx = (y * y - 1) * pow(d * y * y + 1, q - 2, q) % q
    x = pow(xx, (q + 3) // 8, q)
    if (x * x - xx) % q != 0:
        x = (x * I) % q
    if x % 2 != 0:
        x = q - x
    return x


# Base point B (RFC 8032 section 5.1.5): y = 4/5, x recovered.
_By = 4 * pow(5, q - 2, q) % q
_Bx = _xrecover(_By)
# Extended coordinates (X, Y, Z, T) with x = X/Z, y = Y/Z, x*y = T/Z.
_B_ext = (_Bx, _By, 1, _Bx * _By % q)


def _point_add(P, Q):
    """Extended-coordinate point addition (add-2008-hwcd)."""
    X1, Y1, Z1, T1 = P
    X2, Y2, Z2, T2 = Q
    A = (Y1 - X1) * (Y2 - X2) % q
    B = (Y1 + X1) * (Y2 + X2) % q
    C = T1 * 2 * d % q * T2 % q
    D = Z1 * 2 % q * Z2 % q
    E = (B - A) % q
    F = (D - C) % q
    G = (D + C) % q
    H = (B + A) % q
    return (E * F % q, G * H % q, F * G % q, E * H % q)


def _point_double(P):
    """Extended-coordinate point doubling (dbl-2008-hwcd)."""
    X1, Y1, Z1, _T1 = P
    A = X1 * X1 % q
    B = Y1 * Y1 % q
    C = 2 * Z1 * Z1 % q
    D = (-A) % q
    E = ((X1 + Y1) * (X1 + Y1) - A - B) % q
    G = (D + B) % q
    F = (G - C) % q
    H = (D - B) % q
    return (E * F % q, G * H % q, F * G % q, E * H % q)


def _scalarmult(P, e: int):
    """Double-and-add scalar multiplication; e must be >= 0."""
    Q = (0, 1, 1, 0)  # identity element
    bits = bin(e)[2:]
    for ch in bits:
        Q = _point_double(Q)
        if ch == "1":
            Q = _point_add(Q, P)
    return Q


def _to_affine(P):
    """Convert extended coordinates to affine (x, y)."""
    X, Y, Z, _T = P
    inv_z = pow(Z, q - 2, q)
    return (X * inv_z % q, Y * inv_z % q)


def _encode_point(P) -> bytes:
    """Encode an extended-coordinate point (RFC 8032 section 5.1.2)."""
    x, y = _to_affine(P)
    bits = (y & ((1 << 255) - 1)) | ((x & 1) << 255)
    return bits.to_bytes(32, "little")


def _decode_point(data: bytes):
    """Decode a 32-byte point encoding (RFC 8032 section 5.1.3)."""
    if len(data) != 32:
        raise ValueError("encoded point must be 32 bytes")
    y = int.from_bytes(data, "little") & ((1 << 255) - 1)
    x = _xrecover(y)
    if (x & 1) != ((int.from_bytes(data, "little") >> 255) & 1):
        x = q - x
    # On-curve check: -x^2 + y^2 = 1 + d*x^2*y^2 (mod q).
    if (-x * x + y * y - 1 - d * x * x % q * y * y) % q != 0:
        raise ValueError("decoded point is not on the curve")
    return (x, y, 1, x * y % q)


def _clamp(h: bytes) -> int:
    """Clamp the first 32 bytes of a SHA-512 digest (RFC 8032 section 5.1.5)."""
    a = bytearray(h[:32])
    a[0] &= 248
    a[31] &= 127
    a[31] |= 64
    return int.from_bytes(a, "little")


def _hint(data: bytes) -> int:
    return int.from_bytes(_sha512(data), "little")


def keygen(seed: bytes) -> tuple:
    """Derive (public_key, secret_seed) from a 32-byte seed.

    The "secret key" in RFC 8032 test vectors is this 32-byte seed; the
    public key is computed from it (RFC 8032 section 5.1.5).
    """
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    a = _clamp(_sha512(seed))
    A = _scalarmult(_B_ext, a)
    return _encode_point(A), seed


def sign(message: bytes, public_key: bytes, seed: bytes) -> bytes:
    """Sign a message (RFC 8032 section 5.1.6)."""
    h = _sha512(seed)
    a = _clamp(h)
    r = _hint(h[32:] + message) % L
    R = _scalarmult(_B_ext, r)
    R_enc = _encode_point(R)
    S = (r + _hint(R_enc + public_key + message) * a) % L
    return R_enc + S.to_bytes(32, "little")


def verify(signature: bytes, message: bytes, public_key: bytes) -> bool:
    """Verify a signature (RFC 8032 section 5.1.7). Returns True/False."""
    if len(signature) != 64 or len(public_key) != 32:
        return False
    try:
        R = _decode_point(signature[:32])
        A = _decode_point(public_key)
    except ValueError:
        return False
    S = int.from_bytes(signature[32:], "little")
    if S >= L:
        return False
    h = _hint(signature[:32] + public_key + message) % L
    # Check [S]B == R + [h]A.  Compare affine coordinates: extended
    # coordinates are projective, so raw tuples of equal points differ.
    return _to_affine(_scalarmult(_B_ext, S)) == _to_affine(
        _point_add(R, _scalarmult(A, h)))
