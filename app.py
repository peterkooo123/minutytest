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
    """Načíta mená zo súboru Zoznam_mien.txt na GitHube."""
    subor_cesta = "Zoznam_mien.txt"
    zakladne_mena = ["Jozef", "Michal"] # Záloha, ak by súbor neexistoval
    
    if os.path.exists(subor_cesta):
        try:
            with open(subor_cesta, "r", encoding="utf-8") as f:
                # Načíta riadky, odstráni biele znaky a prázdne riadky
                mena_zo_suboru = [line.strip() for line in f if line.strip()]
            if mena_zo_suboru:
                return sorted(list(set(mena_zo_suboru)))
        except Exception as e:
            st.error(f"Chyba pri čítaní súboru s menami: {e}")
    
    return sorted(zakladne_mena)

def load_data():
    try:
        # PRIDANÉ: worksheet="Sheet1" - uisti sa, že sa tvoj list dole v Exceli volá Sheet1
        # PRIDANÉ: ttl=0 - povie Streamlitu: "Zabudni, čo si vedel, a stiahni to teraz znova"
        df = conn.read(worksheet="Sheet1", ttl=0)
        
        if df is None or df.empty:
            return pd.DataFrame(columns=["ID", "Date", "Meno", "Hodnota", "Minúty", "Tankovanie"])
        
        # Očista od prázdnych riadkov
        df = df.dropna(how='all')
        
        # DÔLEŽITÉ: Streamlit niekedy načíta stĺpce s inými menami, ak je tabuľka divne naformátovaná
        # Tu vynútime správne typy
        df['Date'] = pd.to_datetime(df['Date']).dt.date
        df['Hodnota'] = df['Hodnota'].astype(str).str.strip()
        return df
    except Exception as e:
        return pd.DataFrame(columns=["ID", "Date", "Meno", "Hodnota", "Minúty", "Tankovanie"])

def save_data(df):
    try:
        # PRIDANÉ: clear_cache - vymaže internú pamäť Streamlitu pred zápisom
        st.cache_data.clear()
        
        # worksheet="Sheet1" musí byť aj tu
        conn.update(worksheet="Sheet1", data=df)
        return True
    except Exception as e:
        st.error(f"Chyba pri ukladaní: {e}")
        return False

# --- VÝPOČET MINÚT A TRIEDENIE ---
def process_dataframe(df):
    if df.empty:
        return df
    
    df = df.copy()
    df = df.dropna(subset=['Hodnota'])
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
    return full_df

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
    
    if pridat_nove and not nove_meno:
        st.session_state.action_msg = ("error", "Zadaj meno pre nového lyžiara!")
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
    
    if save_data(final_df):
        st.session_state.input_hodnota = ""
        st.session_state.pridat_nove_checkbox = False
        st.session_state.input_t20 = False
        st.session_state.input_t40 = False
        if 'input_nove_meno' in st.session_state:
            st.session_state.input_nove_meno = ""
        st.session_state.action_msg = ("success", "Záznam uložený do Google Sheets! ✅")

# --- HLAVNÁ APP ---
st.title("Minúty 2026 🏄")

raw_df = load_data()
if not raw_df.empty:
    full_df_display = process_dataframe(raw_df).sort_values(['Date', 'Hodnota'], ascending=[False, False])
else:
    full_df_display = raw_df

# --- BOČNÝ PANEL ---
st.sidebar.header("Správa dát")
if not raw_df.empty:
    csv_data = full_df_display.to_csv(index=False).encode('utf-8-sig')
    st.sidebar.download_button("📥 Stiahnuť zálohu (CSV)", data=csv_data, file_name=f"zaloha_{date.today()}.csv", mime="text/csv")

st.sidebar.divider()
st.sidebar.info("Dáta sú automaticky synchronizované s Google Sheets. ☁️")

# --- SEKCIA 1: PRIDAŤ ---
st.header("+ Pridať lyžiara")
col1, col2 = st.columns(2)
with col1:
    st.date_input("Dátum:", date.today(), key="zaznam_datum")
pridat_nove = st.checkbox("+ Pridaj meno", key="pridat_nove_checkbox")

with col2:
    # TU načítavame mená zo súboru Zoznam_mien.txt
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

# --- SEKCIA 2: HISTÓRIA ---
st.header("História")
hist_datum = st.date_input("Dátum histórie", date.today(), key="historia_datum")

if not full_df_display.empty:
    df_day = full_df_display[full_df_display['Date'] == hist_datum].copy()
    if not df_day.empty:
        df_day['Zmazať'] = False
        edited_df = st.data_editor(
            df_day[['ID', 'Meno', 'Hodnota', 'Minúty', 'Tankovanie', 'Zmazať']],
            hide_index=True, use_container_width=True,
            column_config={
                "ID": None, 
                "Minúty": st.column_config.NumberColumn(disabled=True), 
                "Zmazať": st.column_config.CheckboxColumn("Zmazať")
            },
            key="main_editor"
        )
        if st.button("Uložiť zmeny v tabuľke"):
            ids_to_remove = edited_df[edited_df['Zmazať'] == True]['ID'].tolist()
            new_master = raw_df[~raw_df['ID'].isin(ids_to_remove)]
            final_master = process_dataframe(new_master)
            save_data(final_master)
            st.rerun()
    else: st.info("Žiadne záznamy.")

# --- SEKCIA 3: SÚHRN ---
st.divider()
st.header("Súhrn minút")

if not raw_df.empty:
    calc_df = process_dataframe(raw_df)
    celkovy_sum = calc_df.groupby('Meno')['Minúty'].sum().reset_index()
    celkovy_sum = celkovy_sum.rename(columns={'Minúty': 'Celkovo (min)'})

    today = date.today()
    calc_df['Date_dt'] = pd.to_datetime(calc_df['Date'])
    mask_mesiac = (calc_df['Date_dt'].dt.month == today.month) & (calc_df['Date_dt'].dt.year == today.year)
    
    mesacny_df = calc_df[mask_mesiac]
    if not mesacny_df.empty:
        mesacny_sum = mesacny_df.groupby('Meno')['Minúty'].sum().reset_index()
        mesacny_sum = mesacny_sum.rename(columns={'Minúty': 'Tento mesiac (min)'})
        finalny_suhrn = pd.merge(celkovy_sum, mesacny_sum, on='Meno', how='left').fillna(0)
    else:
        celkovy_sum['Tento mesiac (min)'] = 0
        finalny_suhrn = celkovy_sum

    finalny_suhrn['Tento mesiac (min)'] = finalny_suhrn['Tento mesiac (min)'].astype(int)
    finalny_suhrn = finalny_suhrn.sort_values(by='Celkovo (min)', ascending=False)
    st.dataframe(finalny_suhrn, hide_index=True, use_container_width=True)
else:
    st.info("Zatiaľ nie sú k dispozícii žiadne dáta pre súhrn.")

# --- SEKCIA 4: FILTROVANÝ SÚHRN ---
st.divider()
st.header("Súhrn podľa mesiacov")

mesiace_map = {
    "Apríl": 4, "Máj": 5, "Jún": 6, "Júl": 7, 
    "August": 8, "September": 9, "Október": 10
}

vybrane_názvy = st.pills(
    "Vyber mesiace (klikni pre aktiváciu):",
    options=list(mesiace_map.keys()),
    selection_mode="multi"
)

if not raw_df.empty and vybrane_názvy:
    calc_df = process_dataframe(raw_df)
    calc_df['Date_dt'] = pd.to_datetime(calc_df['Date'])
    vybrane_cisla = [mesiace_map[m] for m in vybrane_názvy]
    mask_custom = calc_df['Date_dt'].dt.month.isin(vybrane_cisla)
    filtered_df = calc_df[mask_custom]
    
    if not filtered_df.empty:
        custom_sum = filtered_df.groupby('Meno')['Minúty'].sum().reset_index()
        custom_sum.columns = ['Meno', 'Suma minút']
        custom_sum = custom_sum.sort_values(by='Suma minút', ascending=False)
        st.subheader(f"Štatistika za: {', '.join(vybrane_názvy)}")
        st.dataframe(custom_sum, hide_index=True, use_container_width=True)
