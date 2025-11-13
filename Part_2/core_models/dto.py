from __future__ import annotations
from typing import List, Optional
from datetime import datetime, UTC

from pydantic import BaseModel, Field, constr, ConfigDict

from .enums import Phase, Gender, HMO, Tier, Locale


NineDigit = constr(pattern=r"^\d{9}$")


class UserProfile(BaseModel):
    """
    Represents a user profile with personal and membership details.

    This class is used to store and manage information related to a user's profile,
    including personal details such as name, gender, and date of birth, as well as
    membership-related details. It enforces strict validation on input data to ensure
    data integrity.

    :ivar first_name: The first name of the user.
    :type first_name: Optional[str]
    :ivar last_name: The last name of the user.
    :type last_name: Optional[str]
    :ivar id_number: The Israeli Teudat Zehut number, stored as a 9-digit string.
    :type id_number: Optional[NineDigit]
    :ivar gender: The gender of the user.
    :type gender: Optional[Gender]
    :ivar birth_year: The birth year of the user, constrained between 1900 and
        the current year.
    :type birth_year: Optional[int]
    :ivar hmo_name: The name of the Health Maintenance Organization (HMO) affiliated
        with the user.
    :type hmo_name: Optional[HMO]
    :ivar hmo_card_number: The membership card number for the HMO, stored as a
        9-digit string.
    :type hmo_card_number: Optional[NineDigit]
    :ivar membership_tier: The membership tier level associated with the user.
    :type membership_tier: Optional[Tier]
    """
    model_config = ConfigDict(extra="forbid")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    id_number: Optional[NineDigit] = None          # Israeli Teudat Zehut as 9-digit string
    gender: Optional[Gender] = Gender.UNSPECIFIED
    birth_year: Optional[int] = Field(default=None, ge=1900, le=datetime.now(UTC).year)
    hmo_name: Optional[HMO] = None
    hmo_card_number: Optional[NineDigit] = None     # 9-digit string
    membership_tier: Optional[Tier] = None


class Turn(BaseModel):
    """
    Represents a conversation turn between a user and an assistant.

    This class is used to store the interaction of a single turn in a dialogue,
    including the user's input, the assistant's response, and any associated
    citations. It ensures that all extra fields are forbidden and that the turn
    structure adheres to the defined model configuration.

    :ivar user_text: The text provided by the user during this turn.
    :type user_text: Optional[str]
    :ivar assistant_text: The assistant's response text for this turn.
    :type assistant_text: Optional[str]
    :ivar citations: A list of citation URIs or anchors associated with this
        turn for reference.
    :type citations: List[str]
    """
    model_config = ConfigDict(extra="forbid")
    user_text: Optional[str] = None
    assistant_text: Optional[str] = None
    citations: List[str] = Field(default_factory=list)  # source URIs/anchors


class ConversationHistory(BaseModel):
    """
    Represents the conversation history, encapsulating a sequence of dialogue
    turns and configuration constraints.

    This class is designed to store and manage the history of a conversation,
    represented as a series of dialogue turns. It includes a configuration
    setting that forbids additional unstructured attributes, ensuring its usage
    remains controlled and structured.

    :ivar model_config: Configuration that prohibits extra attributes.
    :type model_config: ConfigDict
    :ivar turns: A list of dialog turns representing the conversation history.
    :type turns: List[Turn]
    """
    model_config = ConfigDict(extra="forbid")
    turns: List[Turn] = Field(default_factory=list)


class SessionBundle(BaseModel):
    """
    Represents a session bundle for managing related session data.

    The SessionBundle class encapsulates all necessary information and states
    required to manage a session, including user profile, conversation history,
    phase of the session, locale, and an optional request identifier. It ensures
    tight validation and control over the attributes using the model configuration.

    :ivar model_config: Configuration settings for the data model, specifying
        additional validation behavior.
    :type model_config: ConfigDict
    :ivar user_profile: The user's profile containing their details and settings.
    :type user_profile: UserProfile
    :ivar history: The conversation history associated with the session.
    :type history: ConversationHistory
    :ivar phase: The current operational phase of the session.
    :type phase: Phase
    :ivar locale: The locale settings to define language and region-specific details.
    :type locale: Locale
    :ivar request_id: An optional identifier for tracking the request within the session.
    :type request_id: Optional[str]
    """
    model_config = ConfigDict(extra="forbid")
    user_profile: UserProfile
    history: ConversationHistory = Field(default_factory=ConversationHistory)
    phase: Phase = Phase.INFO_COLLECTION
    locale: Locale = Locale.HE
    request_id: Optional[str] = None


class ChatRequest(BaseModel):
    """
    Represents a chat request containing a session bundle and user input.

    This class is used to encapsulate the required data for processing a chat
    request, including the session bundle for session context management and
    the input provided by the user.

    :ivar session_bundle: Represents the session bundle, which manages session
        context for the chat request.
    :type session_bundle: SessionBundle
    :ivar user_input: The input provided by the user as part of the chat request.
    :type user_input: str
    """
    model_config = ConfigDict(extra="forbid")
    session_bundle: SessionBundle
    user_input: str


class ChatResponse(BaseModel):
    """
    Represents a structured response to a chat interaction.

    This class is responsible for modeling the data structure of a chat response that
    includes the assistant's text reply, suggested next phase, user profile, citations,
    validation flags, and an optional trace ID for tracking. It ensures that only the
    specified fields are allowed in its structure.

    :ivar assistant_text: The assistant's textual response to the user's input.
    :type assistant_text: str
    :ivar suggested_phase: The suggested next phase or state in the chat process.
    :type suggested_phase: Phase
    :ivar user_profile: Contains information about the user's profile relevant to the chat.
    :type user_profile: UserProfile
    :ivar citations: A list of references or sources cited within the assistant's response.
    :type citations: List[str]
    :ivar validation_flags: A list of validation flags indicating any issues or noteworthy
        items regarding the assistant's response.
    :type validation_flags: List[str]
    :ivar trace_id: An optional identifier for tracing or debugging the interaction.
    :type trace_id: Optional[str]
    """
    model_config = ConfigDict(extra="forbid")
    assistant_text: str
    suggested_phase: Phase
    user_profile: UserProfile
    citations: List[str] = Field(default_factory=list)
    validation_flags: List[str] = Field(default_factory=list)
    trace_id: Optional[str] = None
