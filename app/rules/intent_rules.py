from __future__ import annotations

import re
from enum import Enum
from typing import Optional


class Intent(str, Enum):
    YES = "yes"
    NO = "no"
    MAYBE = "maybe"
    NEED_MORE_INFO = "need_more_info"
    NOT_INTERESTED = "not_interested"
    STOP = "stop"
    WRONG_PERSON = "wrong_person"
    LATER = "later"
    ALREADY_DONE = "already_done"
    OFF_TOPIC = "off_topic"
    HOSTILE = "hostile"
    AUTO_REPLY = "auto_reply"
    COMMITMENT = "commitment"
    REPETITION_COMPLAINT = "repetition_complaint"
    UNKNOWN = "unknown"


AUTO_REPLY_PATTERNS = [
    r"thank you for contacting",
    r"our team will respond",
    r"we will get back",
    r"automated assistant",
    r"business hours",
    r"bahut.?bahut shukriya",
    r"jaankari ke liye",
]

STOP_PATTERNS = [
    r"\bstop\b",
    r"not interested",
    r"don't message",
    r"do not message",
    r"unsubscribe",
    r"spam",
]

HOSTILE_PATTERNS = [
    r"\buseless\b",
    r"\bspam\b",
    r"\bshut up\b",
    r"\bidiot\b",
    r"\bhate\b",
]

COMMITMENT_PATTERNS = [
    r"\blet'?s do it\b",
    r"\bgo ahead\b",
    r"\bok lets do\b",
    r"\byes please send\b",
    r"\bstart it\b",
    r"\bproceed\b",
    r"\bdo it\b",
    r"\bsend (it|now|the)\b",
]

YES_PATTERNS = [
    r"^yes\b",
    r"\byes please\b",
    r"\bsounds good\b",
    r"\bok\b",
    r"\bokay\b",
    r"\bhaan\b",
    r"\btheek hai\b",
    r"\bchalega\b",
    r"\bconfirm\b",
]

NO_PATTERNS = [
    r"^no\b",
    r"\bnot now\b",
    r"\bmaybe later\b",
    r"\bnahi\b",
]

LATER_PATTERNS = [
    r"\blater\b",
    r"\btomorrow\b",
    r"\bnext week\b",
    r"\bgive me time\b",
    r"\bwait\b",
]

OFF_TOPIC_PATTERNS = [
    r"\bgst\b",
    r"\btax filing\b",
    r"\baccounting\b",
    r"\blegal case\b",
]

ALREADY_DONE_PATTERNS = [
    r"\balready done\b",
    r"\balready sent\b",
    r"\balready updated\b",
    r"\bho gaya\b",
    r"\bkar diya\b",
]

REPETITION_PATTERNS = [
    r"\brepeating\b",
    r"\brepeat(ing|ed)?\b",
    r"\bsame message\b",
    r"\bsame thing\b",
    r"\bagain and again\b",
    r"\bbar bar\b",
    r"\bdubara\b",
    r"\bwhy (are you|do you) send",
]


def classify_intent(message: str, prior_auto_count: int = 0) -> Intent:
    text = message.strip().lower()
    if not text:
        return Intent.UNKNOWN

    for pattern in AUTO_REPLY_PATTERNS:
        if re.search(pattern, text):
            return Intent.AUTO_REPLY

    if prior_auto_count >= 2 and len(set(text.split())) <= 12:
        return Intent.AUTO_REPLY

    for pattern in HOSTILE_PATTERNS:
        if re.search(pattern, text):
            return Intent.HOSTILE

    for pattern in STOP_PATTERNS:
        if re.search(pattern, text):
            if "not interested" in text or "stop" in text:
                return Intent.STOP
            return Intent.NOT_INTERESTED

    for pattern in COMMITMENT_PATTERNS:
        if re.search(pattern, text):
            return Intent.COMMITMENT

    for pattern in OFF_TOPIC_PATTERNS:
        if re.search(pattern, text):
            return Intent.OFF_TOPIC

    for pattern in ALREADY_DONE_PATTERNS:
        if re.search(pattern, text):
            return Intent.ALREADY_DONE

    for pattern in REPETITION_PATTERNS:
        if re.search(pattern, text):
            return Intent.REPETITION_COMPLAINT

    for pattern in LATER_PATTERNS:
        if re.search(pattern, text):
            return Intent.LATER

    for pattern in YES_PATTERNS:
        if re.search(pattern, text):
            return Intent.YES

    for pattern in NO_PATTERNS:
        if re.search(pattern, text):
            return Intent.NO

    if "?" in message:
        return Intent.NEED_MORE_INFO

    return Intent.UNKNOWN
