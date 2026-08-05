"""Shared "does this look like a bead-supply order email" heuristic, used by
both the Gmail and Outlook scan services so "why it matched" stays
consistent across providers. Mirrors frontend/src/lib/emailScanTypes.ts —
keep the two in sync if this list changes.
"""

BEAD_KEYWORDS = [
    "bead",
    "beads",
    "beading",
    "gem",
    "gems",
    "gemstone",
    "jewelry",
    "jewellery",
    "findings",
    "cabochon",
    "lampwork",
    "seed bead",
    "swarovski",
    "czech glass",
    "rhinestone",
    "charms",
    "pendants",
    "wire wrap",
    "fire mountain",
    "dakota stones",
    "beadaholique",
    "shipwreck beads",
    "rio grande",
    "halcraft",
    "john bead",
]


def match_reasons(from_: str, subject: str, snippet: str, vendor_names: list[str]) -> list[str]:
    reasons: list[str] = []
    haystack = f"{from_} {subject} {snippet}".lower()

    for vendor in vendor_names:
        name = vendor.strip().lower()
        if len(name) >= 4 and name in haystack:
            reasons.append(f'Matches your vendor "{vendor}"')

    keyword_hits = [kw for kw in BEAD_KEYWORDS if kw in haystack]
    if keyword_hits:
        reasons.append(f"Mentions: {', '.join(keyword_hits[:4])}")

    return reasons
