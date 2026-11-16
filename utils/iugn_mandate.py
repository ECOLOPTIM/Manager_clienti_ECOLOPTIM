"""Mandate generation from the immutable service-contract context."""
from datetime import date
from io import BytesIO
from pathlib import Path
from docxtpl import DocxTemplate
from jinja2 import Environment, StrictUndefined

TEMPLATE=Path(__file__).resolve().parents[1]/'templates'/'contract_mandat_iugn.docx'


def address(ctx,prefix):
    labels=(('judet','jud.'),('localitate','loc.'),('strada','str.'),('numar','nr.'),
            ('bloc','bl.'),('scara','sc.'),('etaj','et.'),('apartament','ap.'),('cod_postal','cod postal'))
    return ', '.join(label+' '+str(ctx[prefix+part]) for part,label in labels if ctx.get(prefix+part))


def context(source,number,issued_date=None):
    if source.get('beneficiar_tip')=='PJ':
        principal=(f"{source['beneficiar_firma']}, CUI {source['beneficiar_cui']}, nr. Registrul Comertului "
                   f"{source['beneficiar_regcom']}, cu sediul in {address(source,'beneficiar_')}, "
                   f"reprezentata de {source['beneficiar_nume']}, in calitate de {source['beneficiar_reprezentant_calitate']}")
    else:
        principal=(f"{source['beneficiar_nume']}, cu domiciliul in {address(source,'beneficiar_')}, "
                   f"CI seria {source['beneficiar_ci_serie']}, nr. {source['beneficiar_ci_nr']}, "
                   f"eliberata de {source['beneficiar_ci_emitent']} la data de {source['beneficiar_ci_data']}")
    agent=(f"{source['executant_denumire']}, CUI {source['executant_cui']}, nr. Registrul Comertului "
           f"{source['executant_regcom']}, cu sediul in {address(source,'executant_')}, "
           f"reprezentata de {source['executant_reprezentant']}, in calitate de {source['executant_reprezentant_calitate']}")
    return {'nr_mandat':number,'data_mandat':(issued_date or date.today()).strftime('%d.%m.%Y'),
            'mandant_identificare':principal,'mandatar_identificare':agent,
            'adresa_lucrare':address(source,'adresa_'),'nr_contract':source['nr_contract'],
            'data_contract':source['data_contract'],'executant_telefon':source['executant_telefon'],
            'executant_email':source['executant_email'],'beneficiar_nume':source['beneficiar_nume'],
            'executant_denumire':source['executant_denumire']}


def generate(values):
    if not TEMPLATE.is_file():raise ValueError('Instaleaza sablonul de mandat ca templates/contract_mandat_iugn.docx.')
    doc=DocxTemplate(TEMPLATE)
    missing=doc.get_undeclared_template_variables()-values.keys()
    if missing:raise ValueError('Sablonul mandatului contine campuri necunoscute: '+', '.join(sorted(missing)))
    doc.render(values,jinja_env=Environment(undefined=StrictUndefined),autoescape=True)
    out=BytesIO();doc.save(out);return out.getvalue()
