from __future__ import annotations

from fastapi import HTTPException

MAX_PATH_LENGTH = 500
MAX_TEXT_BYTES = 4 * 1024 * 1024

ALLOWED_PREFIXES = (
    "ha info",
    "ha core info",
    "ha core check",
    "ha core stats",
    "ha core restart",
    "ha supervisor info",
    "ha host info",
    "ha resolution info",
    "git -C /config ",
    "bash /config/deploy.sh",
    "python3 /config/apply_updates.py",
    "mkdir -p /config/",
    "cp -f /config/",
)

READ_ONLY_COMMANDS = {
    "ha info", "ha core info", "ha core check", "ha core stats",
    "ha supervisor info", "ha host info", "ha resolution info",
}

MUTATING_PREFIXES = (
    "ha core restart",
    "bash /config/deploy.sh",
    "python3 /config/apply_updates.py",
    "mkdir -p /config/",
    "cp -f /config/",
)

PROTECTED_DIRS = (
    ".storage", ".cloud", ".ssh", ".cache", "backups", "tts", "media",
)
PROTECTED_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".sqlite-wal", ".sqlite-shm", ".log", ".pem", ".key", ".p12", ".pfx")


def normalize_command(command: str) -> str:
    return command.strip()


def command_allowed(command: str) -> bool:
    c = normalize_command(command)
    # The 0.3.x bridge executes one shell command. We deliberately reject
    # shell chaining/redirection to avoid turning the allowlist into a bypass.
    if any(x in c for x in ("&&", "||", ";", "\n", "\r", ">", "<", "`", "$()")):
        return False
    return any(c == p.rstrip() or c.startswith(p) for p in ALLOWED_PREFIXES)


def command_is_mutating(command: str) -> bool:
    return any(normalize_command(command).startswith(p) for p in MUTATING_PREFIXES)


def safe_config_path(path: str) -> str:
    if not isinstance(path, str) or len(path) > MAX_PATH_LENGTH:
        raise HTTPException(400, "invalid relative /config path")
    p = path.strip().lstrip("/")
    if p.startswith("config/"):
        p = p[7:]
    if not p or any(part in ("", ".", "..") for part in p.split("/")):
        raise HTTPException(400, "invalid relative /config path")
    if any(p == d or p.startswith(d + "/") for d in PROTECTED_DIRS):
        raise HTTPException(403, "protected runtime path")
    if p == "secrets.yaml" or p.endswith("/secrets.yaml") or p.endswith(PROTECTED_SUFFIXES):
        raise HTTPException(403, "protected runtime/secret file")
    return p


def validate_text_content(content: str) -> None:
    if not isinstance(content, str):
        raise HTTPException(400, "content must be UTF-8 text")
    if len(content.encode("utf-8")) > MAX_TEXT_BYTES:
        raise HTTPException(413, f"content exceeds {MAX_TEXT_BYTES} byte limit")
