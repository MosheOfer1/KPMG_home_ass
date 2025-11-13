from __future__ import annotations
from enum import Enum


class Phase(str, Enum):
    """
    Represents the phases of a process with specific string values.

    This enumeration allows for a clear definition of the different phases
    in a process or workflow, such as information collection and question
    and answer phases. It ensures consistency and avoids the use of arbitrary
    string literals throughout the codebase.
    """
    INFO_COLLECTION = "INFO_COLLECTION"
    QNA = "QNA"


class Gender(str, Enum):
    """
    Represents a gender enumeration.

    This class defines a set of possible gender values as an enumeration. It can
    be used to standardize and validate gender input within an application. Each
    member of the enumeration corresponds to a specific gender or an unspecified
    value.
    """
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNSPECIFIED = "unspecified"


class HMO(str, Enum):
    """
    Represents a health maintenance organization (HMO) enumeration.

    This class provides predefined constants for different health maintenance
    organizations commonly used. The purpose of this enumeration is to
    standardize and simplify the use of HMO names within the codebase.
    """
    MACCABI = "מכבי"
    MEUHEDET = "מאוחדת"
    CLALIT = "כללית"


class Tier(str, Enum):
    """
    Represents a tier enumeration for categorizing levels with distinct values.

    This enumeration is used to specify different levels of tiers with unique
    identifiable names and corresponding Hebrew string values. It simplifies
    the management of categorization or levels in an application.

    :ivar GOLD: Represents the highest tier labeled as 'זהב'.
    :type GOLD: str
    :ivar SILVER: Represents the second tier labeled as 'כסף'.
    :type SILVER: str
    :ivar BRONZE: Represents the third tier labeled as 'ארד'.
    :type BRONZE: str
    """
    GOLD = "זהב"
    SILVER = "כסף"
    BRONZE = "ארד"


class Locale(str, Enum):
    """
    Represents a locale as an enum of string values.

    Provides two specific locale values: "he" (Hebrew) and "en" (English). This
    can be used to control localization options or select between languages
    in an application.

    :ivar HE: Hebrew locale.
    :type HE: str
    :ivar EN: English locale.
    :type EN: str
    """
    HE = "he"
    EN = "en"
