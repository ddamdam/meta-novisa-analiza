import streamlit as st
import pdfplumber
import pandas as pd
import io
import re

st.set_page_config(page_title="Analizator Faktur Meta | Novisa Development", layout="centered")

# Informacja o firmie
st.title("📄 Analizator Faktur Meta (Facebook Ads)")
st.markdown("Aplikacja **Novisa Development** do analizy faktur i kampanii reklamowych Facebook Ads.")

# Zaktualizowany słownik z poszerzonymi synonimami + zmiana MAM2 -> MM2
investments_synonyms = {
    "AP": {
        "full_name": "Apartamenty Przyjaciół",
        "synonyms": [
            "apartamenty przyjaciol",
            "apartamenty przyjaciół",
            "ap_form",
            "apartamenty przyjaci"
        ]
    },
    "BK": {
        "full_name": "Boska Ksawerowska",
        "synonyms": [
            "boska ksawerowska",
            "boska ksawerowska_form"
        ]
    },
    "MM2": {
        "full_name": "Manufaktura Marki 2",
        "synonyms": [
            "manufaktura marki 2",
            "manufaktura marki"
        ]
    },
    "MO4": {
        "full_name": "Miasto Ogród 4",
        "synonyms": [
            "miasto ogrod 4",
            "miasto ogród 4"
        ]
    },
    "MO5": {
        "full_name": "Miasto Ogród 5",
        "synonyms": [
            "mo5",
            "miasto ogród 5",
            "miasto ogrod 5",
            "mo5_kampania"
        ]
    },
    "MO6": {
        "full_name": "Miasto Ogród 6",
        "synonyms": [
            "mo6",
            "miasto ogród 6",
            "miasto ogrod 6"
        ]
    },
    "NM5": {
        "full_name": "Nova Magdalenka 5",
        "synonyms": [
            "nm5",
            "nova magdalenka 5",
            "magdalenka 5",
            "nm5_form kampania",
            "nm5_form"
        ]
    },
    "NM6": {
        "full_name": "Nova Magdalenka 6",
        "synonyms": [
            "nm6",
            "nova magdalenka 6",
            "magdalenka 6"
        ]
    },
    "NM7": {
        "full_name": "Nova Magdalenka 7",
        "synonyms": [
            "nm7",
            "nova magdalenka 7",
            "magdalenka 7"
        ]
    },
    "OP5": {
        "full_name": "Ogrody Przyjaciół 5",
        "synonyms": [
            "op5",
            "op5_form kampania",
            "op5_form",
            "ogrody przyjaciół 5",
            "ogrody przyjaciol 5"
        ]
    },
    "OM": {
        "full_name": "Osiedle Młodych",
        "synonyms": [
            "osiedle mlodych",
            "osiedle młodych",
            "os mlodych"
        ]
    },
    "ON": {
        "full_name": "Osiedle Natura",
        "synonyms": [
            "osiedle natura"
            # Usuwamy krótkie 'on' by uniknąć kolizji z "zielONe"
        ]
    },
    "OS": {
        "full_name": "Osiedle Słoneczne",
        "synonyms": [
            "osiedle sloneczne",
            "osiedle słoneczne",
            "rozpoznawalnosc os",   # dopisujemy, by "rozpoznawalnosc os" była kojarzona
            "rozpoznawalność os"   # lub z polskim znakiem
        ]
    },
    "PT": {
        "full_name": "Pod Topolami",
        "synonyms": [
            "pod topolami"
        ]
    },
    "SW": {
        "full_name": "Slow Wilanów",
        "synonyms": [
            "slow wilanow",
            "slow wilanów"
        ]
    },
    "WPL": {
        "full_name": "Wille przy Lesie",
        "synonyms": [
            "wille przy lesie"
        ]
    },
    "ZO": {
        "full_name": "Zielone Ogrody",
        "synonyms": [
            "zielone ogrody",
            "zielone ogrody_form",
            "zielone ogrody_form kampania"
        ]
    },
    "ZM": {
        "full_name": "Zielono Mi",
        "synonyms": [
            "zielono mi",
            "zm_form",
            "zm form",
            "zm_"
        ]
    },
}

def normalize_polish(text: str) -> str:
    """
    Usuwa polskie znaki i konwertuje do lower-case.
    """
    replace_map = {
        "ą": "a", "ć": "c", "ę": "e", "ł": "l",
        "ń": "n", "ó": "o", "ś": "s", "ź": "z",
        "ż": "z"
    }
    text_lower = text.lower()
    for plchar, ascii_char in replace_map.items():
        text_lower = text_lower.replace(plchar, ascii_char)
    return text_lower

def find_investment(campaign_name: str) -> tuple[str, str]:
    """
    Logika decydująca o tym, do której inwestycji przypisać nazwę kampanii.

    Zasady:
    1) Jeśli nazwa kampanii zawiera "post na instagramie" => INNE (NOVISA).
    2) Zamieniamy '_' na spacje, by np. "boska ksawerowska_listopad" => "boska ksawerowska listopad".
    3) Szukamy synonimów w prosty sposób: if norm_syn in norm_name.
    4) Jeśli nic nie pasuje => INNE (NOVISA).
    """
    norm_name = normalize_polish(campaign_name)

    # 1) "Post na instagramie" zawsze do INNE
    if "post na instagramie" in norm_name:
        return ("INNE (NOVISA)", "INNE (NOVISA)")

    # 2) Zamiana podkreśleń na spacje
    norm_name = norm_name.replace("_", " ")

    # 3) Przeszukiwanie słownika
    for short_code, data in investments_synonyms.items():
        for raw_syn in data["synonyms"]:
            norm_syn = normalize_polish(raw_syn)
            if norm_syn in norm_name:
                return (short_code, data["full_name"])

    # 4) Jeśli brak dopasowania
    return ("INNE (NOVISA)", "INNE (NOVISA)")

def extract_campaigns(file_bytes: bytes) -> pd.DataFrame:
    """
    Otwiera plik PDF (bytes) i na podstawie wzorców w treści wyszukuje informacje o kampaniach.
    Zwraca DataFrame z kolumnami: Kampania, Kwota (zł), Inwestycja (skrót), Inwestycja (nazwa).
    """
    campaigns = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        lines = []
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                for ln in page_text.split("\n"):
                    ln = ln.strip()
                    if ln:
                        lines.append(ln)

    # Regex do wychwycenia linii typu: "Od 01.12.2024 do 31.12.2024"
    date_pattern = re.compile(r"^Od\s.*\sdo\s.*$")
    # Regex kwoty: np. "1 234,56 zł" lub "123,45 zł"
    amount_pattern = re.compile(r"([\d\s]+,\d{2})\s*zł")

    for i in range(len(lines)):
        if date_pattern.match(lines[i]):
            # Zakładamy, że kampania jest 2 linie wyżej, a kwota 1 linię wyżej
            if i < 2:
                continue
            campaign_line = lines[i - 2]
            amount_line = lines[i - 1]

            match = amount_pattern.search(amount_line)
            if match:
                amt_str = match.group(1).replace(' ', '').replace(',', '.')
                try:
                    amount = float(amt_str)
                except ValueError:
                    amount = None

                if amount is not None:
                    inv_code, inv_name = find_investment(campaign_line)
                    campaigns.append(
                        (campaign_line, amount, inv_code, inv_name)
                    )

    df = pd.DataFrame(campaigns, columns=[
        "Kampania",
        "Kwota (zł)",
        "Inwestycja (skrót)",
        "Inwestycja (nazwa)"
    ])
    return df

uploaded_files = st.file_uploader(
    "Wrzuć jeden lub kilka plików PDF z fakturami",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    all_dfs = []
    with st.spinner("Przetwarzanie faktur..."):
        for single_file in uploaded_files:
            file_bytes = single_file.read()
            df_single = extract_campaigns(file_bytes)
            if not df_single.empty:
                df_single["Plik"] = single_file.name
                all_dfs.append(df_single)
            else:
                st.warning(f"Nie udało się znaleźć danych kampanii w pliku: {single_file.name}")

    if all_dfs:
        df_combined = pd.concat(all_dfs, ignore_index=True)

        # Zakładki: Szczegółowy, Raport, Raport uproszczony
        tab_szczegoly, tab_raport, tab_raport_uproszczony = st.tabs(
            ["Szczegółowy", "Raport", "Raport uproszczony"]
        )

        with tab_szczegoly:
            st.subheader("Widok szczegółowy")
            st.dataframe(df_combined)
            total_all = df_combined["Kwota (zł)"].sum()
            st.write(f"**Łączna kwota (wszystkie pliki)**: {total_all:.2f} zł")

            # Eksport do Excela - szczegóły
            to_excel = io.BytesIO()
            df_combined.to_excel(to_excel, index=False)
            to_excel.seek(0)
            st.download_button(
                label="📥 Pobierz szczegółowy arkusz (Excel)",
                data=to_excel,
                file_name="kampanie_szczegoly.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        with tab_raport:
            st.subheader("Raport: Inwestycje -> Kampanie")

            df_grouped = df_combined.groupby(["Inwestycja (skrót)", "Inwestycja (nazwa)"])
            total_sum = 0.0

            for (inv_code, inv_name), group_df in df_grouped:
                st.markdown(f"### {inv_code} - {inv_name}")
                sub = group_df[["Kampania", "Kwota (zł)"]].reset_index(drop=True)
                group_sum = sub["Kwota (zł)"].sum()
                total_sum += group_sum
                st.dataframe(sub)
                st.write(f"**Razem: {group_sum:.2f} zł**")
                st.write("---")

            st.write(f"### Łączna kwota (wszystkie inwestycje): {total_sum:.2f} zł")

            to_excel_raport = io.BytesIO()
            df_combined.to_excel(to_excel_raport, index=False)
            to_excel_raport.seek(0)
            st.download_button(
                label="📥 Pobierz raport inwestycje (Excel)",
                data=to_excel_raport,
                file_name="raport_inwestycje_kampanie.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        with tab_raport_uproszczony:
            st.subheader("Raport uproszczony: Kwota łącznie dla każdej inwestycji")

            df_simpl = (
                df_combined
                .groupby(["Inwestycja (skrót)", "Inwestycja (nazwa)"], as_index=False)["Kwota (zł)"]
                .sum()
            )
            st.dataframe(df_simpl)

            total_simple = df_simpl["Kwota (zł)"].sum()
            st.write(f"**Łącznie (wszystkie inwestycje)**: {total_simple:.2f} zł")

            to_excel_simpl = io.BytesIO()
            df_simpl.to_excel(to_excel_simpl, index=False)
            to_excel_simpl.seek(0)
            st.download_button(
                label="📥 Pobierz raport uproszczony (Excel)",
                data=to_excel_simpl,
                file_name="raport_uproszczony_inwestycje.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    else:
        st.warning("Żaden z wgranych plików nie zawierał danych kampanii.")

# Stopka
st.markdown("---")
st.markdown("**Novisa Development**")
