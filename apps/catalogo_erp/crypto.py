"""Cifrado de la contraseña de conexión al ERP.

Se prefiere ``cryptography.fernet`` (requisito de producción). Si la
dependencia no está instalada (por ejemplo, desarrollo offline), se usa un
cifrado autenticado construido solo con la biblioteca estándar
(PBKDF2-HMAC-SHA256 como KDF + keystream por HMAC en modo CTR + etiqueta
HMAC para integridad). Ambos esquemas protegen la clave en reposo.
"""

import base64
import hashlib
import hmac
import os

from django.conf import settings

try:
    from cryptography.fernet import Fernet, InvalidToken

    _FERNET_DISPONIBLE = True
except Exception:  # pragma: no cover - entorno sin cryptography
    _FERNET_DISPONIBLE = False

# Marca del esquema de la biblioteca estándar (los tokens Fernet empiezan
# siempre por "gAAAA"; los de este esquema, por "cb1:").
_MAGIA = "cb1"
_PREFIJOS_CIFRADOS = ("gAAAA", f"{_MAGIA}:")


def _clave_bytes():
    """Deriva una clave estable de 32 bytes a partir de ``SECRET_KEY``."""
    secreto = settings.SECRET_KEY.encode("utf-8")
    return base64.urlsafe_b64encode(hashlib.sha256(secreto).digest())


def cifrar(texto):
    """Cifra una cadena y devuelve un token seguro para guardar en la BD."""
    if not texto:
        return ""
    if _FERNET_DISPONIBLE:
        return Fernet(_clave_bytes()).encrypt(texto.encode("utf-8")).decode("ascii")
    return _cifrar_fallback(texto)


def descifrar(token):
    """Descifra un token generado con :func:`cifrar`. Devuelve ``""`` si no."""
    if not token:
        return ""
    if _FERNET_DISPONIBLE:
        try:
            return Fernet(_clave_bytes()).decrypt(token.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError, ValueError):
            return ""
    return _descifrar_fallback(token)


# ---------------------------------------------------------------------------
# Esquema de la biblioteca estándar (solo si no hay `cryptography`)
# ---------------------------------------------------------------------------
def _derivar(sal):
    return hashlib.pbkdf2_hmac("sha256", _clave_bytes(), sal, 200_000)


def _keystream(clave, sal, largo):
    """Bloque de bytes pseudoaleatorios: HMAC(clave, sal || contador)."""
    out = bytearray()
    contador = 0
    while len(out) < largo:
        out.extend(
            hmac.new(clave, sal + contador.to_bytes(4, "big"), hashlib.sha256).digest()
        )
        contador += 1
    return bytes(out[:largo])


def _xor(data, clave, sal):
    ks = _keystream(clave, sal, len(data))
    return bytes(a ^ b for a, b in zip(data, ks))


def _cifrar_fallback(texto):
    sal = os.urandom(16)
    clave = _derivar(sal)
    cuerpo = _xor(texto.encode("utf-8"), clave, sal)
    etiqueta = hmac.new(clave, sal + cuerpo, hashlib.sha256).digest()
    token = base64.urlsafe_b64encode(sal + etiqueta + cuerpo).decode("ascii")
    return f"{_MAGIA}:{token}"


def _descifrar_fallback(token):
    if not token.startswith(f"{_MAGIA}:"):
        return ""
    try:
        crudo = base64.urlsafe_b64decode(token.split(":", 1)[1].encode("ascii"))
        sal, etiqueta, cuerpo = crudo[:16], crudo[16:48], crudo[48:]
    except (ValueError, TypeError):
        return ""
    clave = _derivar(sal)
    esperada = hmac.new(clave, sal + cuerpo, hashlib.sha256).digest()
    if not hmac.compare_digest(esperada, etiqueta):
        return ""
    try:
        return _xor(cuerpo, clave, sal).decode("utf-8")
    except UnicodeDecodeError:
        return ""