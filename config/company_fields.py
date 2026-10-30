"""Company settings shared by general settings and document generation."""

COMPANY_GROUPS = {
    'Identificarea firmei': {
        'executant_denumire': 'Denumire firma', 'executant_cui': 'CUI',
        'executant_regcom': 'Numar Registrul Comertului',
        'executant_reprezentant': 'Reprezentant legal',
        'executant_reprezentant_calitate': 'Calitatea reprezentantului',
        'executant_telefon': 'Telefon firma', 'executant_email': 'E-mail firma si cereri GDPR',
    },
    'Sediul social': {
        'executant_judet': 'Judet', 'executant_localitate': 'Localitate',
        'executant_strada': 'Strada', 'executant_numar': 'Numar',
        'executant_bloc': 'Bloc', 'executant_scara': 'Scara', 'executant_etaj': 'Etaj',
        'executant_apartament': 'Apartament', 'executant_cod_postal': 'Cod postal',
    },
    'Date bancare': {'executant_banca': 'Banca', 'executant_iban': 'IBAN'},
    'Autorizatie ANRE proiectare': {
        'autorizatie_proiectare_tip': 'Tip autorizatie proiectare',
        'autorizatie_proiectare_numar': 'Numar autorizatie proiectare',
        'autorizatie_proiectare_expirare': 'Data expirarii proiectare',
    },
    'Autorizatie ANRE executie': {
        'autorizatie_executie_tip': 'Tip autorizatie executie',
        'autorizatie_executie_numar': 'Numar autorizatie executie',
        'autorizatie_executie_expirare': 'Data expirarii executie',
    },
    'Protectia datelor personale': {
        'gdpr_contact_dpo': 'Contact DPO daca exista un responsabil desemnat',
        'gdpr_pastrare_contract': 'Pastrare contract si corespondenta',
        'gdpr_pastrare_tehnic': 'Pastrare dosar tehnic',
        'gdpr_pastrare_contabil': 'Pastrare documente fiscal-contabile',
        'gdpr_pastrare_acte': 'Pastrare copii acte de identitate si proprietate',
        'gdpr_transferuri': 'Servicii externe si eventuale transferuri in afara SEE',
    },
}
COMPANY_FIELDS = {key: label for group in COMPANY_GROUPS.values() for key, label in group.items()}

