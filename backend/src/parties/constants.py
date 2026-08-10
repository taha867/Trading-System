from enum import Enum


class PartyRole(str, Enum):
    CHINA_VENDOR = "china_vendor"
    CARGO_AGENT = "cargo_agent"
    CUSTOMER = "customer"
    LOCAL_VENDOR = "local_vendor"


PARTY_ROLES = tuple(role.value for role in PartyRole)
