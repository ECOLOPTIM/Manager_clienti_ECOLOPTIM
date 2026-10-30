"""Offline IUGN contract preparation. No numbering, database writes or status changes.

The UI must supply verified company/GDPR settings and explicit contract terms.
Existing advance payments are deliberately not treated as the agreed advance.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
import re
from zipfile import ZipFile

from docxtpl import DocxTemplate
from jinja2 import Environment, StrictUndefined

TEMPLATE = Path(__file__).resolve().parents[1] / 'templates' / 'contract_iugn.docx'
ADDRESS_PARTS = ('judet', 'localitate', 'strada', 'numar', 'bloc', 'scara', 'etaj', 'apartament', 'cod_postal')
CLIENT_FIELDS = {
    'beneficiar_nume': 'nume', 'beneficiar_firma': 'firma',
    'beneficiar_cnp': 'cnp', 'beneficiar_ci_serie': 'ci_serie',
    'beneficiar_ci_nr': 'ci_numar', 'beneficiar_ci_emitent': 'ci_emitent',
    'beneficiar_ci_data': 'ci_data', 'client_telefon': 'telefon', 'client_email': 'email',
    **{f'beneficiar_{part}': f'domiciliu_{part}' for part in ADDRESS_PARTS},
}
WORK_FIELDS = {**{f'adresa_{part}': f'adresa_{part}' for part in ADDRESS_PARTS},
               'descriere_lucrare': 'descriere', 'data_contract': 'data_contract'}
MONEY_INPUTS = ('valoare_proiectare', 'valoare_verificare', 'valoare_avize',
                'valoare_executie_receptie', 'valoare_asistenta_pif')


class ContractDataError(ValueError):
    """A reviewable generation error containing field names, never client data."""


def _number(value, field):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result >= Decimal('1000000000000'):
            raise ValueError
        return result
    except (InvalidOperation, ValueError, TypeError):
        raise ContractDataError(f'Valoare numerica invalida: {field}') from None


def _money(value):
    return value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def _fmt(value):
    return format(_money(value), ',.2f').replace(',', '_').replace('.', ',').replace('_', '.')


def _date(value, field):
    if isinstance(value, (date, datetime)):
        return value.strftime('%d.%m.%Y')
    for pattern in ('%Y-%m-%d', '%d.%m.%Y'):
        try:
            return datetime.strptime(str(value), pattern).strftime('%d.%m.%Y')
        except ValueError:
            pass
    raise ContractDataError(f'Data invalida: {field}')


def prepare_context(client, work, company, terms):
    """Map records, validate PF/PJ and amounts; return a complete flat DOCX context.

    company: explicit executant_*, autorizatie_* and gdpr_* template settings.
    terms: remaining contract fields, PF/PJ choice and missing address/identity data.
    terms may override client/work fields only after explicit review in the caller.
    Monetary inputs are unformatted numbers; all service prices include VAT.
    """
    if not client.get('id') or str(work.get('client_id')) != str(client['id']):
        raise ContractDataError('Lucrarea nu apartine clientului selectat.')
    names = DocxTemplate(TEMPLATE).get_undeclared_template_variables()
    ctx = {name: '' for name in names}
    ctx.update({name: client.get(source) or '' for name, source in CLIENT_FIELDS.items()})
    ctx.update({name: work.get(source) or '' for name, source in WORK_FIELDS.items()})
    for settings in (company, terms):
        unknown = set(settings) - names
        if unknown:
            raise ContractDataError('Campuri necunoscute: ' + ', '.join(sorted(unknown)))
    if any(not k.startswith(('executant_', 'autorizatie_', 'gdpr_')) for k in company):
        raise ContractDataError('Configuratia firmei contine campuri straine.')
    if any(k.startswith(('executant_', 'autorizatie_', 'gdpr_')) for k in terms):
        raise ContractDataError('Datele firmei si GDPR se furnizeaza prin configuratia firmei.')
    ctx.update(company)
    ctx.update(terms)
    if ctx['beneficiar_tip'] not in ('PF', 'PJ'):
        raise ContractDataError('Selecteaza explicit beneficiar_tip: PF sau PJ.')
    if not isinstance(ctx['corespondenta_diferita'], bool):
        raise ContractDataError('corespondenta_diferita trebuie sa fie boolean.')

    optional = {'beneficiar_banca', 'beneficiar_iban', 'client_email', 'client_telefon',
                'executant_telefon', 'gdpr_contact_dpo'}
    for prefix in ('beneficiar_', 'executant_', 'adresa_', 'corespondenta_'):
        optional.update(prefix + part for part in ADDRESS_PARTS[4:])
    if not ctx['corespondenta_diferita']:
        optional.update('corespondenta_' + part for part in ADDRESS_PARTS)
    if ctx['beneficiar_tip'] == 'PF':
        optional.update(('beneficiar_firma', 'beneficiar_cui', 'beneficiar_regcom',
                         'beneficiar_reprezentant_calitate'))
    else:
        optional.update(('beneficiar_cnp', 'beneficiar_ci_serie', 'beneficiar_ci_nr',
                         'beneficiar_ci_emitent', 'beneficiar_ci_data'))
    derived = {'valoare_totala', 'valoare_proiect_verificare', 'valoare_executie',
               'avans_suma', 'executie_procent', 'executie_suma', 'pif_suma'}
    if derived.intersection(terms):
        raise ContractDataError('Subtotalurile si transele sunt calculate, nu se introduc manual.')
    missing = [name for name in names - optional - derived
               if ctx[name] is None or str(ctx[name]).strip() == '']
    if missing:
        raise ContractDataError('Completeaza campurile: ' + ', '.join(sorted(missing)))
    for name in names:
        if name.endswith(('_data', '_expirare')) or name.startswith('data_'):
            if ctx[name] and name not in derived:
                ctx[name] = _date(ctx[name], name)
    duration = _number(ctx['durata_contract_zile'], 'durata_contract_zile')
    if duration <= 0 or duration != duration.to_integral_value():
        raise ContractDataError('Durata trebuie sa fie un numar intreg pozitiv de zile.')
    ctx['durata_contract_zile']=str(int(duration))
    prices = {name: _money(_number(ctx[name], name)) for name in MONEY_INPUTS}
    total = sum(prices.values())
    agreed_total = _money(_number(work.get('valoare_contractata'), 'valoare_contractata'))
    if total <= 0 or total != agreed_total:
        raise ContractDataError('Defalcarea pretului nu corespunde valorii contractate a lucrarii.')
    advance = _number(ctx['avans_procent'], 'avans_procent')
    if advance > 90:
        raise ContractDataError('Avansul nu poate depasi 90%; transa finala este 10%.')
    final_amount = _money(total * Decimal('.10'))
    advance_amount = _money(total * advance / 100)
    ctx.update({name: _fmt(value) for name, value in prices.items()})
    ctx.update(valoare_totala=_fmt(total),
               valoare_proiect_verificare=_fmt(sum(prices[n] for n in MONEY_INPUTS[:3])),
               valoare_executie=_fmt(sum(prices[n] for n in MONEY_INPUTS[3:])),
               avans_procent=str(advance), executie_procent=str(90 - advance),
               avans_suma=_fmt(advance_amount), pif_suma=_fmt(final_amount),
               executie_suma=_fmt(total - advance_amount - final_amount))
    return ctx


def generate_contract(client, work, company, terms):
    """Return validated DOCX bytes; caller remains responsible for issuing/saving it."""
    ctx = prepare_context(client, work, company, terms)
    doc = DocxTemplate(TEMPLATE)
    doc.render(ctx, jinja_env=Environment(undefined=StrictUndefined), autoescape=True)
    output = BytesIO()
    doc.save(output)
    with ZipFile(BytesIO(output.getvalue())) as archive:
        if any(re.search(rb'\{[{%]', archive.read(n)) for n in archive.namelist()
               if n.startswith('word/') and n.endswith('.xml')):
            raise ContractDataError('Documentul contine marcaje de sablon necompletate.')
    return output.getvalue()
