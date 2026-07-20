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

# --- INDLÆS DATA (Klar til Cloud og Lokalt) ---
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
    alle_omgange, stint_navne, kører_navne = [], [], []
    hold_pit_tider = []

    er_sallies = 'sallie' in ark_navn.lower()

    for kol in kolonner:
        # Ignorer metadata kolonner
        kol_navn_ren = str(kol).strip().lower()
        if kol_navn_ren == 'stint' or kol_navn_ren == 'stint:' or kol_navn_ren.startswith('omga'):
            continue

        # Pit-analyse (første række)
        if len(df_ark[kol]) > 0:
            forste_tid = pd.to_numeric(df_ark[kol].iloc[0], errors='coerce')
            if pd.notna(forste_tid) and forste_tid > 150:
                hold_pit_tider.append(forste_tid)

        # Track Pace analyse
        stint_data = pd.to_numeric(
            df_ark[kol], errors='coerce').dropna().tolist()
        if len(stint_data) > 0:
            alle_omgange.extend(stint_data)
            stint_navne.extend([kol] * len(stint_data))

            if er_sallies:
                kører = str(kol).split(' ')[0].strip()
            else:
                kører = ark_navn
            kører_navne.extend([kører] * len(stint_data))

    if hold_pit_tider:
        gns_pit = sum(hold_pit_tider) / len(hold_pit_tider)
        pit_data_liste.append({
            'Hold': ark_navn,
            'Gns Pit Tid (Sek)': round(gns_pit, 2),
            'Antal Pitstops': len(hold_pit_tider)
        })

    if len(alle_omgange) > 0:
        hold_df = pd.DataFrame(
            {'Omgangstid': alle_omgange, 'Stint_Navn': stint_navne, 'Kører': kører_navne})
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
    st.dataframe(pit_df, width='stretch')

sallies_kun = rene_omgange[rene_omgange['Hold_Kategori'] == 'Sallies']

if not sallies_kun.empty:
    driver_summary = sallies_kun.groupby(['Holdnavn_Fane', 'Kører']).agg(
        Gns_Omgangstid=('Omgangstid', 'mean'),
        Tid_Tabt_vs_Vinder=('Delta_vs_Vinder', 'mean'),
        Tid_Tabt_vs_Feltet=('Delta_vs_Feltet', 'mean'),
        Omgange=('Omgangstid', 'count')
    ).reset_index().dropna()

    driver_summary['Total_Tid_Tabt_Vinder (Sek)'] = driver_summary['Tid_Tabt_vs_Vinder'] * \
        driver_summary['Omgange']
    driver_summary['Total_Tid_Tabt_Feltet (Sek)'] = driver_summary['Tid_Tabt_vs_Feltet'] * \
        driver_summary['Omgange']
    driver_summary = driver_summary.sort_values(
        by=['Holdnavn_Fane', 'Total_Tid_Tabt_Vinder (Sek)'])

    stint_summary = sallies_kun.groupby(['Holdnavn_Fane', 'Kører', 'Stint_Navn']).agg(
        Gns_Omgangstid=('Omgangstid', 'mean'),
        Tid_Tabt_vs_Vinder=('Delta_vs_Vinder', 'mean'),
        Tid_Tabt_vs_Feltet=('Delta_vs_Feltet', 'mean'),
        Omgange=('Omgangstid', 'count')
    ).reset_index().dropna()

    stint_summary['Total_Tid_Tabt_Vinder (Sek)'] = stint_summary['Tid_Tabt_vs_Vinder'] * \
        stint_summary['Omgange']
    stint_summary['Total_Tid_Tabt_Feltet (Sek)'] = stint_summary['Tid_Tabt_vs_Feltet'] * \
        stint_summary['Omgange']
    stint_summary = stint_summary.sort_values(
        by=['Holdnavn_Fane', 'Stint_Navn'])

    with col2:
        st.subheader("🏎️ Kører Opsummering")
        st.markdown(
            "*Positivt tal = Langsommere (tabt tid). Negativt tal = Hurtigere (vundet tid).*")
        st.dataframe(driver_summary, width='stretch')

    st.markdown("---")

    # --- KØRER DEEP-DIVE ---
    st.subheader("👤 Kører Deep-Dive")
    st.markdown(
        "Vælg en specifik kører for at isolere alle vedkommendes stints.")

    unikke_kørere = sorted(sallies_kun['Kører'].unique())
    valgt_kører = st.selectbox("Vælg Kører:", unikke_kørere)
    kører_data = stint_summary[stint_summary['Kører'] == valgt_kører]

    col_table, col_chart = st.columns([1.5, 1])

    with col_table:
        st.dataframe(kører_data.drop(
            columns=['Holdnavn_Fane', 'Kører']), width='stretch')

    with col_chart:
        # NYT: Knapper til at skifte grafens indhold
        valgt_reference = st.radio(
            "Sammenlign med:", ["Vinderhold", "Feltet (Gennemsnit)"], horizontal=True)

        if valgt_reference == "Vinderhold":
            plot_kolonne = 'Total_Tid_Tabt_Vinder (Sek)'
            titel_suffix = 'Vinder'
        else:
            plot_kolonne = 'Total_Tid_Tabt_Feltet (Sek)'
            titel_suffix = 'Feltet'

        fig_kører, ax_kører = plt.subplots(figsize=(6, 4))
        farver = ['#e74c3c' if x >
                  0 else '#2ecc71' for x in kører_data[plot_kolonne]]
        ax_kører.bar(kører_data['Stint_Navn'],
                     kører_data[plot_kolonne], color=farver)
        ax_kører.axhline(0, color='black', linewidth=1.5)
        ax_kører.set_title(
            f'Samlet Tid Tabt/Vundet vs. {titel_suffix}', fontweight='bold')
        ax_kører.set_ylabel('Total sekunder')
        plt.xticks(rotation=45)
        st.pyplot(fig_kører)

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
