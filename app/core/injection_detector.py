import re
from typing import List


_PATTERNS = [
    (r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)", "override_attempt"),
    (r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)", "override_attempt"),
    (r"forget\s+(all|everything)\s+(you|previous|prior)", "override_attempt"),
    (r"you\s+are\s+now\s+(a|an)\s+", "role_hijack"),
    (r"act\s+as\s+(if\s+)?(you|a|an)\s+", "role_hijack"),
    (r"pretend\s+(to\s+be|you\s+are)", "role_hijack"),
    (r"jailbreak", "override_attempt"),
    (r"system\s*[:\-]\s*", "system_prompt_injection"),
    (r"###\s*(system|instruction|assistant)", "system_prompt_injection"),
    (r"<\s*/?\s*(system|instructions?)\s*>", "system_prompt_injection"),
    (r"reveal\s+(your|the)\s+(system\s+)?(prompt|instructions?)", "prompt_extraction"),
    (r"print\s+(your|the)\s+(system\s+)?(prompt|instructions?)", "prompt_extraction"),
    (r"approve\s+(this|the)\s+(employee|user|request)\s+(automatically|without)", "unauthorized_action"),
    (r"grant\s+(all|full|admin)\s+(access|permissions?|rights?)", "unauthorized_action"),
    (r"bypass\s+(all|the)\s+(checks?|validations?|security)", "unauthorized_action"),
    (r"execute\s+(the\s+)?(following|below)\s+(code|command|script)", "code_execution"),
    (r"run\s+this\s+(code|command|script)", "code_execution"),
    (r"you\s+must\s+(always|now)\s+", "override_attempt"),
    (r"new\s+instructions?\s*[:\-]", "override_attempt"),
    (r"override\s+(your|the|all)\s+(rules?|instructions?|guidelines?)", "override_attempt"),
]

_COMPILED = [(re.compile(pat, re.IGNORECASE | re.DOTALL), tag) for pat, tag in _PATTERNS]


def detect_injection_flags(text: str) -> List[str]:
    if not text:
        return []
    hits = set()
    for regex, tag in _COMPILED:
        if regex.search(text):
            hits.add(tag)
    return sorted(hits)


def flags_to_string(flags: List[str]) -> str:
    return ",".join(flags) if flags else ""
