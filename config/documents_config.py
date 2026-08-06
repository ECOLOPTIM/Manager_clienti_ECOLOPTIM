import os

TEMPLATE_ORDIN = os.path.join("templates", "ordin_serviciu.docx")
TEMPLATE_CONTRACT_BRANS_GAZE = os.path.join("templates", "contract_executie_brans_gaze.docx")
TEMPLATE_CONTRACT_MANDAT = os.path.join("templates", "contract_mandat.docx")
TEMPLATE_ADRESA1_DIST = os.path.join("templates", "adresa1_inaintare_Distrigaz.docx")
TEMPLATE_SITUATIE_PLATA_BRANSAMENT = os.path.join("templates", "situatie_plata_bransament.xlsx")

TEMPLATE_MAP = {
    "🧾 OS (Ordin serviciu)": TEMPLATE_ORDIN,
    "📄 Contract execuție branș. gaze": TEMPLATE_CONTRACT_BRANS_GAZE,
    "📝 Contract mandat": TEMPLATE_CONTRACT_MANDAT,
    "Adresa inaintare Distrigaz (1)": TEMPLATE_ADRESA1_DIST,
    "📊 Situație plată branșament": TEMPLATE_SITUATIE_PLATA_BRANSAMENT,
}