"""Application-session authorization; offline maintenance runs without an actor.

The browser session binds only its authenticated username and password version.
Roles and account flags are always re-read from the configured database.
"""
from contextvars import ContextVar
from functools import wraps
import hashlib
import hmac

ROLES = {'admin', 'birou', 'vizualizare'}
_actor = ContextVar('ecoloptim_authenticated_actor', default=None)


def password_marker(profile):
    return hashlib.sha256(str(profile['parola']).encode('utf-8')).hexdigest()


def bind_actor(username, marker):
    _actor.set((str(username), str(marker)))


def clear_actor():
    _actor.set(None)


def require(permission, target_username=None):
    actor = _actor.get()
    if actor is None:
        # Trusted local setup, tests and maintenance scripts are not browser sessions.
        return
    from db import db
    username, marker = actor
    profile = db.get_utilizator(username)
    if (not profile or not profile.get('activ') or profile.get('rol') not in ROLES
            or not hmac.compare_digest(marker, password_marker(profile))):
        raise PermissionError('Sesiunea nu mai este valida. Autentifica-te din nou.')
    if permission == 'own_password':
        if str(target_username) != username:
            raise PermissionError('Poti schimba numai parola contului tau.')
        return
    if profile.get('must_change_password'):
        raise PermissionError('Schimba parola contului inainte de a continua.')
    if permission == 'admin' and profile['rol'] != 'admin':
        raise PermissionError('Operatia este disponibila numai administratorului.')
    if permission == 'write' and profile['rol'] not in {'admin', 'birou'}:
        raise PermissionError('Contul are acces numai pentru consultare.')


def guard(permission):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            target = (args[0] if args else kwargs.get('username')) if permission == 'own_password' else None
            require(permission, target)
            return function(*args, **kwargs)
        return wrapped
    return decorate


BUSINESS_WRITES = (
    '_next_document_number', 'adauga_inregistrare', 'adauga_client', 'modifica_client',
    'sterge_client', 'save_atasament', 'sterge_atasament', 'adauga_lucrare',
    'modifica_lucrare', 'sterge_lucrare', 'update_sarcina', 'adauga_factura',
    'anuleaza_factura', 'sterge_factura', 'recalculeaza_status_factura',
    'adauga_plata', 'sterge_plata',
)
ADMIN_OPERATIONS = (
    'lista_utilizatori', 'adauga_utilizator', 'reseteaza_parola_admin',
    'seteaza_rol_utilizator', 'seteaza_activ_utilizator', 'sterge_utilizator',
    'seteaza_must_change_password', 'schimba_parola_fara_verificare_admin',
)


def protect_functions(namespace):
    for name in BUSINESS_WRITES:
        namespace[name] = guard('write')(namespace[name])
    for name in ADMIN_OPERATIONS:
        namespace[name] = guard('admin')(namespace[name])
    namespace['schimba_parola'] = guard('own_password')(namespace['schimba_parola'])
