from __future__ import annotations
from typing import List, Optional
from datetime import datetime

from pydantic import BaseModel, Field, constr, ConfigDict

from .enums import Phase, Gender, HMO, Tier, Locale


NineDigit = constr(pattern=r"^\d{9}$")


class UserProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    id_number: Optional[NineDigit] = None          # Israeli Teudat Zehut as 9-digit string
    gender: Optional[Gender] = Gender.UNSPECIFIED
    birth_year: Optional[int] = Field(default=None, ge=1900, le=datetime.utcnow().year)
    hmo_name: Optional[HMO] = None
    hmo_card_number: Optional[NineDigit] = None     # 9-digit string
    membership_tier: Optional[Tier] = None
    locale: Locale = Locale.HE


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_text: Optional[str] = None
    assistant_text: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    citations: List[str] = Field(default_factory=list)  # source URIs/anchors


class ConversationHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    turns: List[Turn] = Field(default_factory=list)


class SessionBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_profile: UserProfile
    history: ConversationHistory = Field(default_factory=ConversationHistory)
    phase: Phase = Phase.INFO_COLLECTION
    locale: Locale = Locale.HE
    request_id: Optional[str] = None


class GroundedSnippet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    source_uri: str
    section: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_bundle: SessionBundle
    user_input: str


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assistant_text: str
    suggested_phase: Phase
    user_profile: UserProfile
    citations: List[str] = Field(default_factory=list)
    validation_flags: List[str] = Field(default_factory=list)
    trace_id: Optional[str] = None
