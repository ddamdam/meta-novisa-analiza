import streamlit as st
import pdfplumber
import pandas as pd
import io
import re

st.set_page_config(page_title="Analizator Faktur Meta | Novisa Development", layout="centered")

# Dodajemy informację o firmie w widocznym miejscu
st.title("📄 Analizator Faktur Meta (Facebook Ads)")
st.markdown("Aplikacja **Novisa Development** do analizy faktur i kampanii reklamowych Facebook Ads.")

# Uaktualniony słownik z poszerzonymi synonimami
investments_synonyms = {
    "AP": {
        "full_name": "Apartamenty Przyjaciół",
        "synonyms": [
            "apartamenty przyjaciol",
            "apartamenty przyjaciół",
            "ap ",
            "ap_form",
            "ap"  # uwzględniamy też bez spacji
        ]
    },
    "BK": {
        "full_name": "Boska Ksawerowska",
        "synonyms": [
            "boska ksawerowska",
            "boska ksawerowska_form"
        ]
    },
    "MAM2": {
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
            "om",
            "osiedle mlodych",
            "osiedle młodych",
            "os mlodych"
        ]
    },
    "ON": {
        "full_name": "Osiedle Natura",
        "synonyms": [
            "on",
            "osiedle natura"
        ]
    },
    "OS": {
        "full_name": "Osiedle Słoneczne",
        "synonyms": [
            "osiedle sloneczne",
            "osiedle słoneczne",
            "os ",
            "os"  # dopisane, by złapać "rozpoznawalnosc os"
        ]
    },
    "PT": {
        "full_name": "Pod Topolami",
        "synonyms": [
            "pt",
            "pod topolami"
        ]
    },
    "SW": {
        "full_name": "Slow Wilanów",
        "synonyms": [
            "slow wilanow",
            "slow wilanów",
            "sw"
        ]
    },
    "WPL": {
        "full_name": "Wille przy Lesie",
        "synonyms": [
            "wpl",
            "wille przy lesie"
        ]
    },
    "ZO": {
        "full_name": "Zielone Ogrody",
        "synonyms": [
            "zo",
            "zielone ogrody",
            "zielone ogrody_form",
            "zielone ogrody_form kampania"
        ]
    },
    "ZM": {
        "full_name": "Zielono Mi",
        "synonyms": [
            "zm",
            "zm_form",
            "zielono mi",
            "zm form",
            "zm_"
        ]
    },
}

import pdfplumber

def normalize_polish(text: str) -> str:
    """
    Usuwa polskie znaki i konwertuje na lower-case.
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
    Próbuje dopasować nazwę kampanii do jednej z inwestycji na podstawie słowników.
    Jeśli nie znajdzie dopasowania, zwraca ('INNE (NOVISA)', 'INNE (NOVISA)').
    """
    norm_name = normalize_polish(campaign_name)

    for short_code, data in investments_synonyms.items():
        full_name = data["full_name"]
        for raw_syn in data["synonyms"]:
            norm_syn = normalize_polish(raw_syn)
            # Jeśli synonim występuje w znormalizowanej nazwie
            if norm_syn in norm_name:
                return (short_code, full_name)

    return ("INNE (NOVISA)", "INNE (NOVISA)")

def extract_campaigns(file) -> pd.DataFrame:
    """
    Otwiera plik PDF i na podstawie wzorców w treści wyszukuje informacje o kampaniach.
    Zwraca DataFrame z kolumnami:
    Kampania, Kwota (zł), Inwestycja (skrót), Inwestycja (nazwa).
    """
    campaigns = []
    with pdfplumber.open(file) as pdf:
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
    # Regex kwoty: "1 234,56 zł" lub "123,45 zł"
    amount_pattern = re.compile(r"([\d\s]+,\d{2})\s*zł")

    for i in range(len(lines)):
        if date_pattern.match(lines[i]):
            # Zakładamy, że kampania jest 2 linie wyżej, kwota 1 linię wyżej
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
            df_single = extract_campaigns(single_file)
            if not df_single.empty:
                df_single["Plik"] = single_file.name
                all_dfs.append(df_single)
            else:
                st.warning(f"Nie udało się znaleźć danych kampanii w pliku: {single_file.name}")

        if all_dfs:
            df_combined = pd.concat(all_dfs, ignore_index=True)

            # Zakładki: Szczegółowy, Raport (Inwestycje -> Kampanie), Raport uproszczony
            tab_szczegoly, tab_raport, tab_raport_uproszczony = st.tabs(
                ["Szczegółowy", "Raport", "Raport uproszczony"]
            )

            with tab_szczegoly:
                st.subheader("Widok szczegółowy")
                st.dataframe(df_combined)
                total_all = df_combined["Kwota (zł)"].sum()
                st.write(f"**Łączna kwota (wszystkie pliki)**: {total_all:.2f} zł")

                # Eksport do Excela (szczegóły)
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

                # Eksport do Excela (ten sam df_combined, bo raport i tak się z niego generuje)
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

                # Grupujemy tylko po inwestycji i sumujemy kwoty, bez rozpisywania kampanii
                df_simpl = (
                    df_combined
                    .groupby(["Inwestycja (skrót)", "Inwestycja (nazwa)"], as_index=False)["Kwota (zł)"]
                    .sum()
                )

                # Wyświetlamy
                st.dataframe(df_simpl)

                # Suma globalna
                total_simple = df_simpl["Kwota (zł)"].sum()
                st.write(f"**Łącznie (wszystkie inwestycje)**: {total_simple:.2f} zł")

                # Eksport do Excela (raport uproszczony)
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

# Ewentualne podsumowanie lub stopka:
st.markdown("---")
st.markdown("**Novisa Development**")
