import streamlit as st
import pandas as pd
from datetime import date
import uuid
import os
from streamlit_gsheets import GSheetsConnection

# --- NASTAVENIA ---
st.set_page_config(page_title="Minúty 2026", layout="centered")
NAMES_FILE = "Zoznam_mien.txt"

# --- PRIPOJENIE ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- MENÁ ---
def load_names():
    if not os.path.exists(NAMES_FILE):
        with open(NAMES_FILE, "w", encoding="utf-8") as f:
            f.write("Jozef\nMichal\n")
    with open(NAMES_FILE, "r", encoding="utf-8") as f:
        return sorted([line.strip() for line in f.readlines() if line.strip()])

# --- DÁTA (ČISTÝ MANAŽMENT) ---
def load_raw_data():
    """Stiahne čistú tabuľku z Google Sheets bez úprav."""
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=["ID", "Date", "Meno", "Hodnota", "Tankovanie"])
        df = df.dropna(how='all')
        df['Date'] = pd.to_datetime(df['Date']).dt.date
        return df
    except:
        return pd.DataFrame(columns=["ID", "Date", "Meno", "Hodnota", "Tankovanie"])

def save_to_google(df):
    """Nahrá tabuľku na Google Sheets."""
    try:
        conn.update(worksheet="Sheet1", data=df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Chyba: {e}")
        return False

# --- TVOJA LOGIKA (VÝPOČET A RADENIE) ---
def process_dataframe(df):
    if df.empty: return df
    
    df = df.copy()
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
    
    # 1. Radenie pre výpočet minút
    full_df = full_df.sort_values(['Date', 'SortValue'])
    
    vals = full_df['Hodnota'].astype(int).tolist()
    minutes = []
    prev_val = None
    for v in vals:
        if prev_val is None: minutes.append(0)
        else:
            diff = v - prev_val
            if diff < -500: diff += 1000
            minutes.append(diff)
        prev_val = v
    full_df['Minúty'] = minutes
    
    # 2. Radenie pre zobrazenie (NAJNOVŠIE HORE - podľa teba)
    return full_df.sort_values(['Date', 'SortValue'], ascending=[False, False])

# --- PROGRAM ---
st.title("Minúty 2026 🏄")

# Načítanie
raw_df = load_raw_data()
display_df = process_dataframe(raw_df)

# --- PRIDÁVANIE ---
st.header("+ Pridať záznam")
c1, c2 = st.columns(2)
with c1:
    datum = st.date_input("Dátum", date.today())
    pridat_meno = st.checkbox("+ Nové meno")
with c2:
    vsetky_mena = load_names()
    meno = st.selectbox("Meno", options=vsetky_mena, disabled=pridat_meno)
    if pridat_meno:
        nove_meno = st.text_input("Zadaj meno")

hodnota = st.text_input("Hodnota (0-999)", max_chars=3)
t20 = st.checkbox("20 L")
t40 = st.checkbox("40 L")

if st.button("Uložiť", type="primary"):
    final_meno = nove_meno if pridat_meno else meno
    if hodnota.isdigit() and final_meno:
        # Pridanie mena do súboru
        if pridat_meno and nove_meno not in vsetky_mena:
            with open(NAMES_FILE, "a", encoding="utf-8") as f: f.write(f"{nove_meno}\n")
        
        # Príprava riadku
        tank = []
        if t20: tank.append("20 L")
        if t40: tank.append("40 L")
        
        new_row = pd.DataFrame([{
            "ID": str(uuid.uuid4()),
            "Date": datum,
            "Meno": final_meno,
            "Hodnota": hodnota.zfill(3),
            "Tankovanie": " + ".join(tank) if tank else "-"
        }])
        
        # Uloženie
        new_master = pd.concat([raw_df, new_row], ignore_index=True)
        if save_to_google(new_master):
            st.success("Uložené!")
            st.rerun()

st.divider()

# --- HISTÓRIA (EDITÁCIA) ---
st.header("História dňa")
h_date = st.date_input("Vyber deň", date.today())
den_df = display_df[display_df['Date'] == h_date].copy()

if not den_df.empty:
    # Tu používame tvoj editor
    edited = st.data_editor(
        den_df[['ID', 'Meno', 'Hodnota', 'Minúty', 'Tankovanie']],
        hide_index=True, use_container_width=True,
        column_config={"ID": None, "Minúty": st.column_config.NumberColumn(disabled=True)},
        key="editor"
    )
    
    if st.button("Uložiť zmeny"):
        # Nahradenie dát pre daný deň
        ostatne = raw_df[raw_df['Date'] != h_date]
        upravene = edited[['ID', 'Meno', 'Hodnota', 'Tankovanie']]
        upravene['Date'] = h_date
        
        if save_to_google(pd.concat([ostatne, upravene], ignore_index=True)):
            st.success("Zmenené!")
            st.rerun()
else:
    st.info("Žiadne záznamy.")

# --- SÚHRNY ---
st.divider()
st.header("Súhrn")
if not display_df.empty:
    # Celkovo
    c_sum = display_df.groupby('Meno')['Minúty'].sum().reset_index().sort_values('Minúty', ascending=False)
    st.subheader("Celkovo")
    st.dataframe(c_sum, hide_index=True, use_container_width=True)
    
    # Filtrovanie mesiacov
    st.subheader("Podľa mesiacov")
    m_map = {"Apríl":4,"Máj":5,"Jún":6,"Júl":7,"August":8,"September":9,"Október":10}
    sel_m = st.pills("Mesiace:", options=list(m_map.keys()), selection_mode="multi")
    if sel_m:
        m_nums = [m_map[m] for m in sel_m]
        f_df = display_df[pd.to_datetime(display_df['Date']).dt.month.isin(m_nums)]
        if not f_df.empty:
            r = f_df.groupby('Meno')['Minúty'].sum().reset_index().sort_values('Minúty', ascending=False)
            st.dataframe(r, hide_index=True, use_container_width=True)
