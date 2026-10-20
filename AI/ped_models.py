"""
RDR2 Exact Ped Model & Relationship Group Registry
Extracted directly from RDR2 game binaries.
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
    if h >= 0x80000000:
        h -= 0x100000000
    return h

# Exact RDR2 character models extracted from the game engine
KNOWN_MODELS = {
    # --- Valentine ---
    "cs_valsheriff": "Sheriff Curtis Malloy (Valentine Sheriff)",
    "u_m_m_valsheriff_01": "Sheriff Curtis Malloy (Valentine Sheriff)",
    "s_m_m_valdeputy_01": "Valentine Deputy",
    "cs_valdeputy_01": "Valentine Deputy",
    "a_m_m_valdeputyresident_01": "Valentine Deputy",
    "u_m_m_valbartender_01": "Valentine Saloon Bartender",
    "u_m_m_valdoctor_01": "Valentine Doctor",
    "u_m_m_valgunsmith_01": "Valentine Gunsmith",
    "u_m_m_valbarber_01": "Valentine Barber",
    "u_m_m_valbutcher_01": "Valentine Butcher",
    "u_m_m_valgenstoreowner_01": "Valentine General Store Owner",
    "u_m_m_valhotelowner_01": "Valentine Hotel Owner",
    "cs_valauctionboss_01": "Valentine Auction Boss",
    "s_m_m_valbankguards_01": "Valentine Bank Guard",

    # --- Rhodes ---
    "u_m_m_rhdsheriff_01": "Sheriff Leigh Gray (Rhodes Sheriff)",
    "cs_rhodeputy_01": "Rhodes Deputy",
    "cs_rhodeputy_02": "Rhodes Deputy",
    "u_m_m_rhdbackupdeputy_01": "Rhodes Deputy",
    "u_m_m_rhdbackupdeputy_02": "Rhodes Deputy",
    "a_m_m_rhddeputyresident_01": "Rhodes Deputy",
    "u_m_m_rhdbartender_01": "Rhodes Saloon Bartender",
    "u_m_m_rhdgunsmith_01": "Rhodes Gunsmith",
    "u_m_m_rhddoctor_01": "Rhodes Doctor",

    # --- Strawberry ---
    "cs_strsheriff_01": "Sheriff Hanley (Strawberry Sheriff)",
    "cs_sheriffowens": "Sheriff Owens",
    "cs_strdeputy_01": "Strawberry Deputy",
    "cs_strdeputy_02": "Strawberry Deputy",
    "a_m_m_strdeputyresident_01": "Strawberry Deputy",

    # --- Saint Denis ---
    "u_m_m_sdpolicechief_01": "Police Chief Benjamin Lambert (Saint Denis)",
    "cs_nbxpolicechiefformal": "Police Chief Benjamin Lambert (Saint Denis)",
    "cs_mp_policechief_lambert": "Police Chief Benjamin Lambert (Saint Denis)",
    "s_m_m_ambientsdpolice_01": "Saint Denis Police Officer",
    "u_m_m_nbxbartender_01": "Saint Denis Bartender",
    "u_m_m_nbxbartender_02": "Saint Denis Bartender",
    "u_m_m_nbxgunsmith_01": "Saint Denis Gunsmith",
    "cs_sddoctor_01": "Saint Denis Doctor",
    "cs_creoledoctor": "Saint Denis Doctor",

    # --- Tumbleweed, Armadillo & Annesburg ---
    "cs_sherifffreeman": "Sheriff Freeman (Tumbleweed Sheriff)",
    "u_m_m_tumbartender_01": "Tumbleweed Saloon Bartender",
    "u_m_m_tumgunsmith_01": "Tumbleweed Gunsmith",
    "u_m_m_tumbutcher_01": "Tumbleweed Butcher",
    "a_m_m_armdeputyresident_01": "Armadillo Deputy",
    "u_m_o_asbsheriff_01": "Annesburg Sheriff",
    "a_m_m_asbdeputyresident_01": "Annesburg Deputy",
    "cs_asbdeputy_01": "Annesburg Deputy",
    "u_m_m_asbgunsmith_01": "Annesburg Gunsmith",
    "u_m_m_annminer_01": "Annesburg Coal Miner",

    # --- Generic Law & Guards ---
    "s_m_m_ambientblwpolice_01": "Blackwater Police Officer",
    "s_m_m_dispatchpolice_01": "Mounted Lawman",
    "s_m_m_dispatchleaderpolice_01": "Law Posse Leader",
    "s_m_m_barber_01": "Barber",
    "s_m_m_unibutchers_01": "Butcher",

    # --- Van der Linde Gang Members ---
    "cs_dutch": "Dutch van der Linde",
    "cs_johnmarston": "John Marston",
    "cs_micahbell": "Micah Bell",
    "cs_hoseamatthews": "Hosea Matthews",
    "cs_billwilliamson": "Bill Williamson",
    "cs_charlessmith": "Charles Smith",
    "cs_javierescuella": "Javier Escuella",
    "cs_mrpearson": "Simon Pearson (Camp Cook)",
    "cs_leostrauss": "Leopold Strauss",
    "cs_revswanson": "Reverend Swanson",
    "cs_abigailroberts": "Abigail Roberts",
    "cs_uncle": "Uncle",
    "cs_lenny": "Lenny Summers",
    "cs_sean": "Sean MacGuire",
    "cs_karen": "Karen Jones",
    "cs_marybeth": "Mary-Beth Gaskill",
    "cs_tilly": "Tilly Jackson",
    "cs_kieran": "Kieran Duffy"
}

# Relationship group identifiers
KNOWN_REL_GROUPS = {
    "rel_cop": "Law Enforcement",
    "rel_law": "Law Enforcement",
    "law_val_sheriff": "Valentine Sheriff's Office",
    "rel_gang_odriscoll": "O'Driscoll Gang Member",
    "rel_gang_lemoyne_raiders": "Lemoyne Raider",
    "rel_gang_murfree": "Murfree Brood",
    "rel_gang_skinner_brothers": "Skinner Brother",
    "rel_gang_del_lobo": "Del Lobo Outlaw",
    "rel_guards_cornwall": "Cornwall Mercenary Guard",
    "rel_braithwaite": "Braithwaite Family Guard",
    "rel_gray": "Gray Family Guard"
}

MODEL_HASH_MAP = {}
for name, label in KNOWN_MODELS.items():
    h = joaat(name)
    MODEL_HASH_MAP[h] = label
    unsigned_h = h if h >= 0 else h + 0x100000000
    MODEL_HASH_MAP[unsigned_h] = label

REL_GROUP_MAP = {}
for name, label in KNOWN_REL_GROUPS.items():
    h = joaat(name)
    REL_GROUP_MAP[h] = label
    unsigned_h = h if h >= 0 else h + 0x100000000
    REL_GROUP_MAP[unsigned_h] = label

def get_ped_occupation(model_hash: int, rel_hash: int = 0) -> str:
    """Returns the specific occupation or identity from the engine model and relationship hashes."""
    if model_hash in MODEL_HASH_MAP:
        return MODEL_HASH_MAP[model_hash]
    if rel_hash in REL_GROUP_MAP:
        return REL_GROUP_MAP[rel_hash]
    return ""
