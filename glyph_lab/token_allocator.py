from __future__ import annotations

import string


TOKEN_POOL = (
    string.ascii_uppercase
    + string.ascii_lowercase
    + string.digits
    + "!$%&()+?@{}~"
)


def allocate_token(used_tokens: set[str]) -> str:
    for token in TOKEN_POOL:
        if token != " " and token not in used_tokens:
            return token
    raise ValueError("token pool exhausted")


def token_pool() -> list[str]:
    return [token for token in TOKEN_POOL if token != " "]
