import streamlit as st
import datetime
import requests
from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo
import re
import os

# ==========================================
# SIVUN ASETUKSET
# ==========================================

st.set_page_config(page_title="🚕 TH Taktinen Tutka", page_icon="🚕", layout="wide")

# ==========================================
# KONFIGURAATIO & APUFUNKTIOT (Integroitu px.txt)
# ==========================================

APP_PASSWORD = st.secrets.get("APP_PASSWORD", "2026")
FINAVIA_API_KEY = st.secrets.get("FINAVIA_API_KEY", "c24ac18c01e44b6e9497a2a30341")
DIGITRAFFIC_API_KEY = st.secrets.get("DIGITRAFFIC_API_KEY", "")

def _get_json(url: str, params: dict = None, headers: dict = None, timeout: int = 8):
    """Yleinen apufunktio JSON-rajapintojen kutsumiseen turvallisesti."""
    try:
        r = requests.get(url, params=params or {}, headers=headers or {}, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        pass
    return None

# ==========================================
# 1. KIRJAUTUMINEN
# ==========================================

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<h1 style='text-align: center; color: #5bc0de;'>🚕 TH Taktinen Tutka</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #aaa;'>Kirjaudu sisään nähdäksesi datan.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pwd = st.text_input("Salasana", type="password")
        if st.button("Kirjaudu", use_container_width=True):
            if pwd == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Väärä salasana.")
                st.stop()

# ==========================================
# 2. TYYLIT JA KÄYTTÖLIITTYMÄ
# ==========================================

if "valittu_asema" not in st.session_state:
    st.session_state.valittu_asema = "Helsinki"
if "paiva_offset" not in st.session_state:
    st.session_state.paiva_offset = 0

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    main { background-color: #121212; }
    .header-container {
        display: flex; justify-content: space-between; align-items: flex-start;
        border-bottom: 1px solid #333; padding-bottom: 15px; margin-bottom: 20px;
    }
    .app-title { font-size: 32px; font-weight: bold; color: #ffffff; margin-bottom: 5px; }
    .time-display { font-size: 42px; font-weight: bold; color: #e0e0e0; line-height: 1.1; }
    .weather-box { background-color: #1e1e2a; padding: 10px 20px; border-radius: 8px; border: 1px solid #5bc0de; text-align: center;}
    .alert-box { background-color: #5a1a00; color: #ffeb3b; padding: 12px 20px; border-radius: 8px; border: 1px solid #ff6b35; margin-bottom: 20px; font-size: 18px;}
    .taksi-card {
        background-color: #1e1e2a; color: #e0e0e0; padding: 22px;
        border-radius: 12px; margin-bottom: 20px; font-size: 22px;
        border: 1px solid #3a3a50; box-shadow: 0 4px 8px rgba(0,0,0,0.3); line-height: 1.6;
    }
    .taksi-link { color: #5bc0de; text-decoration: none; font-size: 19px; display: inline-block; margin-top: 12px; font-weight: bold; }
    .badge-red { background: #7a1a1a; color: #ff9999; padding: 2px 8px; border-radius: 4px; font-size: 18px; }
    .badge-green { background: #1a4a1a; color: #88d888; padding: 2px 8px; border-radius: 4px; font-size: 18px; }
    .pax-good { color: #ffeb3b; font-weight: bold; }
    .pax-ok { color: #a3c2a3; }
    .section-header { color: #e0e0e0; font-size: 26px; font-weight: bold; margin-top: 28px; margin-bottom: 10px; border-left: 4px solid #5bc0de; padding-left: 12px; }
    .live-event { color: #88d888; font-weight: bold; font-size: 20px; }
    .no-event { color: #888888; font-style: italic; font-size: 18px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. UUDET TILA- JA SÄÄFUNKTIOT
# ==========================================

@st.cache_data(ttl=900, show_spinner=False)
def get_weather_helsinki():
    """Hakee Helsingin reaaliaikaisen sään (korvaa px.txt FMI-placeholderin)."""
    url = "https://api.open-meteo.com/v1/forecast?latitude=60.1695&longitude=24.9354&current=temperature_2m,precipitation,weather_code&timezone=Europe%2FHelsinki"
    data = _get_json(url)
    if data and "current" in data:
        c = data["current"]
        code = c.get("weather_code", 0)
        # Yksinkertainen ikonikartta
        if code in [0, 1, 2]: icon = "☀️"
        elif code in [3]: icon = "☁️"
        elif code in [51, 53, 55, 61, 63, 65, 80, 81, 82]: icon = "🌧️"
        elif code in [71, 73, 75, 85, 86]: icon = "❄️"
        else: icon = "🌫️"
        
        return {
            "temp": f"{c.get('temperature_2m')} °C",
            "precip": f"{c.get('precipitation')} mm",
            "icon": icon,
            "is_raining": c.get("precipitation", 0) > 0.5
        }
    return None

@st.cache_data(ttl=300, show_spinner=False)
def get_road_incidents_uusimaa():
    """Hakee käynnissä olevat tieliikennehäiriöt Pääkaupunkiseudulla."""
    url = "https://tie.digitraffic.fi/api/v3/data/traffic-messages/active?situationType=TRAFFIC_INCIDENT"
    headers = {"digitraffic-api-key": DIGITRAFFIC_API_KEY} if DIGITRAFFIC_API_KEY else {}
    data = _get_json(url, headers=headers)
    
    alerts = []
    if data and "features" in data:
        for f in data["features"]:
            props = f.get("properties", {})
            text_dump = str(props).lower()
            # Suodatetaan vain PK-seudun häiriöt
            if any(kw in text_dump for kw in ["helsinki", "espoo", "vantaa", "kehä", "kauniainen"]):
                announcements = props.get("announcements", [])
                if announcements:
                    title = announcements[0].get("title", "Liikennehäiriö")
                    alerts.append(title)
    return alerts[:3] # Palautetaan max 3 kriittisintä

# ==========================================
# 4. HAKUFUNKTIOT (Muokattu käyttämään _get_json)
# ==========================================

@st.cache_data(ttl=60, show_spinner=False)
def get_trains(asema_nimi: str):
    nykyhetki = datetime.datetime.now(ZoneInfo("Europe/Helsinki"))
    raja_2h = nykyhetki + datetime.timedelta(hours=2)
    koodi = {"Helsinki": "HKI", "Pasila": "PSL", "Tikkurila": "TKL"}.get(asema_nimi, "HKI")
    
    url = f"https://rata.digitraffic.fi/api/v1/live-trains/station/{koodi}?arriving_trains=40&include_nonstopping=false&train_categories=Long-distance"
    juna_data = _get_json(url)
    tulos = []
    
    if juna_data:
        for juna in juna_data:
            if juna.get("cancelled") or juna.get("trainCategory") != "Long-distance": 
                continue
            nimi = f"{juna.get('trainType', '')}{juna.get('trainNumber', '')}"
            lahto_koodi = next((rv["stationShortCode"] for rv in juna.get("timeTableRows", []) if rv["type"] == "DEPARTURE"), None)
            if not lahto_koodi or lahto_koodi in ["HKI", "PSL", "TKL"]: 
                continue
                
            for rivi in juna.get("timeTableRows", []):
                if rivi["stationShortCode"] == koodi and rivi["type"] == "ARRIVAL":
                    raaka = rivi.get("liveEstimateTime") or rivi.get("scheduledTime", "")
                    if raaka:
                        try:
                            aika_utc = datetime.datetime.strptime(raaka[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc)
                            aika_hki = aika_utc.astimezone(ZoneInfo("Europe/Helsinki"))
                            if (aika_hki >= nykyhetki - datetime.timedelta(minutes=5) and aika_hki <= raja_2h):
                                tulos.append({
                                    "train": nimi, "origin": lahto_koodi, # Oikaistu koodin nimeen selkeyden vuoksi
                                    "time": aika_hki.strftime("%H:%M"), "delay": rivi.get("differenceInMinutes", 0), "dt": aika_hki
                                })
                        except Exception: 
                            pass
                    break
    
    tulos.sort(key=lambda k: k["dt"])
    return tulos if tulos else [{"train": "--", "origin": "Ei kaukojunia seur. 2h", "time": "", "delay": 0}]

@st.cache_data(ttl=60, show_spinner=False)
def get_flights():
    laajarunko = ("359", "350", "333", "330", "340", "788", "789", "777", "77W", "380", "748")
    url = f"https://api.finavia.fi/flights/public/v0/flights/arr/HEL" # Päivitetty px.txt mukaiseksi
    headers = {"Ocp-Apim-Subscription-Key": FINAVIA_API_KEY}
    
    data = _get_json(url, headers=headers)
    if data:
        saapuvat = data.get("data", []) if isinstance(data, dict) else data
        tulos = []
        for lento in saapuvat:
            actype = str(lento.get("actype", "")).upper()
            status = str(lento.get("prt_f") or lento.get("flightStatusInfo", "")).upper()
            aika_r = str(lento.get("sdt", ""))
            wb = any(c in actype for c in laajarunko)
            if not wb and "DELAY" not in status: continue
                
            tulos.append({
                "flight": lento.get("fltnr", "??"), "origin": lento.get("route_n_1", "Tuntematon"),
                "time": aika_r[11:16] if "T" in aika_r else aika_r[:5],
                "type": f"Laajarunko ({actype})" if wb else f"Kapearunko ({actype})",
                "wb": wb, "status": status or "Odottaa"
            })
        tulos.sort(key=lambda x: (not x["wb"], x["time"]))
        return tulos[:8], None
    return [], "Finavia rajapinta ei vastaa."

# ==========================================
# 5. DASHBOARD KOMPONENTTI
# ==========================================

@st.fragment(run_every=300)
def render_dashboard():
    suomen_aika = datetime.datetime.now(ZoneInfo("Europe/Helsinki"))
    klo = suomen_aika.strftime("%H:%M")
    paiva = suomen_aika.strftime("%A %d.%m.%Y").capitalize()

    # --- YLÄPALKKI & SÄÄ ---
    saa = get_weather_helsinki()
    saa_html = ""
    if saa:
        saa_text_color = "#ffeb3b" if saa["is_raining"] else "#e0e0e0"
        saa_html = (f"<div class='weather-box'>"
                    f"<span style='font-size:32px;'>{saa['icon']}</span><br>"
                    f"<b style='font-size:24px; color:{saa_text_color};'>{saa['temp']}</b><br>"
                    f"<span style='font-size:16px; color:#aaa;'>Sade: {saa['precip']}</span>"
                    f"</div>")

    st.markdown(
        f"<div class='header-container'>"
        f"<div><div class='app-title'>🚕 TH Taktinen Tutka</div>"
        f"<div class='time-display'>{klo} <span style='font-size:16px;color:#888;'>{paiva}</span></div></div>"
        f"<div>{saa_html}</div>"
        f"</div>",
        unsafe_allow_html=True
    )
    
    # --- LIIKENNEHÄIRIÖT (Digitraffic tieliikenne) ---
    hairiot = get_road_incidents_uusimaa()
    if hairiot:
        alert_text = "<br>".join([f"⚠️ <b>{h}</b>" for h in hairiot])
        st.markdown(f"<div class='alert-box'>🚨 <b>AKTIIVISET LIIKENNEHÄIRIÖT PK-SEUTU:</b><br>{alert_text}</div>", unsafe_allow_html=True)
    elif saa and saa["is_raining"]:
        st.markdown(f"<div class='alert-box' style='background-color:#4a3a00;'>🌧️ <b>HUOMIO:</b> Sadesää nostaa taksikysyntää merkittävästi. Ajaudu keskustan solmukohtiin!</div>", unsafe_allow_html=True)

    if st.button("🔄 Pakota päivitys", type="secondary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # ---- JUNAT ----
    st.markdown("<div class='section-header'>🚆 SAAPUVAT KAUKOJUNAT – seuraavat 2h</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    if c1.button("Helsinki (HKI)", use_container_width=True): st.session_state.valittu_asema = "Helsinki"
    if c2.button("Pasila (PSL)", use_container_width=True): st.session_state.valittu_asema = "Pasila"
    if c3.button("Tikkurila (TKL)", use_container_width=True): st.session_state.valittu_asema = "Tikkurila"

    valittu = st.session_state.valittu_asema
    junat = get_trains(valittu)
    juna_html = f"<span style='color:#aaa; font-size:19px;'>Asema: <b>{valittu}</b></span><br><br>"

    for j in junat:
        viive_ui = (f"<span class='badge-red'>+{j['delay']} min</span>" if j['delay'] > 0 else "<span class='badge-green'>Ajassa</span>")
        juna_html += (f"<b style='font-size:24px;'>{j['time']}</b> "
                      f"<span style='font-size:22px;'>{j['train']}</span> "
                      f"<span style='color:#aaa; font-size:20px;'>({j['origin']})</span> "
                      f"{viive_ui}<br><br>")

    st.markdown(f"<div class='taksi-card'>{juna_html}</div>", unsafe_allow_html=True)

    # ---- LENNOT ----
    st.markdown("<div class='section-header'>✈️ LENTOASEMA (HEL) - Laajarungot & Myöhästyneet</div>", unsafe_allow_html=True)
    lennot, virhe = get_flights()
    lento_html = f"<span style='color:#ff9999; font-size:19px;'>{virhe}</span><br>" if virhe else ""
    for lento in lennot:
        pax_class = "pax-good" if lento["wb"] else "pax-ok"
        lento_html += (f"<b style='font-size:24px;'>{lento['time']}</b> "
                       f"<span style='font-size:21px;'>{lento['origin']}</span> "
                       f"<span style='color:#aaa; font-size:17px;'>({lento['status']})</span><br>"
                       f"<span class='{pax_class}' style='font-size:18px;'>└ {lento['type']}</span><br><br>")
    st.markdown(f"<div class='taksi-card'>{lento_html or 'Ei dataa'}</div>", unsafe_allow_html=True)

if st.session_state.authenticated:
    render_dashboard()

