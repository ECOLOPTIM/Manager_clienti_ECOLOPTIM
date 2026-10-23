"""Work-specific milestone UI. The database remains the authorization boundary."""
from datetime import date
import json
import pandas as pd
import streamlit as st
from db import db, iugn, iugn_rules as rules


def render_work_details(row, client_id, edit_key, snapshot_key, conflict_key):
    """Keep generic work editing from rewriting workflow-owned facts."""
    lid = int(row['id'])
    st.info('Rolurile, etapele si programarile se modifica din Flux birou. '
            'Aici poti actualiza adresa, descrierea si observatiile.')
    with st.form(f'iugn_details_{client_id}_{lid}'):
        values = dict(row)
        for field, label in [('adresa_judet', 'Judet'), ('adresa_localitate', 'Localitate'),
                             ('adresa_strada', 'Strada'), ('adresa_numar', 'Numar'),
                             ('adresa_bloc', 'Bloc'), ('adresa_apartament', 'Apartament')]:
            values[field] = st.text_input(label, value=str(row.get(field) or ''))
        values['descriere'] = st.text_area('Descriere lucrare', value=str(row.get('descriere') or ''))
        values['observatii'] = st.text_area('Observatii', value=str(row.get('observatii') or ''))
        save = st.form_submit_button('Salveaza detaliile lucrarii')
        cancel = st.form_submit_button('Inchide editarea')
    if cancel:
        for key in (edit_key, snapshot_key, conflict_key):
            st.session_state.pop(key, None)
        st.rerun()
    if save:
        if not all(values.get(k, '').strip() for k in ('adresa_judet', 'adresa_localitate', 'adresa_strada', 'adresa_numar')):
            st.error('Completeaza judetul, localitatea, strada si numarul.')
            return
        try:
            db.modifica_lucrare(lid, values, expected_revision=int(row['revision']))
        except db.ConcurrentWorkEditError as exc:
            st.session_state[conflict_key] = str(exc)
            st.rerun()
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))
        else:
            for key in (edit_key, snapshot_key, conflict_key):
                st.session_state.pop(key, None)
            st.rerun()


def render(lucrare_id, client_id):
    from config.workflow_catalog import FAMILIES, template_for
    prefix = f'iugn_{client_id}_{lucrare_id}'
    cache = prefix + '_snapshot'
    st.subheader('Flux instalatie de utilizare noua')
    st.caption('Grup: ' + FAMILIES[template_for(rules.WORK_TYPE)['family']])
    st.caption('Dosarul, proiectul, executia si PIF sunt urmarite separat. '
               'Fiecare confirmare ramane in istoricul lucrarii.')
    live = iugn.get(lucrare_id)
    if live is None:
        st.info('Lucrare existenta: activeaza fluxul nou. Sarcinile vechi sunt pastrate in istoric; '
                'etapele realizate se confirma din documentele lucrarii.')
        if st.button('Activeaza fluxul IUGN', key=prefix+'_activate'):
            try:
                iugn.activate(lucrare_id)
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))
            else:
                st.rerun()
        return
    if cache not in st.session_state:
        st.session_state[cache] = live
    snapshot = st.session_state[cache]
    state, revision = snapshot['state'], snapshot['revision']
    if live['revision'] != revision:
        st.warning('Fluxul s-a modificat in alta sesiune. Reincarca pentru a lucra cu datele actuale.')
    if st.button('Reincarca fluxul', key=prefix+'_reload'):
        st.session_state.pop(cache, None)
        st.rerun()
    for col, (stream, label) in zip(st.columns(4), rules.stream_states(state).items()):
        col.metric(stream, label)
    st.markdown('**Persoane desemnate**')
    for role, label in rules.ROLES.items():
        st.write(f"{label}: {state['roles'][role] or 'Nedesemnat'}")
    for label in rules.outstanding_exceptions(state):
        st.warning(label + ' — restanta ramane deschisa.')
    if iugn.is_manager() and rules.contract_ready(state):
        users = iugn.assignable_users()
        with st.expander('Desemnare / schimbare persoane'):
            with st.form(prefix+f'_roles_{revision}'):
                selected = {}
                for role, label in rules.ROLES.items():
                    options = [''] + users
                    current = state['roles'][role]
                    selected[role] = st.selectbox(label, options,
                        index=options.index(current) if current in options else 0,
                        key=prefix+f'_role_{role}_{revision}')
                save_roles = st.form_submit_button('Salveaza persoanele desemnate')
            if save_roles:
                try:
                    iugn.assign_roles(lucrare_id, selected, expected_revision=revision)
                except (ValueError, PermissionError) as exc:
                    st.error(str(exc))
                else:
                    st.session_state.pop(cache, None)
                    st.rerun()
    rows = []
    for key, label, stream, role, _ in rules.STEPS:
        done = key in state['facts']
        problem = rules.blocked_reason(state, key)
        rows.append({'Etapa': stream.capitalize(), 'Sarcina': label,
                     'Stare': 'Finalizat' if done else 'In asteptare' if problem else 'Disponibil',
                     'Persoana': 'Gelu' if role == 'manager' else state['roles'].get(role, ''),
                     'Data': state['facts'].get(key, {}).get('date', ''),
                     'Conditie': '' if done else problem})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
    available = [key for key in rules.EVENT_LABELS
                 if not rules.blocked_reason(state, key) and iugn.can_record(state, key)]
    if available:
        st.markdown('**Inregistreaza un eveniment**')
        key = st.selectbox('Eveniment', available, format_func=rules.EVENT_LABELS.get,
                           key=prefix+f'_event_{revision}')
        with st.form(prefix+f'_record_{revision}_{key}'):
            occurred = st.date_input('Data evenimentului', value=date.today(), max_value=date.today())
            scheduled = ''
            team = ''
            if key in {'executie_programata', 'programare_pif_primita'} | rules.RESCHEDULES.keys():
                scheduled = st.date_input('Data programata', value=date.today())
            if key in {'executie_programata', 'echipa_pif_alocata', 'reprogramare_executie'}:
                team = st.text_input('Echipa alocata')
            if key == 'reprogramare_pif':
                st.info('Beneficiarul achita din nou taxa PIF, conform noii note Distrigaz. '
                        'Nota, echipa si dosarul pentru noua programare vor fi urmarite din nou.')
            note = st.text_area('Motiv / observatii' if key in rules.EXCEPTIONS | rules.RESCHEDULES else 'Observatii / referinta documentului')
            save = st.form_submit_button('Inregistreaza evenimentul')
        if save:
            try:
                iugn.record_event(lucrare_id, key, str(occurred), expected_revision=revision,
                                  note=note, scheduled_for=str(scheduled), team=team)
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))
            else:
                st.session_state.pop(cache, None)
                st.rerun()
    else:
        st.info('Nu exista evenimente disponibile pentru contul tau in etapa curenta. '
                'Verifica persoanele desemnate si conditiile din tabel.')
    with st.expander('Istoricul lucrarii'):
        events = iugn.history(lucrare_id)
        if not events.empty:
            events['event_key'] = events['event_key'].map(lambda k: rules.EVENT_LABELS.get(k, k))
            events['detail'] = events['detail'].map(lambda d: json.dumps(json.loads(d), ensure_ascii=False))
            st.dataframe(events.rename(columns={'event_key': 'Eveniment', 'occurred_on': 'Data eveniment',
                'recorded_at': 'Inregistrat la', 'actor': 'Utilizator', 'detail': 'Detalii',
                'revision': 'Versiune'}), hide_index=True, width='stretch')
    with st.expander('Sarcinile anterioare activarii'):
        tasks = db.lista_sarcini_lucrare(lucrare_id)
        old = tasks[tasks['cod_flux'].isna()]
        if old.empty:
            st.caption('Nu exista sarcini anterioare.')
        else:
            st.dataframe(old[['tip_sarcina', 'status', 'responsabil', 'observatii']], hide_index=True)
    st.caption('Prima etapa confirma evenimentele declarate de operator. Generarea si verificarea '
               'documentelor, termenele automate, transele si inchiderea dosarului urmeaza separat.')
