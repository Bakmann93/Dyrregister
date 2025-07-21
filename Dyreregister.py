import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials

# Google Sheets opsætning
SHEET_URL = "https://docs.google.com/spreadsheets/d/1TqBD5etiHRWYsgnKz1O-ZkKn6KobHIPS89wScsq63JY/edit"
SHEET_NAME = "Ark1"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# ✅ Brug secrets i stedet for lokal fil
credentials = Credentials.from_service_account_info(
    st.secrets["gcp_secret_json"], scopes=SCOPES
)
client = gspread.authorize(credentials)
worksheet = client.open_by_url(SHEET_URL).worksheet(SHEET_NAME)


# Funktion: Gem DataFrame til Google Sheets
def gem_til_google_sheets(df):
    worksheet.clear()
    worksheet.append_row(df.columns.tolist())
    df = df.fillna("")

    # Konverter alle Timestamps og datoer til strenge (dd/mm/yyyy)
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%d/%m/%Y")
        elif df[col].apply(lambda x: isinstance(x, (datetime.date, datetime.datetime))).any():
            df[col] = df[col].apply(lambda x: x.strftime("%d/%m/%Y") if isinstance(x, (datetime.date, datetime.datetime)) else x)

    for row in df.values.tolist():
        worksheet.append_row(row)

# Indlæs data fra Google Sheets
def hent_data():
    records = worksheet.get_all_records()
    return pd.DataFrame(records)

df = hent_data()

# --- UI ---
st.title("🐔🐱 Dyregister")

# 📅 Faner per år
st.header("📅 Faner pr. år")
if not df.empty:
    df["Købt/Født"] = pd.to_datetime(df["Købt/Født"], errors='coerce', dayfirst=True)
    df["År"] = df["Købt/Født"].dt.year
    årstal = sorted(df["År"].dropna().unique().astype(int).tolist())

    if årstal:
        tabs = st.tabs([str(år) for år in årstal])
        for i, år in enumerate(årstal):
            with tabs[i]:
                st.subheader(f"Dyr i {år} ({len(df[df['År'] == år])} stk.)")
                for art in df["Art"].unique():
                    art_df = df[(df["År"] == år) & (df["Art"] == art)]
                    if not art_df.empty:
                        with st.expander(f"🧬 {art} ({len(art_df)} stk.)"):
                            visnings_df = art_df.copy()
                            if "Købt/Født" in visnings_df.columns:
                                visnings_df["Købt/Født"] = visnings_df["Købt/Født"].dt.strftime("%d/%m/%Y")
                            st.dataframe(visnings_df, use_container_width=True)


# 📊 Optælling
st.header("📊 Optælling pr. år og art")
if not df.empty:
    optælling = df.groupby(["År", "Art"]).size().unstack(fill_value=0)
    st.dataframe(optælling)

# ➕ Tilføj nyt dyr
with st.expander("➕ Tilføj nyt dyr"):
    with st.form("tilføj_dyr_formular"):
        navn = st.text_input("Navn")
        art = st.text_input("Art")
        kf = st.date_input("Købt/Født", value=datetime.date.today())
        foder = st.text_area("Foder")
        bemærkninger = st.text_area("Bemærkninger")

        if st.form_submit_button("Tilføj"):
            ny_række = pd.DataFrame([{
                "Navn": navn,
                "Art": art,
                "Købt/Født": kf.strftime("%d/%m/%Y"),
                "Død/Solgt": "",  # Tomt til at starte med
                "Foder": foder,
                "Bemærkninger": bemærkninger
            }])
            df = pd.concat([df, ny_række], ignore_index=True)
            gem_til_google_sheets(df)
            st.success(f"{navn} tilføjet.")


# ✏️ Rediger eller slet dyr
with st.expander("✏️ Rediger eller slet eksisterende dyr"):
    if not df.empty:
        selected_index = st.selectbox("Vælg række der skal redigeres/slettes:", df.index, format_func=lambda i: df.at[i, "Navn"])
        if selected_index is not None:
            navn_edit = st.text_input("Navn", df.at[selected_index, "Navn"])
            art_edit = st.text_input("Art", df.at[selected_index, "Art"])

            # Robust håndtering af datoer
            def hent_dato(kolonne):
                værdi = df.at[selected_index, kolonne]
                if isinstance(værdi, str) and værdi.strip() != "":
                    try:
                        return datetime.datetime.strptime(værdi.strip(), "%d/%m/%Y").date()
                    except ValueError:
                        return datetime.date.today()
                elif isinstance(værdi, pd.Timestamp):
                    return værdi.date()
                elif isinstance(værdi, datetime.date):
                    return værdi
                return datetime.date.today()

            kf_edit = st.date_input("Købt/Født", hent_dato("Købt/Født"))
            ds_edit = st.date_input("Død/Solgt", hent_dato("Død/Solgt"))

            foder_edit = st.text_area("Foder", df.at[selected_index, "Foder"] if "Foder" in df.columns else "")
            bem_edit = st.text_area("Bemærkninger", df.at[selected_index, "Bemærkninger"] if "Bemærkninger" in df.columns else "")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Gem ændringer"):
                    df.at[selected_index, "Navn"] = navn_edit
                    df.at[selected_index, "Art"] = art_edit
                    df.at[selected_index, "Købt/Født"] = kf_edit.strftime("%d/%m/%Y")
                    df.at[selected_index, "Død/Solgt"] = ds_edit.strftime("%d/%m/%Y") if ds_edit else ""
                    df.at[selected_index, "Foder"] = foder_edit
                    df.at[selected_index, "Bemærkninger"] = bem_edit
                    gem_til_google_sheets(df)
                    st.success("Række opdateret.")

            with col2:
                if st.button("🗑️ Slet række"):
                    df = df.drop(index=selected_index).reset_index(drop=True)
                    gem_til_google_sheets(df)
                    st.warning("Række slettet.")
    else:
        st.info("Ingen data at redigere endnu.")

