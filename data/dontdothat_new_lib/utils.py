import hashlib
import re

def parse_version(v):
    parts = []
    for part in str(v).split("."):
        num_part = part.split("-")[0]
        try:
            parts.append(int(num_part))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)

def compare_versions(a, b):
    ta, tb = parse_version(a), parse_version(b)
    if ta < tb:
        return -1
    if ta > tb:
        return 1
    return 0

def check_version_range(version, spec):
    if not spec:
        return True
    try:
        if spec.startswith("^"):
            base = spec[1:].strip()
            current = parse_version(version)
            target = parse_version(base)
            return current[0] == target[0] and current >= target
        if spec.startswith("~"):
            base = spec[1:].strip()
            current = parse_version(version)
            target = parse_version(base)
            return current[:2] == target[:2] and current >= target
        parts = [p.strip() for p in spec.split(",")]
        for p in parts:
            if not p:
                continue
            if p.startswith(">="):
                if compare_versions(version, p[2:].strip()) < 0:
                    return False
            elif p.startswith("<="):
                if compare_versions(version, p[2:].strip()) > 0:
                    return False
            elif p.startswith(">"):
                if compare_versions(version, p[1:].strip()) <= 0:
                    return False
            elif p.startswith("<"):
                if compare_versions(version, p[1:].strip()) >= 0:
                    return False
            elif p.startswith("=="):
                if compare_versions(version, p[2:].strip()) != 0:
                    return False
            else:
                if compare_versions(version, p) != 0:
                    return False
        return True
    except Exception:
        return True

def sha1(s):
    return hashlib.sha1(s.encode("utf-8", errors="ignore")).hexdigest()

def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()

def is_valid_name(name):
    if not name:
        return False
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9_\-]{1,63}$", name))
