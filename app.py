import streamlit as st
import pandas as pd
from datetime import date
import uuid
from streamlit_gsheets import GSheetsConnection

# --- NASTAVENIA STRÁNKY ---
st.set_page_config(page_title="Minúty 2026", layout="centered")

# --- PRIPOJENIE NA GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- POMOCNÉ FUNKCIE ---
def load_names():
    # Pre jednoduchosť zoznam mien, môžeš si doplniť načítanie zo súboru ako predtým
    return sorted(["Jozef", "Michal", "Adam", "Ester", "Matti", "Lívia Bač."])

def load_data():
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=["ID", "Date", "Meno", "Hodnota", "Tankovanie"])
        df = df.dropna(how='all')
        df['Date'] = pd.to_datetime(df['Date']).dt.date
        df['Hodnota'] = df['Hodnota'].astype(str).str.zfill(3)
        return df
    except:
        return pd.DataFrame(columns=["ID", "Date", "Meno", "Hodnota", "Tankovanie"])

def save_data(df):
    try:
        # Pred uložením zabezpečíme formátovanie hodnoty
        df['Hodnota'] = df['Hodnota'].astype(str).str.zfill(3)
        conn.update(worksheet="Sheet1", data=df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Chyba pri ukladaní do Google Sheets: {e}")
        return False

# --- VÝPOČET MINÚT A TRIEDENIE (TVOJA PERFEKTNÁ LOGIKA) ---
def process_dataframe(df):
    if df.empty:
        return df
    
    # Pre istotu formátovanie
    df['Hodnota'] = df['Hodnota'].astype(str).str.zfill(3)
    
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
    
    # 1. Zoradenie pre výpočet (vzostupne)
    full_df = full_df.sort_values(['Date', 'SortValue'])
    
    # Výpočet minút
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
    
    # 2. Zoradenie pre zobrazenie (Najnovšie Dátumy a najnovšie SortValue HORE)
    return full_df.sort_values(['Date', 'SortValue'], ascending=[False, False])

# --- CALLBACK PRE ULOŽENIE ---
def save_record_callback():
    hodnota_in = st.session_state.get('input_hodnota', '').strip()
    pridat_nove = st.session_state.get('pridat_nove_checkbox', False)
    vybrane_meno = st.session_state.get('vybrane_meno_selectbox', '')
    nove_meno = st.session_state.get('input_nove_meno', '').strip()
    zaznam_datum = st.session_state.get('zaznam_datum', date.today())
    
    meno_na_zapis = nove_meno if pridat_nove else vybrane_meno
    
    if not hodnota_in.isdigit():
        st.session_state.action_msg = ("error", "Zadaj číselnú hodnotu!")
        return
    
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
    
    if save_data(updated_df):
        st.session_state.input_hodnota = ""
        st.session_state.pridat_nove_checkbox = False
        st.session_state.input_t20 = False
        st.session_state.input_t40 = False
        st.session_state.action_msg = ("success", "Záznam uložený do Google Sheets!")

# --- HLAVNÁ APP ---
st.title("Minúty 2026 🏄")

raw_df = load_data()
full_df_with_minutes = process_dataframe(raw_df)

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
        # Zoradenie v editore - najnovšie SortValue hore
        df_display = df_display.sort_values('SortValue', ascending=False)
        
        edited_df = st.data_editor(
            df_display[['ID', 'Meno', 'Hodnota', 'Minúty', 'Tankovanie']],
            hide_index=True, use_container_width=True,
            column_config={
                "ID": None, 
                "Minúty": st.column_config.NumberColumn("Min (auto)", disabled=True)
            },
            key="main_editor"
        )
        
        if st.button("Uložiť zmeny v tabuľke"):
            # Zoberieme všetko okrem tohto dňa
            master_df = load_data()
            master_df = master_df[master_df['Date'] != hist_datum]
            
            # Pridáme upravené dáta z dneška
            to_keep = edited_df[['ID', 'Meno', 'Hodnota', 'Tankovanie']].copy()
            to_keep['Date'] = hist_datum
            
            new_master = pd.concat([master_df, to_keep], ignore_index=True)
            if save_data(new_master):
                st.success("Zmeny uložené!")
                st.rerun()
    else:
        st.info("Žiadne záznamy.")

# --- SEKCIA 3: SÚHRN (Mesačný + Celkový) ---
st.divider()
st.header("Súhrn minút")

if not full_df_with_minutes.empty:
    # Celkový
    celkovy_sum = full_df_with_minutes.groupby('Meno')['Minúty'].sum().reset_index()
    celkovy_sum.columns = ['Meno', 'Celkovo (min)']

    # Aktuálny mesiac
    today = date.today()
    mesacny_df = full_df_with_minutes[
        (pd.to_datetime(full_df_with_minutes['Date']).dt.month == today.month) & 
        (pd.to_datetime(full_df_with_minutes['Date']).dt.year == today.year)
    ]
    mesacny_sum = mesacny_df.groupby('Meno')['Minúty'].sum().reset_index()
    mesacny_sum.columns = ['Meno', f'Mesiac {today.month} (min)']

    final_summary = pd.merge(celkovy_sum, mesacny_sum, on='Meno', how='left').fillna(0)
    final_summary.iloc[:, 1:] = final_summary.iloc[:, 1:].astype(int)
    st.dataframe(final_summary.sort_values('Celkovo (min)', ascending=False), hide_index=True, use_container_width=True)

# --- SEKCIA 4: FILTROVANÝ SÚHRN (SEZÓNA) ---
st.divider()
st.header("Súhrn podľa výberu mesiacov")
sezona_map = {"Apríl": 4, "Máj": 5, "Jún": 6, "Júl": 7, "August": 8, "September": 9, "Október": 10}

vybrane_mesiace = st.pills("Klikni na mesiace sezóny:", options=list(sezona_map.keys()), selection_mode="multi")

if vybrane_mesiace and not full_df_with_minutes.empty:
    cisla = [sezona_map[m] for m in vybrane_mesiace]
    filt_df = full_df_with_minutes[pd.to_datetime(full_df_with_minutes['Date']).dt.month.isin(cisla)]
    if not filt_df.empty:
        res = filt_df.groupby('Meno')['Minúty'].sum().reset_index().sort_values('Minúty', ascending=False)
        st.dataframe(res, hide_index=True, use_container_width=True)
    else:
        st.info("Žiadne záznamy pre tieto mesiace.")
