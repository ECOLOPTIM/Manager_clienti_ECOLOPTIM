"""Shared workflow families; only discussed and approved templates are enabled.

Work types remain distinct for reporting and pricing. Several work types may use
one family/template; no inference that a particular installation needs no design.
"""
FAMILIES = {
    'fara_proiectare': 'Executie fara proiectare',
    'cu_proiectare': 'Proiectare si executie',
    'doar_proiectare': 'Doar proiectare',
}

TEMPLATES = {
    'Instalatie de utilizare noua': {
        'family': 'cu_proiectare', 'template': 'iugn01', 'version': 2,
    },
}


def template_for(work_type):
    """None means keep the existing workflow until its rules have been defined."""
    return TEMPLATES.get(work_type)
