"""
RDR2 Zone Hash Mapper
Maps zone hashes returned by ZONE::_GET_MAP_ZONE_AT_COORDS to human-readable locations.
"""

def joaat(text: str) -> int:
    """Computes the 32-bit signed Jenkins one-at-a-time hash used by RAGE."""
    text = text.lower()
    h = 0
    for char in text:
        h = (h + ord(char)) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h = (h ^ (h >> 6)) & 0xFFFFFFFF
    h = (h + (h << 3)) & 0xFFFFFFFF
    h = (h ^ (h >> 11)) & 0xFFFFFFFF
    h = (h + (h << 15)) & 0xFFFFFFFF
    # Convert to signed 32-bit int if needed
    if h >= 0x80000000:
        h -= 0x100000000
    return h

KNOWN_ZONES = [
    "VALENTINE",
    "STRAWBERRY",
    "RHODES",
    "SAINT_DENIS",
    "BLACKWATER",
    "ANNESBURG",
    "VAN_HORN",
    "EMERALD_RANCH",
    "COLTER",
    "ARMADILLO",
    "TUMBLEWEED",
    "MACFARLANE_RANCH",
    "CALIGA_HALL",
    "BRAITHWAITE_MANOR",
    "WAPITI",
    "BUTCHER_CREEK",
    "LAGRAS",
    "CORNHORNS",
    "GRIZZLIES_EAST",
    "GRIZZLIES_WEST",
    "BIG_VALLEY",
    "HEARTLANDS",
    "SCARLETT_MEADOWS",
    "BAYOU_NWA",
    "ROANOKE_RIDGE",
    "CUMBERLAND_FOREST",
    "CHOLLA_SPRINGS",
    "HENNIGANS_STEAD",
    "RIO_BRAVO",
    "GAPTOOTH_RIDGE"
]

ZONE_HASH_MAP = {}
for zone in KNOWN_ZONES:
    h = joaat(zone)
    ZONE_HASH_MAP[h] = zone.replace("_", " ").title()
    # Unsigned representation as well
    unsigned_h = h if h >= 0 else h + 0x100000000
    ZONE_HASH_MAP[unsigned_h] = zone.replace("_", " ").title()

def get_zone_name(zone_hash: int) -> str:
    """Returns the readable town or area name from a zone hash."""
    if zone_hash in ZONE_HASH_MAP:
        return ZONE_HASH_MAP[zone_hash]
    return "the frontier / wilderness"
