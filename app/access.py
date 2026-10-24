"""Who may read a campus source.

Pattern from PipesHub (https://github.com/pipeshub-ai/pipeshub-ai): knowledge
stays in its own records, and a desk retrieves them under an access rule.
PipesHub itself is not installed. This module is the demo-sized version.

- public: events and places, on every student desk.
- personal: a student's own record, preferences, and mock emails that name them.
- There is no campus-wide inbox. Listing mail requires the student id.
"""

from __future__ import annotations


def describe_access(kind: str, record: dict) -> dict:
    if kind in {"event", "place"}:
        return {
            "scope": "public",
            "owner_id": None,
            "rule": "Events and places are public on the student desk.",
        }
    if kind == "user":
        return {
            "scope": "personal",
            "owner_id": record["id"],
            "rule": "The person record belongs to that student.",
        }
    if kind == "preference":
        return {
            "scope": "personal",
            "owner_id": record["user_id"],
            "rule": "A preference is cited to explain a match. It is not copied into another inbox.",
        }
    if kind == "email":
        owners = list(record.get("related_user_ids") or [])
        return {
            "scope": "personal",
            "owner_id": owners[0] if len(owners) == 1 else None,
            "owner_ids": owners,
            "rule": "A mock email is readable with the student it names. There is no all-campus inbox.",
        }
    return {"scope": "public", "owner_id": None, "rule": "Unclassified source."}


def emails_for(emails: list[dict], user_id: str) -> list[dict]:
    return [mail for mail in emails if user_id in mail.get("related_user_ids", [])]
