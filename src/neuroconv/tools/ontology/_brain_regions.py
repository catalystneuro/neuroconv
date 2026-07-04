"""Lightweight, offline recognition of mouse brain regions as Allen Mouse Brain Atlas terms.

NWB stores an anatomical location as a free-text string (e.g. the ``location`` column of the
electrodes table, ``ElectrodeGroup.location``, or ``ImagingPlane.location``). For the mouse, the
Allen Mouse Brain Atlas (MBA) provides a standard controlled vocabulary of brain structures, each
with a numeric identifier. Recognizing a location string as an MBA term lets NeuroConv attach a
machine-readable reference (``MBA:<id>``) so downstream tools can resolve the exact structure.

This is intentionally a small curated table of common neuroscience structures rather than a full
ontology client: it runs offline, has no extra dependencies, and only resolves a term when it is
confident. Identifiers and names below are taken from the Allen Mouse Brain CCFv3 structure graph
and are registered in the Bioregistry under the ``MBA`` prefix (https://bioregistry.io/registry/mba).
"""

from dataclasses import dataclass

__all__ = [
    "MBA_TERMS",
    "BrainRegionTerm",
    "get_brain_region_term",
]


@dataclass(frozen=True)
class BrainRegionTerm:
    """An Allen Mouse Brain Atlas structure with its numeric MBA identifier."""

    acronym: str
    mba_id: int
    name: str

    @property
    def curie(self) -> str:
        """The compact identifier for the structure (e.g. ``"MBA:382"``)."""
        return f"MBA:{self.mba_id}"

    @property
    def entity_uri(self) -> str:
        """Resolvable URI for the MBA entity (usable as a HERD ``entity_uri``)."""
        return f"https://purl.brain-bican.org/ontology/mbao/MBA_{self.mba_id}"


# Allen acronym -> (MBA numeric id, canonical name), from the CCFv3 structure graph.
_ACRONYM_TO_ID_AND_NAME: dict[str, tuple[int, str]] = {
    # Gross divisions
    "root": (997, "root"),
    "grey": (8, "Basic cell groups and regions"),
    "CH": (567, "Cerebrum"),
    "BS": (343, "Brain stem"),
    "CTX": (688, "Cerebral cortex"),
    "CNU": (623, "Cerebral nuclei"),
    "Isocortex": (315, "Isocortex"),
    # Isocortical areas
    "MOp": (985, "Primary motor area"),
    "MOs": (993, "Secondary motor area"),
    "SSp": (322, "Primary somatosensory area"),
    "SSs": (378, "Supplemental somatosensory area"),
    "SSp-bfd": (329, "Primary somatosensory area, barrel field"),
    "VISp": (385, "Primary visual area"),
    "VISl": (409, "Lateral visual area"),
    "VISal": (402, "Anterolateral visual area"),
    "VISam": (394, "Anteromedial visual area"),
    "VISpm": (533, "posteromedial visual area"),
    "VISrl": (417, "Rostrolateral visual area"),
    "VISpl": (425, "Posterolateral visual area"),
    "VISpor": (312782628, "Postrhinal area"),
    "AUDp": (1002, "Primary auditory area"),
    "AUDd": (1011, "Dorsal auditory area"),
    "ACAd": (39, "Anterior cingulate area, dorsal part"),
    "ACAv": (48, "Anterior cingulate area, ventral part"),
    "PL": (972, "Prelimbic area"),
    "ILA": (44, "Infralimbic area"),
    "ORBl": (723, "Orbital area, lateral part"),
    "ORBm": (731, "Orbital area, medial part"),
    "RSPd": (879, "Retrosplenial area, dorsal part"),
    "RSPv": (886, "Retrosplenial area, ventral part"),
    "AId": (104, "Agranular insular area, dorsal part"),
    "TEa": (541, "Temporal association areas"),
    "PERI": (922, "Perirhinal area"),
    "ECT": (895, "Ectorhinal area"),
    "GU": (1057, "Gustatory areas"),
    "VISC": (677, "Visceral area"),
    "PTLp": (22, "Posterior parietal association areas"),
    # Hippocampal formation
    "HPF": (1089, "Hippocampal formation"),
    "HIP": (1080, "Hippocampal region"),
    "CA1": (382, "Field CA1"),
    "CA2": (423, "Field CA2"),
    "CA3": (463, "Field CA3"),
    "DG": (726, "Dentate gyrus"),
    "SUB": (502, "Subiculum"),
    "ProS": (484682470, "Prosubiculum"),
    "POST": (1037, "Postsubiculum"),
    "PRE": (1084, "Presubiculum"),
    "PAR": (843, "Parasubiculum"),
    "ENT": (909, "Entorhinal area"),
    "ENTl": (918, "Entorhinal area, lateral part"),
    "ENTm": (926, "Entorhinal area, medial part, dorsal zone"),
    # Olfactory areas
    "OLF": (698, "Olfactory areas"),
    "MOB": (507, "Main olfactory bulb"),
    "PIR": (961, "Piriform area"),
    "AON": (159, "Anterior olfactory nucleus"),
    # Cortical subplate / amygdala
    "BLA": (295, "Basolateral amygdalar nucleus"),
    "CEA": (536, "Central amygdalar nucleus"),
    "MEA": (403, "Medial amygdalar nucleus"),
    "LA": (131, "Lateral amygdalar nucleus"),
    # Cerebral nuclei
    "STR": (477, "Striatum"),
    "CP": (672, "Caudoputamen"),
    "ACB": (56, "Nucleus accumbens"),
    "PAL": (803, "Pallidum"),
    "LSr": (258, "Lateral septal nucleus, rostral (rostroventral) part"),
    # Thalamus
    "TH": (549, "Thalamus"),
    "VPM": (733, "Ventral posteromedial nucleus of the thalamus"),
    "VPL": (718, "Ventral posterolateral nucleus of the thalamus"),
    "VM": (685, "Ventral medial nucleus of the thalamus"),
    "VAL": (629, "Ventral anterior-lateral complex of the thalamus"),
    "MD": (362, "Mediodorsal nucleus of thalamus"),
    "LGd": (170, "Dorsal part of the lateral geniculate complex"),
    "LP": (218, "Lateral posterior nucleus of the thalamus"),
    "PO": (1020, "Posterior complex of the thalamus"),
    "RT": (262, "Reticular nucleus of the thalamus"),
    # Hypothalamus
    "HY": (1097, "Hypothalamus"),
    "LHA": (194, "Lateral hypothalamic area"),
    "PVH": (38, "Paraventricular hypothalamic nucleus"),
    "ZI": (797, "Zona incerta"),
    # Midbrain
    "MB": (313, "Midbrain"),
    "SCs": (302, "Superior colliculus, sensory related"),
    "SCm": (294, "Superior colliculus, motor related"),
    "IC": (4, "Inferior colliculus"),
    "PAG": (795, "Periaqueductal gray"),
    "VTA": (749, "Ventral tegmental area"),
    "SNr": (381, "Substantia nigra, reticular part"),
    "SNc": (374, "Substantia nigra, compact part"),
    "RN": (214, "Red nucleus"),
    "APN": (215, "Anterior pretectal nucleus"),
    "MRN": (128, "Midbrain reticular nucleus"),
    # Hindbrain
    "P": (771, "Pons"),
    "PB": (867, "Parabrachial nucleus"),
    "PG": (931, "Pontine gray"),
    "DR": (872, "Dorsal nucleus raphe"),
    "LC": (147, "Locus ceruleus"),
    "MY": (354, "Medulla"),
    "NTS": (651, "Nucleus of the solitary tract"),
    "IO": (83, "Inferior olivary complex"),
    # Cerebellum
    "CB": (512, "Cerebellum"),
}


MBA_TERMS: dict[str, BrainRegionTerm] = {
    acronym: BrainRegionTerm(acronym=acronym, mba_id=mba_id, name=name)
    for acronym, (mba_id, name) in _ACRONYM_TO_ID_AND_NAME.items()
}


# Canonical name (lower-cased) -> acronym, so full names written into ``location`` also resolve.
_NAME_TO_ACRONYM: dict[str, str] = {term.name.lower(): term.acronym for term in MBA_TERMS.values()}


# Common informal names and abbreviations -> Allen acronym. Compared case-insensitively.
_ALIAS_TO_ACRONYM: dict[str, str] = {
    "hippocampus": "HIP",
    "entorhinal cortex": "ENT",
    "primary visual cortex": "VISp",
    "v1": "VISp",
    "primary motor cortex": "MOp",
    "m1": "MOp",
    "primary somatosensory cortex": "SSp",
    "s1": "SSp",
    "barrel cortex": "SSp-bfd",
    "neocortex": "Isocortex",
    "dorsal striatum": "CP",
    "locus coeruleus": "LC",
    "substantia nigra pars compacta": "SNc",
    "substantia nigra pars reticulata": "SNr",
    "periaqueductal grey": "PAG",
}


def get_brain_region_term(location: str) -> BrainRegionTerm | None:
    """
    Resolve a free-text location string to an Allen Mouse Brain Atlas term.

    The lookup is high-precision: it matches an exact Allen acronym (case-sensitive, e.g.
    ``"CA1"``), a canonical structure name (case-insensitive, e.g. ``"caudoputamen"``), or a
    small set of common informal names and abbreviations (e.g. ``"hippocampus"``, ``"V1"``).
    Anything it does not recognize returns ``None``.

    Parameters
    ----------
    location : str
        The anatomical location string as written to an NWB ``location`` field.

    Returns
    -------
    BrainRegionTerm or None
        The recognized MBA term, or ``None`` when the string cannot be resolved.
    """
    if not isinstance(location, str):
        return None

    stripped = location.strip()
    if stripped == "":
        return None

    # Exact Allen acronym (case-sensitive: acronyms like "VISp" and "MOp" are case-specific).
    if stripped in MBA_TERMS:
        return MBA_TERMS[stripped]

    lowered = stripped.lower()
    acronym = _NAME_TO_ACRONYM.get(lowered) or _ALIAS_TO_ACRONYM.get(lowered)
    if acronym is not None:
        return MBA_TERMS[acronym]

    return None
