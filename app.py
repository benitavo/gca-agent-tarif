import streamlit as st
import anthropic
import json
import base64

st.set_page_config(page_title="Document Extraction Agent", page_icon="⚡", layout="centered")

st.markdown("""
<style>
  .block-container { padding-top: 1.5rem; }
  .header { background:#1c2b3a; color:#e8dfc8; padding:20px 28px;
            border-bottom:3px solid #c9a84c; border-radius:8px; margin-bottom:24px;
            display:flex; align-items:center; gap:14px; }
  .icon { background:#c9a84c; color:#1c2b3a; font-size:18px; font-weight:bold;
          width:38px; height:38px; display:flex; align-items:center;
          justify-content:center; border-radius:4px; flex-shrink:0; }
  .field-label { font-size:11px; font-weight:700; text-transform:uppercase;
                 letter-spacing:0.6px; margin-bottom:2px; }
</style>
<div class="header">
  <div class="icon">⚡</div>
  <div>
    <div style="font-size:19px;font-weight:700;letter-spacing:1px;">Document Extraction Agent</div>
    <div style="font-size:12px;color:#9aa8b4;margin-top:2px;">Grid Connection Agreement · Tariff Award Letter · Automated Data Extraction</div>
  </div>
</div>
""", unsafe_allow_html=True)

GCA_FIELDS = [
    ("project",                     "Project"),
    ("grid_operator",               "Grid operator"),
    ("company",                     "Company"),
    ("type",                        "Type"),
    ("reference",                   "Reference"),
    ("location",                    "Location"),
    ("date_of_signature",           "Date of signature"),
    ("date_initial_gco_request",    'Date of initial GCO ("PTF") request'),
    ("injection_capacity",          "Injection capacity"),
    ("consumption_capacity",        "Consumption capacity"),
    ("grid_voltage",                "Grid voltage"),
    ("inverters",                   "Inverters"),
    ("reactive_energy_requirements","Reactive energy requirements"),
    ("plant_substation",            "Plant substation"),
    ("grid_substation",             "Grid substation"),
    ("connection_works",            "Connection works"),
    ("equipment_plant_substation",  "Equipment in plant substation"),
    ("hv_protection_category",      "HV protection category"),
    ("hz_filter",                   "175 Hz filter"),
    ("downtime",                    "Downtime"),
    ("other",                       "Other"),
    ("total_costs_excl_vat",        "Total costs (excluding VAT)"),
    ("quote_part_excl_vat",         "Quote-part (excluding VAT)"),
    ("timing",                      "Timing"),
]

TARIFF_FIELDS = [
    ("project",               "Project"),
    ("date",                  "Date"),
    ("tender",                "Tender"),
    ("project_specifications","Project specifications"),
    ("carbon_evaluation",     "Carbon evaluation of modules"),
    ("reference_price",       "Reference price (T)"),
    ("duration",              "Duration"),
    ("conditions",            "Conditions"),
]

GCA_SYSTEM_PROMPT = """You are an expert at reading French grid connection agreements (Convention de raccordement / CRAC) from Enedis.
Respond ONLY with a valid JSON object — no markdown, no backticks.

CRITICAL: ALL values must be written in ENGLISH, even if the source document is in French.
Translate French terms, descriptions, and sentences into English. Never copy French text as-is.

Fields to extract (all values in English):
- project: Short project name (e.g. "Orion 45")
- grid_operator: e.g. "Enedis"
- company: Full legal company name of the applicant
- type: In English, e.g. "Grid connection agreement"
- reference: e.g. "CRAC dated 16/09/2022"
- location: City and postal code
- date_of_signature: DD/MM/YYYY
- date_initial_gco_request: DD/MM/YYYY
- injection_capacity: e.g. "10,330 kW"
- consumption_capacity: e.g. "30 kW"
- grid_voltage: e.g. "20 kV"
- inverters: English sentence, e.g. "46 Sungrow SG250HX inverters"
- reactive_energy_requirements: English sentence describing tan phi / reactive power requirements
- plant_substation: Name of the delivery substation (poste de livraison)
- grid_substation: Name of source substation and HTA feeder in English
- connection_works: English description of cable works (length, type, voltage)
- equipment_plant_substation: English description of equipment required at the plant substation
- hv_protection_category: English, e.g. "Category H.5 (by derogation)"
- hz_filter: English sentence on whether a 175 Hz filter is required
- downtime: English sentence on interruption zone and allowed downtime
- other: Any other notable requirements, in English
- total_costs_excl_vat: e.g. "€1,195,654.91 excl. VAT"
- quote_part_excl_vat: e.g. "€152,574.10 excl. VAT"
- timing: English sentence on expected connection or commissioning date

If a field cannot be found, use exactly: "Info not found"."""

TARIFF_SYSTEM_PROMPT = """You are an expert at reading French renewable energy tariff award letters (lettres de désignation de lauréat) issued by the French Ministry of Energy following CRE tender processes.

Respond ONLY with a valid JSON object — no markdown, no backticks.

CRITICAL: ALL values must be written in ENGLISH, even if the source document is in French.
Translate all French content into clear, professional English.

Fields to extract:

- project: Short project name only (e.g. "Baconnière")

- date: Date of the letter in DD/MM/YYYY format

- tender: The call for tenders reference translated to English (e.g. "CRE4 tender – 7th period, family 1, ref. 2016/S 148-268152")

- project_specifications: One English sentence: capacity in MWp, technology, full location (lieu-dit, commune, postal code).
  Example: "12.915 MWp ground-mounted PV plant located at Lieu-dit 'La Baconnière', Roussay 49450 SEVREMOINE."

- carbon_evaluation: Carbon footprint value with unit (e.g. "550 kg eq CO2/kWc")

- reference_price: Reference electricity price T in €/MWh including any participatory investment bonus and any mention of reduction in case of delay.
  Example: "55.9 €/MWh, increased by 3 €/MWh for participatory investment commitment, for the full contract duration."

- duration: Contract duration if stated (e.g. "20 years"), otherwise "Info not found"

- conditions: Bullet-point summary in English of ALL laureate obligations, each starting with "• ":
  • Deadline to complete and connect the installation (X months from notification)
  • Deadline to submit a complete grid connection request (X months from notification)
  • Deadline to constitute the financial execution guarantee (X months from notification) and minimum guarantee duration
  • Obligation to provide EDF/grid operator with the conformity attestation
  • Participatory investment obligations if any
  • Any other conditions or obligations mentioned in the letter

If a field cannot be found, use exactly: "Info not found"."""

def run_extraction(pdf_bytes, system_prompt):
    b64 = base64.standard_b64encode(pdf_bytes).decode()
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": system_prompt},
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}},
            {"type": "text", "text": "Extract all fields from this document and return as a JSON object."}
        ]}]
    )
    raw = resp.content[0].text.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)

def render_extraction_ui(fields, session_key, filename_prefix, system_prompt):
    uploaded = st.file_uploader("Drop your PDF here", type="pdf",
                                label_visibility="collapsed", key=f"uploader_{session_key}")
    if uploaded:
        st.info(f"📄 **{uploaded.name}** · {uploaded.size // 1024} KB")

        data_key = f"data_{session_key}"
        if data_key not in st.session_state:
            st.session_state[data_key] = {}

        if st.button("⚡  Extract Data", use_container_width=True, type="primary", key=f"btn_{session_key}"):
            with st.spinner("Reading document and extracting data…"):
                try:
                    st.session_state[data_key] = run_extraction(uploaded.read(), system_prompt)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Extraction failed: {e}")

        if st.session_state.get(data_key):
            data = st.session_state[data_key]
            not_found_count = sum(1 for k, _ in fields if data.get(k) == "Info not found")

            st.markdown("---")
            st.markdown("✅ **Extracted — review and edit if needed**")
            if not_found_count:
                st.warning(f"⚠ {not_found_count} field{'s' if not_found_count > 1 else ''} not found in the document.")

            st.markdown("<br>", unsafe_allow_html=True)
            for key, label in fields:
                val = data.get(key, "")
                is_nf = val == "Info not found"
                color = "#c0392b" if is_nf else "#444"
                st.markdown(f"<div class='field-label' style='color:{color}'>{label}</div>",
                            unsafe_allow_html=True)
                h = 44
                if len(val) > 200: h = 180
                elif len(val) > 80: h = 90
                data[key] = st.text_area(label, value=val, height=h,
                                         label_visibility="collapsed",
                                         key=f"{session_key}_{key}")

            st.markdown("---")
            c1, c2 = st.columns(2)

            tsv = "\n".join(f"{lbl}\t{data.get(k,'')}" for k, lbl in fields)
            c1.download_button("📋 Download TSV (paste into Excel)",
                data=tsv.encode("utf-8"),
                file_name=f"{filename_prefix}_{data.get('project','output').replace(' ','_')}.tsv",
                mime="text/tab-separated-values", use_container_width=True,
                key=f"tsv_{session_key}")

            csv_rows = [f'"{lbl}","{data.get(k,"").replace(chr(34), chr(34)*2)}"' for k, lbl in fields]
            c2.download_button("⬇ Download CSV",
                data=("\ufeff" + "\n".join(csv_rows)).encode("utf-8"),
                file_name=f"{filename_prefix}_{data.get('project','output').replace(' ','_')}.csv",
                mime="text/csv", use_container_width=True, type="primary",
                key=f"csv_{session_key}")

            if st.button("↩ Process another PDF", key=f"reset_{session_key}"):
                del st.session_state[data_key]
                st.rerun()

tab1, tab2 = st.tabs(["📋  Grid Connection Agreement (CRAC)", "🏆  Tariff Award Letter (CRE)"])

with tab1:
    render_extraction_ui(GCA_FIELDS, "gca", "GCA", GCA_SYSTEM_PROMPT)

with tab2:
    render_extraction_ui(TARIFF_FIELDS, "tariff", "Tariff", TARIFF_SYSTEM_PROMPT)
