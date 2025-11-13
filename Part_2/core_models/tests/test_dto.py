import pytest
from ..dto import UserProfile, HMO, Tier


def test_user_profile_accepts_9_digit_strings():
    u = UserProfile(id_number="012345678", hmo_name=HMO.MACCABI, membership_tier=Tier.GOLD, birth_year=1995)
    assert u.id_number == "012345678"

def test_invalid_birth_year_raises():
    with pytest.raises(Exception):
        UserProfile(birth_year=1800)
