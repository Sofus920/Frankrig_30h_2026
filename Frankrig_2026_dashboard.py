import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import streamlit as st
import warnings

warnings.filterwarnings('ignore')

# --- STREAMLIT OPSÆTNING ---
st.set_page_config(page_title="Karting Analyse 2026", layout="wide")
st.title("🏁 Gokart Analyse: Frankrig 2026")
st.markdown("Interaktiv analyse af track pace, pit-tider og konsistens.")

# --- INDLÆS DATA ---
script_mappe = os.path.dirname(os.path.abspath(__file__))
filnavn = 'Frankrig_2026_opdelt_per_hold.xlsx'
fuld_sti = os.path.join(script_mappe, filnavn)


@st.cache_data
def indlæs_data():
    try:
        return pd.read_excel(fuld_sti, sheet_name=None, decimal=',')
    except FileNotFoundError:
        return None


alle_ark = indlæs_data()

if alle_ark is None:
    st.error(f"Kunne ikke finde Excel-filen på stien: {fuld_sti}")
    st.stop()

vinder_hold_navn = 'Joker Team'
samlet_data = []
pit_data_liste = []

# --- DATABEHANDLING ---
for ark_navn, df_ark in alle_ark.items():
    kolonner = [k for k in df_ark.columns if 'Unnamed' not in str(k)]

    # --- NYT: Tidslinje lister ---
    alle_omgange, stint_navne, kører_navne, stint_kronologi_liste = [], [], [], []
    hold_pit_tider = []

    er_sallies = 'sallie' in ark_navn.lower()

    stint_counter = 1  # Starter vores usynlige kronologiske tæller for holdet

    for kol in kolonner:
        kol_navn_ren = str(kol).strip().lower()
        if kol_navn_ren == 'stint' or kol_navn_ren == 'stint:' or kol_navn_ren.startswith('omga'):
            continue

        if len(df_ark[kol]) > 0:
            forste_tid = pd.to_numeric(df_ark[kol].iloc[0], errors='coerce')
            if pd.notna(forste_tid) and forste_tid > 150:
                hold_pit_tider.append(forste_tid)

        stint_data = pd.to_numeric(
            df_ark[kol], errors='coerce').dropna().tolist()
        if len(stint_data) > 0:
            alle_omgange.extend(stint_data)
            stint_navne.extend([kol] * len(stint_data))

            # Stempler stintet med sit sande løbsnummer ud fra Excel-kolonnen
            stint_kronologi_liste.extend([stint_counter] * len(stint_data))

            if er_sallies:
                kører = str(kol).split(' ')[0].strip()
            else:
                kører = ark_navn
            kører_navne.extend([kører] * len(stint_data))

            stint_counter += 1

    if hold_pit_tider:
        gns_pit = sum(hold_pit_tider) / len(hold_pit_tider)
        pit_data_liste.append({
            'Hold': ark_navn,
            'Gns Pit Tid (Sek)': round(gns_pit, 2),
            'Antal Pitstops': len(hold_pit_tider)
        })

    if len(alle_omgange) > 0:
        hold_df = pd.DataFrame({
            'Omgangstid': alle_omgange,
            'Stint_Navn': stint_navne,
            'Kører': kører_navne,
            'Stint_Kronologi': stint_kronologi_liste  # Flettes ind i datasættet
        })
        hold_df['Akkumuleret_Tid_Sek'] = hold_df['Omgangstid'].cumsum()
        hold_df['Timer_Kørt'] = hold_df['Akkumuleret_Tid_Sek'] / 3600

        if ark_navn == vinder_hold_navn:
            hold_df['Hold_Kategori'] = 'Vinderhold'
        elif er_sallies:
            hold_df['Hold_Kategori'] = 'Sallies'
        else:
            hold_df['Hold_Kategori'] = 'Feltet'

        hold_df['Holdnavn_Fane'] = ark_navn
        samlet_data.append(hold_df)

samlet_df = pd.concat(samlet_data, ignore_index=True)
pit_df = pd.DataFrame(pit_data_liste).sort_values(
    by='Gns Pit Tid (Sek)').reset_index(drop=True)

# Udregn Pace og Delta
interval = 0.25
samlet_df['Tids_Interval'] = (samlet_df['Timer_Kørt'] // interval) * interval
rene_omgange = samlet_df[samlet_df['Omgangstid'] < 100].copy()

vinder_interval = rene_omgange[rene_omgange['Hold_Kategori'] == 'Vinderhold'].groupby(
    'Tids_Interval')['Omgangstid'].mean().reset_index(name='Vinder_Gns')
feltet_interval = rene_omgange[rene_omgange['Hold_Kategori'] == 'Feltet'].groupby(
    'Tids_Interval')['Omgangstid'].mean().reset_index(name='Feltet_Gns')

rene_omgange = pd.merge(rene_omgange, vinder_interval,
                        on='Tids_Interval', how='left')
rene_omgange = pd.merge(rene_omgange, feltet_interval,
                        on='Tids_Interval', how='left')

rene_omgange['Delta_vs_Vinder'] = rene_omgange['Omgangstid'] - \
    rene_omgange['Vinder_Gns']
rene_omgange['Delta_vs_Feltet'] = rene_omgange['Omgangstid'] - \
    rene_omgange['Feltet_Gns']

# --- DASHBOARD LAYOUT ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("⏱️ Pitstop Analyse")
    st.markdown("Gennemsnitlig tid for Omgang 1. Løbsstart er sorteret fra.")
    st.dataframe(pit_df, hide_index=True)

sallies_kun = rene_omgange[rene_omgange['Hold_Kategori'] == 'Sallies']

if not sallies_kun.empty:
    with col2:
        st.subheader("🏎️ Kører Opsummering")
        st.markdown(
            "*Lav 'Std_Afvigelse' = Mange omgange på samme tid (konsistent).*")

        # --- OUTLIER FILTER CHECKBOX ---
        fjern_outliers = st.checkbox("Rens data (Fjern top/bund 5 % omgange)", value=True,
                                     help="Fjerner de 5% hurtigste og langsommeste omgange i HVERT stint, for at filtrere taktisk ventetid, trafik eller fejl fra.")

    if fjern_outliers:
        lower = sallies_kun.groupby(['Holdnavn_Fane', 'Kører', 'Stint_Navn'])[
            'Omgangstid'].transform(lambda x: x.quantile(0.05))
        upper = sallies_kun.groupby(['Holdnavn_Fane', 'Kører', 'Stint_Navn'])[
            'Omgangstid'].transform(lambda x: x.quantile(0.95))
        df_til_beregning = sallies_kun[(sallies_kun['Omgangstid'] >= lower) & (
            sallies_kun['Omgangstid'] <= upper)]
    else:
        df_til_beregning = sallies_kun

    driver_summary = df_til_beregning.groupby(['Holdnavn_Fane', 'Kører']).agg(
        Gns_Omgangstid=('Omgangstid', 'mean'),
        Std_Afvigelse=('Omgangstid', 'std'),
        Tid_Tabt_vs_Vinder=('Delta_vs_Vinder', 'mean'),
        Tid_Tabt_vs_Feltet=('Delta_vs_Feltet', 'mean'),
        Omgange=('Omgangstid', 'count')
    ).reset_index()
    driver_summary['Std_Afvigelse'] = driver_summary['Std_Afvigelse'].fillna(0)

    driver_summary['Total_Tid_Tabt_Vinder (Sek)'] = driver_summary['Tid_Tabt_vs_Vinder'] * \
        driver_summary['Omgange']
    driver_summary['Total_Tid_Tabt_Feltet (Sek)'] = driver_summary['Tid_Tabt_vs_Feltet'] * \
        driver_summary['Omgange']
    driver_summary = driver_summary.sort_values(
        by=['Holdnavn_Fane', 'Total_Tid_Tabt_Vinder (Sek)'])

    # Inkluderer Stint_Kronologi i vores beregning
    stint_summary = df_til_beregning.groupby(['Holdnavn_Fane', 'Kører', 'Stint_Navn', 'Stint_Kronologi']).agg(
        Gns_Omgangstid=('Omgangstid', 'mean'),
        Std_Afvigelse=('Omgangstid', 'std'),
        Tid_Tabt_vs_Vinder=('Delta_vs_Vinder', 'mean'),
        Tid_Tabt_vs_Feltet=('Delta_vs_Feltet', 'mean'),
        Omgange=('Omgangstid', 'count')
    ).reset_index()
    stint_summary['Std_Afvigelse'] = stint_summary['Std_Afvigelse'].fillna(0)

    stint_summary['Total_Tid_Tabt_Vinder (Sek)'] = stint_summary['Tid_Tabt_vs_Vinder'] * \
        stint_summary['Omgange']
    stint_summary['Total_Tid_Tabt_Feltet (Sek)'] = stint_summary['Tid_Tabt_vs_Feltet'] * \
        stint_summary['Omgange']

    # --- NYT: Sorterer kun på vores sande usynlige tidslinje ---
    stint_summary = stint_summary.sort_values(
        by=['Holdnavn_Fane', 'Stint_Kronologi'])

    # Drop den usynlige kolonne for tabellen, men bevar den originale til senere
    visnings_stint = stint_summary.drop(columns=['Stint_Kronologi'])

    with col2:
        st.dataframe(driver_summary, hide_index=True)

    st.markdown("---")

    # --- KØRER DEEP-DIVE MED RATING ---
    st.subheader("👤 Kører Deep-Dive & Ratings")
    st.markdown("Vælg en specifik kører for at se detaljerede stints, graf og en beregnet Speed & Consistency Score (0-100). *Nu sorteret fuldstændig kronologisk.*")

    unikke_kørere = sorted(df_til_beregning['Kører'].unique())
    valgt_kører = st.selectbox("Vælg Kører:", unikke_kørere)
    kører_data = visnings_stint[visnings_stint['Kører'] == valgt_kører]

    # RATING LOGIK
    gns_delta = kører_data['Tid_Tabt_vs_Vinder'].mean()
    speed_rating = int(max(0, min(100, 90 - (gns_delta * 40))))

    gns_std = kører_data['Std_Afvigelse'].mean()
    cons_rating = int(max(0, min(100, 100 - ((gns_std - 0.05) * 150))))

    m1, m2, m3 = st.columns(3)
    m1.metric("🏁 Speed Rating (0-100)", f"{speed_rating}")
    m2.metric("⏱️ Consistency Rating (0-100)", f"{cons_rating}")
    m3.metric("🔁 Totale omgange (vist i beregning)",
              f"{int(kører_data['Omgange'].sum())}")

    st.write("")

    col_table, col_chart = st.columns([1.5, 1])

    with col_table:
        st.dataframe(kører_data.drop(
            columns=['Holdnavn_Fane', 'Kører']), hide_index=True)

    with col_chart:
        valgt_reference = st.radio(
            "Sammenlign med:", ["Vinderhold", "Feltet (Gennemsnit)"], horizontal=True)
        valgt_metrik = st.radio(
            "Visning:", ["Total tid (per stint)", "Gennemsnit (per omgang)"], horizontal=True)

        if valgt_reference == "Vinderhold":
            titel_suffix = 'Vinder'
            if "Total" in valgt_metrik:
                plot_kolonne = 'Total_Tid_Tabt_Vinder (Sek)'
                y_label = 'Total sekunder'
            else:
                plot_kolonne = 'Tid_Tabt_vs_Vinder'
                y_label = 'Sekunder per omgang'
        else:
            titel_suffix = 'Feltet'
            if "Total" in valgt_metrik:
                plot_kolonne = 'Total_Tid_Tabt_Feltet (Sek)'
                y_label = 'Total sekunder'
            else:
                plot_kolonne = 'Tid_Tabt_vs_Feltet'
                y_label = 'Sekunder per omgang'

        fig_kører, ax_kører = plt.subplots(figsize=(6, 4))
        farver = ['#e74c3c' if x >
                  0 else '#2ecc71' for x in kører_data[plot_kolonne]]

        # Plot bruger nu Stint_Navn som x-akse, men er garanteret i kronologisk rækkefølge
        ax_kører.bar(kører_data['Stint_Navn'],
                     kører_data[plot_kolonne], color=farver)
        ax_kører.axhline(0, color='black', linewidth=1.5)
        ax_kører.set_title(
            f'Tid Tabt/Vundet vs. {titel_suffix}', fontweight='bold')
        ax_kører.set_ylabel(y_label)
        plt.xticks(rotation=45)
        st.pyplot(fig_kører)

    st.markdown("---")

    # --- NYT: DEN INTERNE DUEL (SALLIE'S VS OLD BOYS) ---
    st.subheader("⚔️ Den Interne Duel: Sallie's vs Old Boys")
    st.markdown("Sammenligning af gennemsnitstider per stint. *Negativ difference (Grøn) = Sallie's var hurtigst. Positiv (Rød) = Old Boys var hurtigst.*")

    sallies_team1 = stint_summary[stint_summary['Holdnavn_Fane'] == "Sallie's"]
    sallies_team2 = stint_summary[stint_summary['Holdnavn_Fane']
                                  == "Sallie's Old Boys"]

    if not sallies_team1.empty and not sallies_team2.empty:
        # Nu fletter vi KUN på vores bundsolide Stint_Kronologi
        st1_agg = sallies_team1.groupby(['Stint_Kronologi', 'Stint_Navn', 'Kører']).agg(
            Tid1=('Gns_Omgangstid', 'mean')).reset_index()
        st2_agg = sallies_team2.groupby(['Stint_Kronologi', 'Stint_Navn', 'Kører']).agg(
            Tid2=('Gns_Omgangstid', 'mean')).reset_index()

        comp_df = pd.merge(st1_agg, st2_agg, on=[
                           'Stint_Kronologi'], how='outer', suffixes=('_S', '_OB'))
        comp_df = comp_df.sort_values('Stint_Kronologi')

        display_comp = pd.DataFrame({
            'Løbs Stint Nr.': comp_df['Stint_Kronologi'],
            "Sallie's Kører": comp_df['Kører_S'].fillna("Ingen data") + " (" + comp_df['Stint_Navn_S'].fillna("") + ")",
            "Sallie's Tid": comp_df['Tid1'].round(3),
            "Old Boys Kører": comp_df['Kører_OB'].fillna("Ingen data") + " (" + comp_df['Stint_Navn_OB'].fillna("") + ")",
            "Old Boys Tid": comp_df['Tid2'].round(3),
            "Difference (Sallie's vs OB)": (comp_df['Tid1'] - comp_df['Tid2']).round(3)
        })

        # Ryd pænt op i parenteserne, hvis data mangler
        display_comp["Sallie's Kører"] = display_comp["Sallie's Kører"].str.replace(
            " ()", "", regex=False)
        display_comp["Old Boys Kører"] = display_comp["Old Boys Kører"].str.replace(
            " ()", "", regex=False)

        # Style funktionen lægger baggrundsfarver i Differencen
        def farv_difference(val):
            if pd.isna(val):
                return ''
            color = '#e74c3c' if val > 0 else '#2ecc71'
            return f'color: {color}; font-weight: bold;'

        st.dataframe(display_comp.style.map(farv_difference, subset=[
                     "Difference (Sallie's vs OB)"]), hide_index=True)
    else:
        st.write(
            "Kunne ikke finde nok data til begge hold for at lave sammenligningen.")

    st.markdown("---")

# --- GRAFIK ---
st.subheader("📈 Pace Udvikling Over Tid")
sns.set_theme(style="darkgrid")
pace_udvikling = rene_omgange.groupby(['Hold_Kategori', 'Holdnavn_Fane', 'Tids_Interval'])[
    'Omgangstid'].mean().reset_index()

fig, ax = plt.subplots(figsize=(16, 7))

for ark_navn in pace_udvikling[pace_udvikling['Hold_Kategori'] == 'Feltet']['Holdnavn_Fane'].unique():
    hold_data = pace_udvikling[pace_udvikling['Holdnavn_Fane'] == ark_navn]
    label = 'Andre Hold (Feltet)' if ark_navn == pace_udvikling[pace_udvikling['Hold_Kategori'] == 'Feltet']['Holdnavn_Fane'].unique()[
        0] else None
    ax.plot(hold_data['Tids_Interval'], hold_data['Omgangstid'],
            color='grey', alpha=0.3, linewidth=1.5, label=label)

vinder_data = pace_udvikling[pace_udvikling['Hold_Kategori'] == 'Vinderhold']
if not vinder_data.empty:
    ax.plot(vinder_data['Tids_Interval'], vinder_data['Omgangstid'], color='#e74c3c',
            linewidth=3, label=f'Vinder ({vinder_hold_navn})', marker='o', markersize=4)

sallies_ark = pace_udvikling[pace_udvikling['Hold_Kategori']
                             == 'Sallies']['Holdnavn_Fane'].unique()
farver = ['#3498db', '#9b59b6']
for i, ark_navn in enumerate(sallies_ark):
    sallies_data = pace_udvikling[pace_udvikling['Holdnavn_Fane'] == ark_navn]
    if not sallies_data.empty:
        ax.plot(sallies_data['Tids_Interval'], sallies_data['Omgangstid'], color=farver[i % len(
            farver)], linewidth=3, label=ark_navn, marker='o', markersize=4)

ax.set_title('Track Pace: Sallies vs Vinder vs Feltet',
             fontweight='bold', fontsize=16)
ax.set_xlabel('Timer Kørt', fontsize=12)
ax.set_ylabel('Gennemsnitlig Omgangstid i sekunder', fontsize=12)
ax.legend(fontsize=12, loc='upper right')
plt.tight_layout()

st.pyplot(fig)
