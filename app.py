import streamlit as st
import pandas as pd
from datetime import date
import os
import uuid

# --- NASTAVENIA STRÁNKY ---
st.set_page_config(page_title="Minúty 2026", layout="centered")

# --- SÚBORY ---
NAMES_FILE = "Zoznam_mien.txt"
DATA_FILE = "data.csv"

# Inicializácia súborov
if not os.path.exists(NAMES_FILE):
    with open(NAMES_FILE, "w", encoding="utf-8") as f:
        f.write("Jozef\nMichal\n")

if not os.path.exists(DATA_FILE):
    df_init = pd.DataFrame(columns=["ID", "Date", "Meno", "Hodnota", "Tankovanie"])
    df_init.to_csv(DATA_FILE, index=False)

# --- POMOCNÉ FUNKCIE ---
def load_names():
    if not os.path.exists(NAMES_FILE): return ["Jozef", "Michal"]
    with open(NAMES_FILE, "r", encoding="utf-8") as f:
        return sorted([line.strip() for line in f.readlines() if line.strip()])

def save_name(new_name):
    with open(NAMES_FILE, "a", encoding="utf-8") as f:
        f.write(f"{new_name}\n")

def load_data():
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame(columns=["ID", "Date", "Meno", "Hodnota", "Tankovanie"])
    df = pd.read_csv(DATA_FILE)
    df['Date'] = pd.to_datetime(df['Date']).dt.date
    df['Hodnota'] = df['Hodnota'].astype(str).str.zfill(3)
    return df

def save_data(df):
    df['Hodnota'] = df['Hodnota'].astype(str).str.zfill(3)
    df.to_csv(DATA_FILE, index=False)

# --- VÝPOČET MINÚT A TRIEDENIE ---
def process_dataframe(df):
    if df.empty:
        return df
    
    def prep_sort(group):
        vals = group['Hodnota'].astype(int)
        has_high = (vals >= 900).any()
        has_low = (vals <= 100).any()
        if has_high and has_low:
            group['SortValue'] = group['Hodnota'].apply(lambda x: int(x) + 1000 if int(x) < 500 else int(x))
        else:
            group['SortValue'] = vals
        return group

    processed_days = []
    unique_dates = sorted(df['Date'].unique())
    for d in unique_dates:
        day_df = df[df['Date'] == d].copy()
        day_df = prep_sort(day_df)
        processed_days.append(day_df)
    
    full_df = pd.concat(processed_days)
    full_df = full_df.sort_values(['Date', 'SortValue'])
    
    vals = full_df['Hodnota'].astype(int).tolist()
    minutes = []
    prev_val = None
    for v in vals:
        if prev_val is None:
            minutes.append(0)
        else:
            diff = v - prev_val
            if diff < -500: diff += 1000
            minutes.append(diff)
        prev_val = v
        
    full_df['Minúty'] = minutes
    return full_df.sort_values(['Date', 'SortValue'], ascending=[False, False])

# --- CALLBACK PRE ULOŽENIE ---
def save_record_callback():
    hodnota_in = st.session_state.get('input_hodnota', '')
    pridat_nove = st.session_state.get('pridat_nove_checkbox', False)
    vybrane_meno = st.session_state.get('vybrane_meno_selectbox', '')
    nove_meno = st.session_state.get('input_nove_meno', '')
    zaznam_datum = st.session_state.get('zaznam_datum', date.today())
    
    meno_na_zapis = nove_meno if pridat_nove else vybrane_meno
    
    if not hodnota_in.isdigit():
        st.session_state.action_msg = ("error", "Zadaj číselnú hodnotu!")
        return
    
    names = load_names()
    if pridat_nove and meno_na_zapis not in names:
        save_name(meno_na_zapis)
        
    tank = []
    if st.session_state.get('input_t20', False): tank.append("20 L")
    if st.session_state.get('input_t40', False): tank.append("40 L")
    
    new_row = {
        "ID": str(uuid.uuid4()),
        "Date": zaznam_datum,
        "Meno": meno_na_zapis,
        "Hodnota": hodnota_in.zfill(3),
        "Tankovanie": " + ".join(tank) if tank else "-"
    }
    
    current_df = load_data()
    updated_df = pd.concat([current_df, pd.DataFrame([new_row])], ignore_index=True)
    save_data(updated_df)
    
    # RESET
    st.session_state.input_hodnota = ""
    st.session_state.pridat_nove_checkbox = False
    st.session_state.input_t20 = False
    st.session_state.input_t40 = False
    if 'input_nove_meno' in st.session_state:
        st.session_state.input_nove_meno = ""
    st.session_state.action_msg = ("success", "Záznam uložený!")

# --- HLAVNÁ APP ---
st.title("Minúty 2026 🏄")

raw_df = load_data()
full_df_with_minutes = process_dataframe(raw_df)

# --- BOČNÝ PANEL (EXPORT & IMPORT) ---
st.sidebar.header("Správa dát")

# EXPORT
if not full_df_with_minutes.empty:
    export_df = full_df_with_minutes.copy().sort_values(['Date', 'SortValue'])
    export_df = export_df[['Date', 'Meno', 'Hodnota', 'Minúty', 'Tankovanie']]
    csv_data = export_df.to_csv(index=False).encode('utf-8-sig')
    st.sidebar.download_button("📥 Stiahnuť report (CSV)", data=csv_data, file_name=f"report_{date.today()}.csv", mime="text/csv")

st.sidebar.divider()

# IMPORT
uploaded_file = st.sidebar.file_uploader("Nahrať záložné CSV", type="csv")
if uploaded_file is not None:
    if st.sidebar.button("⚠️ Obnoviť dáta zo súboru"):
        try:
            imported_df = pd.read_csv(uploaded_file)
            if "ID" not in imported_df.columns:
                imported_df["ID"] = [str(uuid.uuid4()) for _ in range(len(imported_df))]
            if "Tankovanie" not in imported_df.columns:
                imported_df["Tankovanie"] = "-"
            
            save_data(imported_df[["ID", "Date", "Meno", "Hodnota", "Tankovanie"]])
            st.sidebar.success("Hotovo!")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Chyba: {e}")

# --- SEKCIA 1: PRIDAŤ ---
st.header("+ Pridať lyžiara")
col1, col2 = st.columns(2)
with col1:
    st.date_input("Dátum:", date.today(), key="zaznam_datum")
pridat_nove = st.checkbox("+ Pridaj meno", key="pridat_nove_checkbox")

with col2:
    st.selectbox("Meno:", options=load_names(), disabled=pridat_nove, key="vybrane_meno_selectbox")

if pridat_nove:
    st.text_input("Zadaj nové meno:", key="input_nove_meno")

st.text_input("Hodnota", max_chars=3, key="input_hodnota")
col_t1, col_t2 = st.columns(2)
col_t1.checkbox("20 L", key="input_t20")
col_t2.checkbox("40 L", key="input_t40")

st.button("Uložiť záznam", type="primary", on_click=save_record_callback)

if 'action_msg' in st.session_state:
    m_type, m_text = st.session_state.action_msg
    if m_type == "error": st.error(m_text)
    else: st.success(m_text)
    del st.session_state.action_msg

st.divider()

# --- SEKCIA 2: HISTÓRIA ---
st.header("História")
hist_datum = st.date_input("Dátum histórie", date.today(), key="historia_datum")

if not full_df_with_minutes.empty:
    df_display = full_df_with_minutes[full_df_with_minutes['Date'] == hist_datum].copy()
    if not df_display.empty:
        df_display['Zmazať'] = False
        edited_df = st.data_editor(
            df_display[['ID', 'Meno', 'Hodnota', 'Minúty', 'Tankovanie', 'Zmazať']],
            hide_index=True, use_container_width=True,
            column_config={"ID": None, "Minúty": st.column_config.NumberColumn(disabled=True), "Zmazať": st.column_config.CheckboxColumn("Zmazať")},
            key="main_editor"
        )
        if st.button("Uložiť zmeny v tabuľke"):
            to_keep = edited_df[edited_df['Zmazať'] == False][['ID', 'Meno', 'Hodnota', 'Tankovanie']]
            master_df = load_data()
            master_df = master_df[~master_df['ID'].isin(df_display['ID'])]
            to_keep['Date'] = hist_datum
            save_data(pd.concat([master_df, to_keep], ignore_index=True))
            st.rerun()
    else: st.info("Žiadne záznamy.")

# --- SEKCIA 3: SÚHRN ---
st.divider()
st.header("Súhrn minút")

if not full_df_with_minutes.empty:
    # 1. Výpočet CELKOVÉHO súhrnu
    celkovy_sum = full_df_with_minutes.groupby('Meno')['Minúty'].sum().reset_index()
    celkovy_sum = celkovy_sum.rename(columns={'Minúty': 'Celkovo (min)'})

    # 2. Výpočet súhrnu za AKTUÁLNY MESIAC
    today = date.today()
    mask_mesiac = (full_df_with_minutes['Date'].apply(lambda x: x.month == today.month)) & \
                  (full_df_with_minutes['Date'].apply(lambda x: x.year == today.year))
    
    mesacny_df = full_df_with_minutes[mask_mesiac]
    mesacny_sum = mesacny_df.groupby('Meno')['Minúty'].sum().reset_index()
    mesacny_sum = mesacny_sum.rename(columns={'Minúty': 'Tento mesiac (min)'})

    # 3. Spojenie tabuliek a zoradenie
    finalny_suhrn = pd.merge(celkovy_sum, mesacny_sum, on='Meno', how='left').fillna(0)
    finalny_suhrn['Tento mesiac (min)'] = finalny_suhrn['Tento mesiac (min)'].astype(int)
    
    # Zoradenie od najvyššieho po najnižšie (podľa celkových minút)
    finalny_suhrn = finalny_suhrn.sort_values(by='Celkovo (min)', ascending=False)

    st.dataframe(finalny_suhrn, hide_index=True, use_container_width=True)
else:
    st.info("Zatiaľ nie sú k dispozícii žiadne dáta pre súhrn.")

# --- SEKCIA 4: FILTROVANÝ SÚHRN (KRAJŠÍ DIZAJN) ---
st.divider()
st.header("Súhrn podľa mesiacov")

mesiace_map = {
    "Apríl": 4, "Máj": 5, "Jún": 6, "Júl": 7, 
    "August": 8, "September": 9, "Október": 10
}

# 1. Možnosť: Moderné "Pills" (tlačidlá)
# Ak chceš, aby boli na začiatku všetky vypnuté, zmeň selection_mode na "single" alebo nechaj prázdny výber
vybrane_názvy = st.pills(
    "Vyber mesiace (klikni pre aktiváciu):",
    options=list(mesiace_map.keys()),
    selection_mode="multi"
)

# Ak tvoj Streamlit vyhodí chybu pri st.pills, použi tento zakomentovaný kód nižšie (checkboxy v stĺpcoch):
# st.write("Vyber mesiace:")
# cols = st.columns(len(mesiace_map))
# vybrane_názvy = []
# for i, (m_name, m_num) in enumerate(mesiace_map.items()):
#     if cols[i].checkbox(m_name):
#         vybrane_názvy.append(m_name)

if not full_df_with_minutes.empty and vybrane_názvy:
    vybrane_cisla = [mesiace_map[m] for m in vybrane_názvy]
    
    mask_custom = full_df_with_minutes['Date'].apply(lambda x: x.month in vybrane_cisla)
    filtered_df = full_df_with_minutes[mask_custom]
    
    if not filtered_df.empty:
        custom_sum = filtered_df.groupby('Meno')['Minúty'].sum().reset_index()
        custom_sum.columns = ['Meno', 'Suma minút']
        custom_sum = custom_sum.sort_values(by='Suma minút', ascending=False)
        
        # Zobrazenie výsledku v peknom formáte
        st.subheader(f"Štatistika za: {', '.join(vybrane_názvy)}")
        st.dataframe(custom_sum, hide_index=True, use_container_width=True)
    else:
        st.info("Pre vybrané mesiace nie sú žiadne záznamy.")
elif not vybrane_názvy:
    st.info("☝️ Klikni na mesiace vyššie, aby sa zobrazil súhrn.")
