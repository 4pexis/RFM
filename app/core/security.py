"""Validação de dados, controle de permissões e proteção de configurações.

O RFM nunca armazena senhas, cookies ou tokens de sessão do Roblox: os
validadores abaixo recusam textos que pareçam conter esse tipo de segredo.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import sys

# --------------------------------------------------------------------------- erros


class ValidationError(ValueError):
    """Dado inválido informado pelo usuário."""


class PermissionDenied(PermissionError):
    """O perfil atual não pode executar a operação."""


# ----------------------------------------------------------------------- validação

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
_SECRET_MARKERS = ("_|WARNING:-DO-NOT-SHARE-THIS", ".ROBLOSECURITY", "ROBLOSECURITY=")


def validate_username(value: str) -> str:
    value = (value or "").strip()
    if not _USERNAME_RE.fullmatch(value):
        raise ValidationError(
            "Nome de usuário inválido: use de 3 a 20 caracteres (letras, números e _)."
        )
    return value


def validate_user_id(value: object) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        number = int(str(value).strip())
    except ValueError as exc:
        raise ValidationError("O ID público do usuário deve ser numérico.") from exc
    if number <= 0:
        raise ValidationError("O ID público do usuário deve ser positivo.")
    return number


def validate_experience_id(value: object) -> str:
    text = str(value or "").strip()
    if text and not text.isdigit():
        raise ValidationError("O identificador da experiência deve conter apenas números.")
    return text


def clean_text(value: object, max_len: int = 2000, field: str = "texto") -> str:
    """Normaliza texto livre e recusa conteúdo com aparência de credencial."""
    text = str(value or "").strip()
    if len(text) > max_len:
        raise ValidationError(f"O campo {field} excede {max_len} caracteres.")
    upper = text.upper()
    if any(marker.upper() in upper for marker in _SECRET_MARKERS):
        raise ValidationError(
            "Este texto parece conter um cookie/token do Roblox. "
            "O RFM não armazena credenciais — remova-o."
        )
    return text


def normalize_tags(value: object) -> str:
    """'Main, alt ,MAIN' -> 'alt,main' (minúsculas, sem duplicatas)."""
    if isinstance(value, (list, tuple, set)):
        parts = [str(v) for v in value]
    else:
        parts = re.split(r"[,;]", str(value or ""))
    tags = sorted({p.strip().lower() for p in parts if p.strip()})
    return clean_text(",".join(tags), 255, "tags")


# ---------------------------------------------------------------------- permissões


class Role:
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"
    LABELS = {ADMIN: "Administrador", OPERATOR: "Operador", VIEWER: "Somente leitura"}


class Permission:
    WRITE = "write"  # criar/editar registros
    DELETE = "delete"  # excluir registros
    ADMIN = "admin"  # configurações, backups, restauração


_ROLE_PERMISSIONS = {
    Role.ADMIN: {Permission.WRITE, Permission.DELETE, Permission.ADMIN},
    Role.OPERATOR: {Permission.WRITE},
    Role.VIEWER: set(),
}


class AccessControl:
    def __init__(self, role: str = Role.ADMIN) -> None:
        self.role = role if role in _ROLE_PERMISSIONS else Role.VIEWER

    def can(self, permission: str) -> bool:
        return permission in _ROLE_PERMISSIONS[self.role]

    def require(self, permission: str) -> None:
        if not self.can(permission):
            raise PermissionDenied(
                f"O perfil “{Role.LABELS[self.role]}” não tem permissão para esta operação."
            )


# ----------------------------------------------------------------------------- PIN


def hash_pin(pin: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 200_000)
    return base64.b64encode(salt + digest).decode()


def verify_pin(pin: str, stored: str) -> bool:
    try:
        raw = base64.b64decode(stored)
    except ValueError:
        return False
    salt, digest = raw[:16], raw[16:]
    return hmac.compare_digest(digest, hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 200_000))


# ------------------------------------------------- proteção de configurações (DPAPI)


def _dpapi(data: bytes, encrypt: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buffer = ctypes.create_string_buffer(data, len(data))
    blob_in = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    blob_out = Blob()
    crypt32 = ctypes.windll.crypt32
    func = crypt32.CryptProtectData if encrypt else crypt32.CryptUnprotectData
    if not func(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("Falha na proteção de dados do Windows (DPAPI).")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def protect(value: str) -> str:
    """Cifra um valor de configuração para o usuário atual do Windows (DPAPI).

    Fora do Windows não há DPAPI: o valor é apenas codificado (prefixo ``b64:``)
    e segredos devem vir de variáveis de ambiente.
    """
    if sys.platform == "win32":
        return "dpapi:" + base64.b64encode(_dpapi(value.encode(), True)).decode()
    return "b64:" + base64.b64encode(value.encode()).decode()


def unprotect(value: str) -> str:
    if value.startswith("dpapi:"):
        return _dpapi(base64.b64decode(value[6:]), False).decode()
    if value.startswith("b64:"):
        return base64.b64decode(value[4:]).decode()
    return value
