"""IUGN 01 v2, first delivery: recorded milestones and parallel work streams.

Documents, invoicing and automatic due dates are separate deliveries. A milestone
here records an operator's confirmation; it does not create a signed document.
"""
from copy import deepcopy
from datetime import date

WORK_TYPE = 'Instalatie de utilizare noua'
ROLES = {'responsabil': 'Responsabil lucrare', 'proiectant': 'Proiectant',
         'comercial': 'Comercial / financiar'}
# key, label, stream, owner, prerequisites
STEPS = (
    ('oferta_acceptata', 'Oferta acceptata', 'dosar', 'comercial', ()),
    ('documente_complete', 'Documentele clientului colectate', 'dosar', 'responsabil', ('oferta_acceptata',)),
    ('contract_emis', 'Contract emis', 'dosar', 'comercial', ('documente_complete',)),
    ('contract_semnat', 'Contract semnat', 'dosar', 'comercial', ('contract_emis',)),
    ('avans_confirmat', 'Avans incasat - confirmare', 'dosar', 'comercial', ('contract_emis',)),
    ('cerere_depusa', 'Cerere de racordare depusa', 'dosar', 'responsabil', ('contract_emis',)),
    ('nota_analiza_transmisa', 'Nota analiza dosar transmisa clientului', 'dosar', 'responsabil', ('cerere_depusa',)),
    ('notificare_primita', 'Notificare de racordare primita', 'dosar', 'responsabil', ('cerere_depusa',)),
    ('notificare_proiectant', 'Notificare transmisa proiectantului', 'proiect', 'responsabil', ('notificare_primita',)),
    ('proiect_intocmit', 'Proiect intocmit', 'proiect', 'proiectant', ('notificare_proiectant',)),
    ('proiect_avizat', 'Proiect avizat, inclusiv izometrie', 'proiect', 'responsabil', ('proiect_intocmit',)),
    ('executie_programata', 'Ziua executiei stabilita', 'executie', 'manager', ('notificare_primita',)),
    ('ordin_executie_predat', 'Ordin executie emis si predat echipei', 'executie', 'responsabil', ('executie_programata',)),
    ('executie_finalizata', 'Executie finalizata', 'executie', 'responsabil', ('ordin_executie_predat',)),
    ('ordin_executie_arhivat', 'Ordin executie completat si arhivat', 'executie', 'responsabil', ('executie_finalizata',)),
    ('contract_furnizare', 'Contract de furnizare disponibil', 'pif', 'responsabil', ('contract_emis',)),
    ('solicitare_pif', 'Solicitare PIF depusa cu dosarul complet', 'pif', 'responsabil', ('executie_finalizata', 'proiect_avizat', 'contract_furnizare')),
    ('nota_pif_transmisa', 'Nota PIF transmisa clientului', 'pif', 'responsabil', ('solicitare_pif',)),
    ('programare_pif_primita', 'Programare PIF primita de la Distrigaz', 'pif', 'responsabil', ('solicitare_pif',)),
    ('echipa_pif_alocata', 'Echipa PIF alocata', 'pif', 'manager', ('programare_pif_primita',)),
    ('dosar_pif_predat', 'Ordin si dosar PIF predate echipei', 'pif', 'responsabil', ('echipa_pif_alocata',)),
    ('pif_efectuata', 'PIF efectuata cu succes', 'pif', 'responsabil', ('dosar_pif_predat',)),
    ('copie_pv_pif_arhivata', 'Copia PV PIF si ordinul completat arhivate', 'pif', 'responsabil', ('pif_efectuata',)),
)
BY_KEY = {step[0]: step for step in STEPS}
EXCEPTIONS = {'exceptie_contract': 'Exceptie: semnatura contractului in asteptare',
              'exceptie_avans': 'Exceptie: avans in asteptare',
              'executie_fara_proiect': 'Decizie responsabil: executie cu proiect nefinalizat'}
RESCHEDULES = {'reprogramare_executie': 'Executie amanata / reprogramata',
               'reprogramare_pif': 'PIF amanata / reprogramata'}
EVENT_LABELS = {k: label for k, label, *_ in STEPS} | EXCEPTIONS | RESCHEDULES


def initial_state():
    return {'facts': {}, 'roles': {k: '' for k in ROLES}, 'exceptions': {}}


def contract_ready(state):
    return ('contract_emis' in state['facts'] and
            ('contract_semnat' in state['facts'] or 'exceptie_contract' in state['exceptions']))


def blocked_reason(state, key):
    facts = state['facts']
    if key in RESCHEDULES:
        schedule, finished = (('executie_programata', 'executie_finalizata')
                              if key == 'reprogramare_executie' else ('programare_pif_primita', 'pif_efectuata'))
        if schedule not in facts:
            return 'Lipseste: ' + EVENT_LABELS[schedule]
        return 'Etapa a fost deja efectuata.' if finished in facts else ''
    if key in EXCEPTIONS:
        if key in state['exceptions']:
            return 'Decizia este deja inregistrata.'
        needed = 'notificare_primita' if key == 'executie_fara_proiect' else 'contract_emis'
        if needed not in facts:
            return 'Lipseste: ' + EVENT_LABELS[needed]
        if key == 'executie_fara_proiect' and not state['roles']['responsabil']:
            return 'Desemneaza responsabilul lucrarii.'
        resolved = {'exceptie_contract': 'contract_semnat', 'exceptie_avans': 'avans_confirmat',
                    'executie_fara_proiect': 'proiect_avizat'}[key]
        return 'Situatia este deja rezolvata.' if resolved in facts else ''
    if key not in BY_KEY:
        return 'Eveniment necunoscut.'
    if key in facts:
        return 'Evenimentul este deja inregistrat.'
    missing = [EVENT_LABELS[x] for x in BY_KEY[key][4] if x not in facts]
    if missing:
        return 'Lipseste: ' + ', '.join(missing)
    if key == 'cerere_depusa':
        if not contract_ready(state):
            return 'Contractul trebuie semnat sau exceptia aprobata de Gelu.'
        if not ('avans_confirmat' in facts or 'exceptie_avans' in state['exceptions']):
            return 'Avansul trebuie confirmat sau exceptia aprobata de Gelu.'
        if not all(state['roles'].values()):
            return 'Desemneaza responsabilul, proiectantul si persoana comerciala.'
    if key == 'executie_finalizata' and not ('proiect_avizat' in facts or
                                            'executie_fara_proiect' in state['exceptions']):
        return 'Proiect nefinalizat: responsabilul trebuie sa consemneze decizia de continuare.'
    return ''


def record(state, key, occurred_on, note='', today=None):
    """Validate once on the server, regardless of which UI invokes the write."""
    problem = blocked_reason(state, key)
    if problem:
        raise ValueError(problem)
    day = date.fromisoformat(str(occurred_on))
    if day > (today or date.today()):
        raise ValueError('Data evenimentului nu poate fi in viitor. Data programata se completeaza separat.')
    if key in RESCHEDULES:
        prerequisites = ('executie_programata' if key == 'reprogramare_executie' else 'programare_pif_primita',)
    else:
        prerequisites = BY_KEY[key][4] if key in BY_KEY else (
            'notificare_primita' if key == 'executie_fara_proiect' else 'contract_emis',)
    if any(day < date.fromisoformat(state['facts'][p]['date']) for p in prerequisites):
        raise ValueError('Data precede evenimentul necesar anterior.')
    if key in EXCEPTIONS | RESCHEDULES and not str(note).strip():
        raise ValueError('Motivul deciziei este obligatoriu.')
    result = deepcopy(state)
    target = 'exceptions' if key in EXCEPTIONS else 'facts'
    result[target][key] = {'date': day.isoformat(), 'note': str(note).strip()}
    return result


def stream_states(state):
    f = state['facts']
    stages = {
        'Dosar': [('oferta_acceptata', 'Oferta acceptata'), ('contract_emis', 'Contract emis'),
                  ('cerere_depusa', 'Cerere depusa'), ('notificare_primita', 'Notificare primita')],
        'Proiect': [('notificare_proiectant', 'La proiectant'), ('proiect_intocmit', 'Intocmit'),
                    ('proiect_avizat', 'Avizat')],
        'Executie': [('executie_programata', 'Programata'), ('ordin_executie_predat', 'Ordin predat'),
                     ('executie_finalizata', 'Executata'), ('ordin_executie_arhivat', 'Ordin arhivat')],
        'PIF': [('contract_furnizare', 'Furnizare pregatita'), ('solicitare_pif', 'Solicitata'),
                ('programare_pif_primita', 'Programare primita'), ('dosar_pif_predat', 'Dosar predat'),
                ('pif_efectuata', 'Efectuata'), ('copie_pv_pif_arhivata', 'Documente arhivate')],
    }
    return {name: next((label for key, label in reversed(items) if key in f), 'Neinceput')
            for name, items in stages.items()}


def outstanding_exceptions(state):
    resolutions = {'exceptie_contract': 'contract_semnat', 'exceptie_avans': 'avans_confirmat',
                   'executie_fara_proiect': 'proiect_avizat'}
    return [EVENT_LABELS[key] for key in state['exceptions'] if resolutions[key] not in state['facts']]
