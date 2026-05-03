import streamlit as st
import pandas as pd
from datetime import date
import uuid
import os
from streamlit_gsheets import GSheetsConnection

# --- NASTAVENIA STRÁNKY ---
st.set_page_config(page_title="Minúty 2026", layout="centered")

# --- PRIPOJENIE NA GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- POMOCNÉ FUNKCIE ---
def load_names_from_file():
    subor_cesta = "Zoznam_mien.txt"
    zakladne_mena = ["Jozef", "Michal"]
    if os.path.exists(subor_cesta):
        try:
            with open(subor_cesta, "r", encoding="utf-8") as f:
                mena_zo_suboru = [line.strip() for line in f if line.strip()]
            if mena_zo_suboru:
                return sorted(list(set(mena_zo_suboru)))
        except:
            pass
    return sorted(zakladne_mena)

def load_data():
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=["ID", "Date", "Meno", "Hodnota", "Minúty", "Tankovanie"])
        df = df.dropna(how='all')
        df['Date'] = pd.to_datetime(df['Date']).dt.date
        df['Hodnota'] = df['Hodnota'].astype(str).str.strip()
        return df
    except:
        return pd.DataFrame(columns=["ID", "Date", "Meno", "Hodnota", "Minúty", "Tankovanie"])

def save_data(df):
    try:
        conn.update(worksheet="Sheet1", data=df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Chyba pri ukladaní: {e}")
        return False

# --- VÝPOČET MINÚT A TRIEDENIE (S TVOJÍM PRAVIDLOM) ---
def process_dataframe(df):
    if df.empty:
        return df
    
    df = df.copy()
    df = df.dropna(subset=['Date', 'Hodnota'])
    df['Hodnota'] = df['Hodnota'].astype(str).str.strip()
    df = df[df['Hodnota'].str.isdigit()]
    
    if df.empty:
        return df

    def prep_sort(group):
        vals = group['Hodnota'].astype(int)
        has_high = (vals >= 900).any()
        has_low = (vals <= 100).any()
        if has_high and has_low:
            group['SortValue'] = group['Hodnota'].apply(lambda x: int(x) + 1000 if int(x) < 500 else int(x))
        else:
            group['SortValue'] = vals.values
        return group

    processed_days = []
    df['Date'] = pd.to_datetime(df['Date']).dt.date
    unique_dates = sorted(df['Date'].unique())
    
    for d in unique_dates:
        day_df = df[df['Date'] == d].copy()
        day_df = prep_sort(day_df)
        processed_days.append(day_df)
    
    full_df = pd.concat(processed_days)
    # Triedenie pre výpočet minút (vzostupne)
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
    return full_df[["ID", "Date", "Meno", "Hodnota", "Minúty", "Tankovanie", "SortValue"]]

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
    final_df = process_dataframe(updated_df)
    
    if save_data(final_df.drop(columns=['SortValue'])):
        st.session_state.input_hodnota = ""
        st.session_state.pridat_nove_checkbox = False
        st.session_state.input_t20 = False
        st.session_state.input_t40 = False
        st.session_state.action_msg = ("success", "Záznam uložený! ✅")

# --- HLAVNÁ APP ---
st.title("Minúty 2026 🏄")

raw_df = load_data()
full_df_display = process_dataframe(raw_df)

# --- PRIDÁVANIE ---
st.header("+ Pridať lyžiara")
col1, col2 = st.columns(2)
with col1:
    st.date_input("Dátum:", date.today(), key="zaznam_datum")
pridat_nove = st.checkbox("+ Pridaj meno", key="pridat_nove_checkbox")

with col2:
    st.selectbox("Meno:", options=load_names_from_file(), disabled=pridat_nove, key="vybrane_meno_selectbox")

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

# --- HISTÓRIA (NAJNOVŠIE HORE PODĽA SortValue) ---
st.header("História")
hist_datum = st.date_input("Dátum histórie", date.today(), key="historia_datum")

if not full_df_display.empty:
    df_day = full_df_display[full_df_display['Date'] == hist_datum].copy()
    if not df_day.empty:
        # Triedenie: Najnovšie záznamy dňa podľa SortValue (tvoje pravidlo) idú hore
        df_day = df_day.sort_values('SortValue', ascending=False)
        
        edited_df = st.data_editor(
            df_day[['ID', 'Meno', 'Hodnota', 'Minúty', 'Tankovanie']],
            hide_index=True, use_container_width=True,
            column_config={
                "ID": None, 
                "Minúty": st.column_config.NumberColumn("Min (auto)", disabled=True), 
            },
            key="main_editor"
        )
        
        if st.button("Uložiť zmeny v histórii"):
            df_others = full_df_display[full_df_display['Date'] != hist_datum]
            df_updated_day = edited_df.copy()
            df_updated_day['Date'] = hist_datum
            
            final_master = pd.concat([df_others, df_updated_day], ignore_index=True)
            final_master = process_dataframe(final_master)
            if save_data(final_master.drop(columns=['SortValue'])):
                st.success("Zmeny uložené!")
                st.rerun()
    else:
        st.info("Žiadne záznamy.")

# --- SÚHRN (MESIAC + CELKOVO) ---
st.divider()
st.header("Súhrn minút")
if not full_df_display.empty:
    today = date.today()
    # Celkový súčet
    total_sum = full_df_display.groupby('Meno')['Minúty'].sum().reset_index()
    total_sum.columns = ['Meno', 'Celkovo']
    
    # Mesačný súčet
    full_df_display['dt'] = pd.to_datetime(full_df_display['Date'])
    month_df = full_df_display[(full_df_display['dt'].dt.month == today.month) & (full_df_display['dt'].dt.year == today.year)]
    month_sum = month_df.groupby('Meno')['Minúty'].sum().reset_index()
    month_sum.columns = ['Meno', f'Mesiac ({today.month})']
    
    summary = pd.merge(month_sum, total_sum, on='Meno', how='outer').fillna(0)
    summary.iloc[:, 1:] = summary.iloc[:, 1:].astype(int)
    st.dataframe(summary.sort_values('Celkovo', ascending=False), hide_index=True, use_container_width=True)

# --- FILTROVANÝ SÚHRN ---
st.divider()
st.header("Súhrn podľa výberu mesiacov")
mesiace_map = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"Máj":5,"Jún":6,"Júl":7,"Aug":8,"Sep":9,"Okt":10,"Nov":11,"Dec":12}
vybrane = st.pills("Vyber mesiace:", options=list(mesiace_map.keys()), selection_mode="multi")

if vybrane and not full_df_display.empty:
    mes_cisla = [mesiace_map[m] for m in vybrane]
    filt_df = full_df_display[pd.to_datetime(full_df_display['Date']).dt.month.isin(mes_cisla)]
    if not filt_df.empty:
        res = filt_df.groupby('Meno')['Minúty'].sum().reset_index().sort_values('Minúty', ascending=False)
        st.dataframe(res, hide_index=True, use_container_width=True)
    else:
        st.info("Žiadne záznamy pre tieto mesiace.")
