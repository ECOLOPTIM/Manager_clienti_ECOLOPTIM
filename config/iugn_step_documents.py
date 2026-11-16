"""Document kinds shown beside each IUGN milestone, without changing prerequisites."""
KINDS = {
 'oferta_acceptata': {'deviz_acceptat':'Deviz-oferta acceptat'},
 'documente_complete': {'identitate':'Act de identitate', 'proprietate':'Act de proprietate',
    'adeverinta_asociatie':'Adeverinta asociatie', 'tabel_coproprietari':'Tabel coproprietari', 'alt_document':'Alt document al clientului'},
 'contract_semnat': {'contract_semnat':'Contract semnat', 'mandat_semnat':'Mandat semnat'},
 'avans_confirmat': {'dovada_avans':'Dovada incasarii avansului'},
 'cerere_depusa': {'cerere_inregistrata':'Cerere si dovada depunerii'},
 'nota_analiza_transmisa': {'nota_analiza':'Nota de plata analiza', 'dovada_transmitere':'Dovada transmiterii'},
 'notificare_primita': {'notificare':'Notificare de racordare'},
 'notificare_proiectant': {'dovada_transmitere':'Dovada transmiterii catre proiectant'},
 'proiect_intocmit': {'proiect':'Proiect tehnic'},
 'proiect_avizat': {'proiect_avizat':'Proiect avizat', 'izometrie':'Izometrie'},
 'executie_programata': {'confirmare_programare':'Confirmare programare executie'},
 'ordin_executie_predat': {'ordin_executie':'Ordin de lucru executie'},
 'executie_finalizata': {'pv_receptie':'PV receptie tehnica', 'pv_ascunse':'PV lucrari ascunse', 'document_executie':'Alt document de executie'},
 'ordin_executie_arhivat': {'ordin_completat':'Ordin executie completat'},
 'contract_furnizare': {'contract_furnizare':'Contract de furnizare'},
 'solicitare_pif': {'solicitare_inregistrata':'Solicitare si dovada depunerii PIF', 'dosar_pif':'Dosar PIF depus'},
 'nota_pif_transmisa': {'nota_pif':'Nota de plata PIF', 'dovada_transmitere':'Dovada transmiterii'},
 'programare_pif_primita': {'programare_pif':'Programare PIF'},
 'echipa_pif_alocata': {'ordin_pif':'Ordin de lucru PIF'},
 'dosar_pif_predat': {'ordin_pif':'Ordin de lucru PIF', 'dosar_pif':'Dosar PIF pentru echipa'},
 'pif_efectuata': {'pv_pif':'PV punere in functiune'},
 'copie_pv_pif_arhivata': {'pv_pif':'Copia PV PIF', 'ordin_completat':'Ordin PIF completat'},
}
# These documents attest the milestone itself. Other milestones also involve an
# action (transmission, payment, completion or handover), so confirmation is opt-in.
DOCUMENT_FACTS = {'oferta_acceptata', 'contract_semnat', 'notificare_primita',
                  'proiect_intocmit', 'proiect_avizat', 'contract_furnizare',
                  'ordin_executie_arhivat', 'copie_pv_pif_arhivata'}
REQUIRED_KINDS = {
 'contract_semnat': {'contract_semnat'},
 'proiect_avizat': {'proiect_avizat', 'izometrie'},
 'copie_pv_pif_arhivata': {'pv_pif', 'ordin_completat'},
}
