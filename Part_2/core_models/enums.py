from __future__ import annotations
from enum import Enum


class Phase(str, Enum):
    INFO_COLLECTION = "INFO_COLLECTION"
    QNA = "QNA"


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNSPECIFIED = "unspecified"


class HMO(str, Enum):
    MACCABI = "מכבי"
    MEUHEDET = "מאוחדת"
    CLALIT = "כללית"


class Tier(str, Enum):
    GOLD = "זהב"
    SILVER = "כסף"
    BRONZE = "ארד"


class Locale(str, Enum):
    HE = "he"
    EN = "en"
