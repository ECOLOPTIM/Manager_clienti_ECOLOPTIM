"""Contract terms and a standard Romanian workday calendar for IUGN tracking.

Movable holidays use the Orthodox calendar. Additional company/cult-specific
closures require manual review; no external-party delay extends a contract here.
"""
from datetime import date, datetime, timedelta

STAGE_DEFAULTS = {'durata_proiectare_zile': 10, 'durata_verificare_zile': 5,
                  'durata_executie_zile': 2, 'durata_receptie_zile': 1}
STAGE_LABELS = {'durata_proiectare_zile': 'Proiectare - zile lucratoare',
                'durata_verificare_zile': 'Verificare proiect - zile lucratoare',
                'durata_executie_zile': 'Executie - zile lucratoare',
                'durata_receptie_zile': 'Receptie tehnica - zile lucratoare'}


def as_date(value):
    if isinstance(value, datetime):return value.date()
    if isinstance(value, date):return value
    for fmt in ('%Y-%m-%d','%d.%m.%Y'):
        try:return datetime.strptime(str(value),fmt).date()
        except ValueError:pass
    raise ValueError('Data calendaristica invalida.')


def orthodox_easter(year):
    a,b,c=year%4,year%7,year%19
    d=(19*c+15)%30
    e=(2*a+4*b-d+34)%7
    return date(year,(d+e+114)//31,(d+e+114)%31+1)+timedelta(days=year//100-year//400-2)


def holidays(year):
    fixed={(1,1),(1,2),(1,6),(1,7),(1,24),(5,1),(6,1),(8,15),(11,30),(12,1),(12,25),(12,26)}
    easter=orthodox_easter(year)
    return {date(year,m,d) for m,d in fixed}|{easter+timedelta(days=n) for n in (-2,0,1,49,50)}


def workday(day):
    return day.weekday()<5 and day not in holidays(day.year)


def after_workdays(start,count):
    """Exclude the triggering day; a deadline of one workday means next workday."""
    day=as_date(start)
    for _ in range(count):
        day+=timedelta(days=1)
        while not workday(day):day+=timedelta(days=1)
    return day


def execution_finish(start,count):
    """The scheduled working day is day one of actual site execution."""
    day=as_date(start)
    while not workday(day):day+=timedelta(days=1)
    return after_workdays(day,count-1)


def whole_days(value,label):
    try:
        from decimal import Decimal
        n=Decimal(str(value))
        if not n.is_finite() or n!=n.to_integral_value() or not 1<=n<=3660:raise ValueError
        return int(n)
    except (ValueError,ArithmeticError):
        raise ValueError(label+': introdu un numar intreg intre 1 si 3660.') from None


def terms(values):
    return {k:whole_days(values.get(k,v),STAGE_LABELS[k]) for k,v in STAGE_DEFAULTS.items()}


def budget(values,start):
    """Check a sequential baseline, excluding external wait and scheduling gaps."""
    stages=terms(values)
    total=whole_days(values.get('durata_contract_zile',90),'Durata totala')
    begin=as_date(start)
    project=after_workdays(begin,stages['durata_proiectare_zile'])
    verified=after_workdays(project,stages['durata_verificare_zile'])
    executed=execution_finish(after_workdays(verified,1),stages['durata_executie_zile'])
    received=after_workdays(executed,stages['durata_receptie_zile'])
    expiry=begin+timedelta(days=total)
    if received>expiry:
        raise ValueError('Duratele etapelor nu se incadreaza in durata totala a contractului. Ajusteaza termenele convenite.')
    return {'expiry':expiry,'reception':received,'remaining_days':(expiry-received).days}


def report(context,state,today=None):
    """Actual recorded triggers only; a draft/issue date is never a signature."""
    today=today or date.today()
    f=state['facts'];s=terms(context);rows=[]
    signed=f.get('contract_semnat',{}).get('date')
    if not signed:return rows
    expiry=as_date(signed)+timedelta(days=whole_days(context['durata_contract_zile'],'Durata totala'))
    def add(label,due,finished=None):
        completion=as_date(f[finished]['date']) if finished and finished in f else None
        late=(completion or today)>due
        rows.append({'Etapa':label,'Termen':due.isoformat(),
                     'Stare':('Finalizat cu depasire' if late else 'Finalizat') if completion else ('Depasit' if late else 'In termen'),
                     'Depaseste durata contractului':due>expiry})
    add('Durata totala a contractului',expiry,'pif_efectuata')
    if all(k in f for k in ('documente_complete','notificare_primita')):
        start=max(as_date(signed),*(as_date(f[k]['date']) for k in ('documente_complete','notificare_primita')))
        add('Proiect intocmit',after_workdays(start,s['durata_proiectare_zile']),'proiect_intocmit')
    if 'proiect_intocmit' in f:
        add('Proiect verificat',after_workdays(f['proiect_intocmit']['date'],s['durata_verificare_zile']),'proiect_avizat')
    if f.get('executie_programata',{}).get('scheduled_for'):
        add('Executie finalizata',execution_finish(f['executie_programata']['scheduled_for'],s['durata_executie_zile']),'executie_finalizata')
    if f.get('programare_pif_primita',{}).get('scheduled_for'):
        add('Programare PIF',as_date(f['programare_pif_primita']['scheduled_for']),'pif_efectuata')
    return rows
