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
    """Načíta dáta a vynúti čerstvú verziu bez cache."""
    try:
        # ttl=0 je kľúčové, aby sme nečítali staré verzie z pamäte
        df = conn.read(worksheet="Sheet1", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=["ID", "Date", "Meno", "Hodnota", "Minúty", "Tankovanie"])
        
        df = df.dropna(how='all')
        # Prevod dátumu a hodnôt na správny formát
        df['Date'] = pd.to_datetime(df['Date']).dt.date
        df['Hodnota'] = df['Hodnota'].astype(str).str.strip()
        return df
    except:
        return pd.DataFrame(columns=["ID", "Date", "Meno", "Hodnota", "Minúty", "Tankovanie"])

def save_data(df):
    """Uloží dáta a okamžite premaže cache, aby ďalšie načítanie bolo správne."""
    try:
        conn.update(worksheet="Sheet1", data=df)
        st.cache_data.clear() # Vymaže internú pamäť Streamlitu
        return True
    except Exception as e:
        st.error(f"Chyba pri ukladaní: {e}")
        return False

# --- VÝPOČET MINÚT A TRIEDENIE ---
def process_dataframe(df):
    if df.empty:
        return df
    
    df = df.copy()
    # Odstránime riadky, ktoré nemajú dátum alebo hodnotu
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
    unique_dates = sorted(df['Date'].unique())
    
    for d in unique_dates:
        day_df = df[df['Date'] == d].copy()
        day_df = prep_sort(day_df)
        processed_days.append(day_df)
    
    full_df = pd.concat(processed_days)
    full_df = full_df.sort_values(['Date', 'SortValue'])
    
    # Prepočet minút
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
    # Ponecháme len pôvodné stĺpce
    return full_df[["ID", "Date", "Meno", "Hodnota", "Minúty", "Tankovanie"]]

# --- CALLBACK PRE ULOŽENIE NOVÉHO ---
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
    
    # Načítame aktuálny stav priamo z Google Sheets (ttl=0)
    current_df = load_data()
    updated_df = pd.concat([current_df, pd.DataFrame([new_row])], ignore_index=True)
    final_df = process_dataframe(updated_df)
    
    if save_data(final_df):
        st.session_state.input_hodnota = ""
        st.session_state.pridat_nove_checkbox = False
        st.session_state.input_t20 = False
        st.session_state.input_t40 = False
        st.session_state.action_msg = ("success", "Záznam uložený! ✅")

# --- HLAVNÁ APP ---
st.title("Minúty 2026 🏄")

raw_df = load_data()
# Procesujeme dáta, aby sa prepočítali minúty pre zobrazenie
full_df_display = process_dataframe(raw_df)

# --- SEKCIA 1: PRIDAŤ ---
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

# --- SEKCIA 2: HISTÓRIA A EDITÁCIA ---
st.header("História")
hist_datum = st.date_input("Dátum histórie", date.today(), key="historia_datum")

if not full_df_display.empty:
    # Vyberieme záznamy pre konkrétny deň na editáciu
    df_day = full_df_display[full_df_display['Date'] == hist_datum].copy()
    
    if not df_day.empty:
        df_day['Zmazať'] = False
        
        edited_df = st.data_editor(
            df_day[['ID', 'Meno', 'Hodnota', 'Minúty', 'Tankovanie', 'Zmazať']],
            hide_index=True, 
            use_container_width=True,
            column_config={
                "ID": None, # ID skryjeme
                "Minúty": st.column_config.NumberColumn("Min (auto)", disabled=True), 
                "Zmazať": st.column_config.CheckboxColumn("Zmazať 🗑️")
            },
            key="main_editor"
        )
        
        if st.button("Uložiť zmeny v histórii", use_container_width=True):
            # 1. Získame ID riadkov, ktoré používateľ označil na zmazanie
            ids_to_delete = edited_df[edited_df['Zmazať'] == True]['ID'].tolist()
            
            # 2. Získame upravené dáta z editora (tie, ktoré sa nemajú zmazať)
            df_edited_clean = edited_df[edited_df['Zmazať'] == False].copy()
            
            # 3. Zoberieme CELÚ tabuľku (všetky dni) a odstránime z nej 
            # pôvodné verzie riadkov pre tento deň + tie na zmazanie
            # Týmto krokom zabezpečíme, že ostatné dni ostanú nedotknuté
            ostatne_dni = full_df_display[full_df_display['Date'] != hist_datum]
            
            # 4. Spojíme ostatné dni s tými, ktoré sme práve upravili v editore
            # Pridáme dátum späť k upraveným riadkom, lebo v editore sme ho nezobrazovali
            df_edited_clean['Date'] = hist_datum
            
            # Spojíme to do jednej master tabuľky
            new_master = pd.concat([ostatne_dni, df_edited_clean], ignore_index=True)
            
            # 5. Pre istotu preženieme cez process_dataframe (prepočet minút) a uložíme
            final_to_save = process_dataframe(new_master)
            
            if save_data(final_to_save):
                st.success("Zmeny boli úspešne uložené!")
                st.rerun()
    else:
        st.info(f"Na deň {hist_datum} nie sú žiadne záznamy.")

# --- SEKCIA 3: SÚHRNY (Vždy prepočítané) ---
st.divider()
st.header("Súhrn minút")
if not raw_df.empty:
    calc_df = process_dataframe(raw_df)
    # ... (zvyšok kódu pre súhrny zostáva rovnaký ako predtým)
    celkovy_sum = calc_df.groupby('Meno')['Minúty'].sum().reset_index().sort_values('Minúty', ascending=False)
    st.dataframe(celkovy_sum, hide_index=True, use_container_width=True)
