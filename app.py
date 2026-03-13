import streamlit as st
import datetime
import requests
from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo
import re

# ==========================================
# SIVUN ASETUKSET
# ==========================================

st.set_page_config(page_title="🚕 TH Taktinen Tutka", page_icon="🚕", layout="wide")

# ==========================================
# APUFUNKTIOT (Integroitu px.txt)
# ==========================================

def _get_json(url: str, params: dict = None, headers: dict = None, timeout: int = 8):
    """
    Yleinen apufunktio JSON-rajapintojen kutsumiseen turvallisesti (px.txt pohjalta).
    Käsittelee virheet niin, ettei sovellus kaadu API-katkoksiin.
    """
    try:
        r = requests.get(url, params=params or {}, headers=headers or {}, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

# ==========================================
# 1. KIRJAUTUMINEN
# ==========================================

APP_PASSWORD = st.secrets.get("APP_PASSWORD", "2026")

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
# 2. ALUSTUKSET JA TYYLIT
# ==========================================

FINAVIA_API_KEY = st.secrets.get("FINAVIA_API_KEY", "c24ac18c01e44b6e9497a2a30341")

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
    .taksi-card {
        background-color: #1e1e2a; color: #e0e0e0; padding: 22px;
        border-radius: 12px; margin-bottom: 20px; font-size: 22px;
        border: 1px solid #3a3a50; box-shadow: 0 4px 8px rgba(0,0,0,0.3); line-height: 1.6;
    }
    .card-title {
        font-size: 26px; font-weight: bold; margin-bottom: 12px;
        color: #ffffff; border-bottom: 2px solid #444; padding-bottom: 8px;
    }
    .taksi-link {
        color: #5bc0de; text-decoration: none; font-size: 19px;
        display: inline-block; margin-top: 12px; font-weight: bold;
    }
    .badge-red { background: #7a1a1a; color: #ff9999; padding: 2px 8px; border-radius: 4px; font-size: 18px; }
    .badge-green { background: #1a4a1a; color: #88d888; padding: 2px 8px; border-radius: 4px; font-size: 18px; }
    .badge-gold { background: #4a3a00; color: #ffd700; padding: 3px 10px; border-radius: 4px; font-size: 17px; font-weight: bold; }
    .badge-fire { background: #5a1a00; color: #ff6b35; padding: 3px 10px; border-radius: 4px; font-size: 17px; font-weight: bold; }
    .pax-good { color: #ffeb3b; font-weight: bold; }
    .pax-ok { color: #a3c2a3; }
    .section-header {
        color: #e0e0e0; font-size: 26px; font-weight: bold;
        margin-top: 28px; margin-bottom: 10px;
        border-left: 4px solid #5bc0de; padding-left: 12px;
    }
    .venue-name { color: #ffffff; font-weight: bold; font-size: 22px; }
    .venue-address { color: #aaaaaa; font-size: 18px; }
    .eventline { border-left: 3px solid #333; padding-left: 12px; margin-bottom: 20px; }
    .live-event { color: #88d888; font-weight: bold; font-size: 20px; }
    .no-event { color: #888888; font-style: italic; font-size: 18px; }

    /* Tapahtumakortit luokittelun mukaan */
    .ev-main { color: #f0f0f0; font-size: 21px; margin-bottom: 14px; line-height: 1.4; border-left: 3px solid #5bc0de; padding-left: 10px; }
    .ev-ballet { color: #d0c8ff; font-size: 20px; margin-bottom: 12px; line-height: 1.4; border-left: 3px solid #9b8fd4; padding-left: 10px; }
    .ev-family { color: #b0c8b0; font-size: 18px; margin-bottom: 10px; line-height: 1.3; border-left: 2px solid #607860; padding-left: 10px; }
    .ev-small { color: #999; font-size: 16px; margin-bottom: 8px; line-height: 1.2; border-left: 2px solid #444; padding-left: 8px; }
    .ev-venue-tag { color: #ffeb3b; font-weight: bold; font-size: 17px; }
    .ev-venue-small { color: #777; font-size: 15px; }
</style>
""", unsafe_allow_html=True)


def laske_kysyntakerroin(wb_status: bool, klo_str: str) -> str:
    indeksi = 2.0
    if wb_status: 
        indeksi += 5.0
    try:
        tunnit = int(klo_str.split(":")[0])
        if tunnit >= 22 or tunnit <= 4: 
            indeksi += 2.5
        elif 15 <= tunnit <= 18: 
            indeksi += 1.5
    except ValueError: 
        pass
    
    indeksi = min(indeksi, 10.0)
    
    if indeksi >= 7: 
        return f"<span style='color:#ff4b4b; font-weight:bold;'>Kysyntä: {indeksi}/10</span>"
    if indeksi >= 4: 
        return f"<span style='color:#ffeb3b;'>Kysyntä: {indeksi}/10</span>"
    return f"<span style='color:#a3c2a3;'>Kysyntä: {indeksi}/10</span>"

# ==========================================
# 4. HAKUFUNKTIOT
# ==========================================

@st.cache_data(ttl=86400, show_spinner=False)
def hae_juna_asemat():
    asemat = {"HKI": "Helsinki", "PSL": "Pasila", "TKL": "Tikkurila"}
    data = _get_json("https://rata.digitraffic.fi/api/v1/metadata/stations", timeout=5)
    if data:
        for s in data: 
            asemat[s["stationShortCode"]] = s["stationName"].replace(" asema", "")
    return asemat

@st.cache_data(ttl=60, show_spinner=False)
def get_trains(asema_nimi: str):
    """Palauttaa seuraavat kaukojunat - vain seuraavan 2 tunnin sisällä saapuvat."""
    nykyhetki = datetime.datetime.now(ZoneInfo("Europe/Helsinki"))
    raja_2h = nykyhetki + datetime.timedelta(hours=2)
    koodi = {"Helsinki": "HKI", "Pasila": "PSL", "Tikkurila": "TKL"}.get(asema_nimi, "HKI")
    asemat_dict = hae_juna_asemat()
    tulos = []
    
    url = f"https://rata.digitraffic.fi/api/v1/live-trains/station/{koodi}?arriving_trains=40&include_nonstopping=false&train_categories=Long-distance"
    data = _get_json(url, timeout=8)
    
    if data:
        for juna in data:
            if juna.get("cancelled") or juna.get("trainCategory") != "Long-distance": 
                continue
            nimi = f"{juna.get('trainType', '')}{juna.get('trainNumber', '')}"
            lahto_koodi = next(
                (rv["stationShortCode"] for rv in juna.get("timeTableRows", []) if rv["type"] == "DEPARTURE"),
                None
            )
            if not lahto_koodi or lahto_koodi in ["HKI", "PSL", "TKL"]: 
                continue
                
            for rivi in juna.get("timeTableRows", []):
                if rivi["stationShortCode"] == koodi and rivi["type"] == "ARRIVAL":
                    raaka = rivi.get("liveEstimateTime") or rivi.get("scheduledTime", "")
                    if raaka:
                        try:
                            aika_utc = datetime.datetime.strptime(raaka[:19], "%Y-%m-%dT%H:%M:%S").replace(
                                tzinfo=datetime.timezone.utc
                            )
                            aika_hki = aika_utc.astimezone(ZoneInfo("Europe/Helsinki"))
                            # Näytetään vain -5min -> +2h ikkuna
                            if (aika_hki >= nykyhetki - datetime.timedelta(minutes=5) and aika_hki <= raja_2h):
                                tulos.append({
                                    "train": nimi,
                                    "origin": asemat_dict.get(lahto_koodi, lahto_koodi),
                                    "time": aika_hki.strftime("%H:%M"),
                                    "delay": rivi.get("differenceInMinutes", 0),
                                    "dt": aika_hki
                                })
                        except Exception: 
                            pass
                    break
                    
        tulos.sort(key=lambda k: k["dt"])
        return tulos if tulos else [{"train": "--", "origin": "Ei kaukojunia seuraavan 2h aikana", "time": "", "delay": 0}]
    return [{"train": "API-virhe", "origin": "VR rajapinta ei vastaa", "time": "", "delay": 0}]

@st.cache_data(ttl=600, show_spinner=False)
def get_averio_ships():
    """Palauttaa seuraavat 3 saapuvaa laivaa kellonajasta riippumatta."""
    # Averio on HTML-sivu, käytetään suoraan requests & BeautifulSoup (kuten px.txt opasti HTML-sivuille)
    nykyhetki = datetime.datetime.now(ZoneInfo("Europe/Helsinki"))
    laivat_kaikki = []
    try:
        r = requests.get("https://averio.fi/laivat", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for taulu in soup.find_all("table"):
            for rivi in taulu.find_all("tr"):
                solut = [td.get_text(strip=True) for td in rivi.find_all(["td", "th"])]
                if len(solut) < 3: 
                    continue
                teksti = " ".join(solut).lower()
                if "alus" in teksti or "laiva" in teksti: 
                    continue
                
                pax = next(
                    (int(re.sub(r"[^\d]", "", s)) for s in solut
                     if re.sub(r"[^\d]", "", s).isdigit() and 50 < int(re.sub(r"[^\d]", "", s)) <= 9999),
                    None
                )
                nimi = max(
                    [s for s in solut if re.search(r"[A-Za-zÄÖÅäöå]{3,}", s)],
                    key=len, default="Tuntematon"
                )
                aika_str = ""
                for osa in solut:
                    m = re.search(r"(\d{1,2}:\d{2})", str(osa))
                    if m: 
                        aika_str = m.group(1)
                        break
                
                term = "Länsiterminaali T2" if ("t2" in teksti or "finlandia" in nimi.lower()) else "Olympia / Katajanokka"

                dt_laiva = None
                if aika_str:
                    try:
                        tunnit, minuutit = map(int, aika_str.split(":"))
                        dt_laiva = nykyhetki.replace(hour=tunnit, minute=minuutit, second=0, microsecond=0)
                        if dt_laiva < nykyhetki - datetime.timedelta(minutes=10):
                            dt_laiva += datetime.timedelta(days=1)  # Yön yli -saapuminen
                    except Exception: 
                        pass

                laivat_kaikki.append({"ship": nimi, "terminal": term, "time": aika_str, "pax": pax, "dt": dt_laiva})

        laivat_kaikki.sort(key=lambda x: x["dt"] if x["dt"] else datetime.datetime.max.replace(tzinfo=ZoneInfo("Europe/Helsinki")))
        return laivat_kaikki[:3]
    except Exception: 
        return []

@st.cache_data(ttl=60, show_spinner=False)
def get_flights():
    laajarunko = ("359", "350", "333", "330", "340", "788", "789", "777", "77W", "380", "748")
    url = f"https://apigw.finavia.fi/flights/public/v0/flights/arr/HEL?subscription-key={FINAVIA_API_KEY}"
    
    data = _get_json(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
    if data:
        saapuvat = data.get("data", []) if isinstance(data, dict) else data
        tulos = []
        for lento in saapuvat:
            actype = str(lento.get("actype", "")).upper()
            status = str(lento.get("prt_f") or lento.get("flightStatusInfo", "")).upper()
            aika_r = str(lento.get("sdt", ""))
            wb = any(c in actype for c in laajarunko)
            
            if not wb and "DELAY" not in status: 
                continue
                
            tulos.append({
                "flight": lento.get("fltnr", "??"),
                "origin": lento.get("route_n_1", "Tuntematon"),
                "time": aika_r[11:16] if "T" in aika_r else aika_r[:5],
                "type": f"Laajarunko ({actype})" if wb else f"Kapearunko ({actype})",
                "wb": wb,
                "status": status or "Odottaa"
            })
        tulos.sort(key=lambda x: (not x["wb"], x["time"]))
        return tulos[:8], None
    return [], "Finavian rajapinta ei juuri nyt vastaa."

def parse_hel_api_datetime(time_str):
    if not time_str: 
        return None
    try:
        dt_utc = datetime.datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        return dt_utc.astimezone(ZoneInfo("Europe/Helsinki"))
    except Exception: 
        return None

# ==========================================
# OOPPERAN/KULTTUURIN TAPAHTUMALUOKITUS
# ==========================================

def luokittele_kulttuuritapahtuma(nimi: str, loc_name: str) -> str:
    n = nimi.lower()
    l = loc_name.lower()
    pieni_keywords = ["pieni", "almin", "studio pasila", "lilla teatern", "camerata",
                      "sonore", "black box", "organo", "paavo", "klubi", "lämpiö",
                      "aula", "kahvila", "ravintola", "foajee", "parvi"]
    perhe_keywords = ["perhe", "lasten", "nukketeatteri", "satuja", "lapsille"]
    baletti_keywords = ["baletti", "ballet", "tanssi"]
    ooppera_keywords = ["ooppera", "opera"]

    if any(kw in n for kw in pieni_keywords) or any(kw in l for kw in pieni_keywords): return "ev-small"
    if any(kw in n for kw in perhe_keywords): return "ev-family"
    if any(kw in n for kw in baletti_keywords): return "ev-ballet"
    if any(kw in n for kw in ooppera_keywords): return "ev-main"
    return "ev-main"

@st.cache_data(ttl=3600, show_spinner=False)
def hae_tapahtumat_api(kohde: dict, pvm_iso: str) -> list:
    if "api_text" not in kohde: 
        return []
    
    dt = datetime.datetime.strptime(pvm_iso, "%Y-%m-%d")
    seuraava_paiva = (dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    params = {
        "text": kohde["api_text"],
        "start": f"{pvm_iso}T00:00:00Z",
        "end": f"{seuraava_paiva}T00:00:00Z",
        "include": "location",
        "language": "fi",
        "sort": "start_time"
    }
    
    data = _get_json("https://api.hel.fi/linkedevents/v1/event/", params=params, timeout=8)
    if data:
        tulos = []
        ajat_seen = set()
        for t in data.get("data", []):
            nimi = (t.get("name", {}) or {}).get("fi")
            if not nimi: 
                continue
            alku_dt = parse_hel_api_datetime(t.get("start_time"))
            loppu_dt = parse_hel_api_datetime(t.get("end_time"))
            if not alku_dt: 
                continue
            if alku_dt.strftime("%Y-%m-%d") != pvm_iso: 
                continue
            
            if loppu_dt:
                kesto_h = (loppu_dt - alku_dt).total_seconds() / 3600
                if kesto_h > 14: 
                    continue
                    
            alku_klo = alku_dt.strftime("%H:%M")
            loppu_klo = loppu_dt.strftime("%H:%M") if loppu_dt else ""
            if alku_klo == "00:00" and not loppu_klo: 
                continue

            loc = t.get("location", {})
            loc_name = loc.get("name", {}).get("fi", "").strip() if isinstance(loc, dict) else ""
            osoite = loc.get("street_address", {}).get("fi", "").strip() if isinstance(loc, dict) else ""
            loc_name_l = loc_name.lower()
            osoite_l = osoite.lower()

            if kohde["api_text"] == "ooppera":
                if not ("ooppera" in loc_name_l or "almin" in loc_name_l or "helsinginkatu" in osoite_l): continue
            elif kohde["api_text"] == "musiikkitalo":
                if "musiikkitalo" not in loc_name_l and "mannerheimintie 13" not in osoite_l: continue
            elif kohde["api_text"] == "kaupunginteatteri":
                if not any(kw in loc_name_l for kw in ["kaupunginteatteri", "arena", "pasila", "lilla teatern", "eläintarhan"]): continue

            osoite_str = f", {osoite}" if osoite else ""
            sali_info = f"{loc_name}{osoite_str}" if loc_name else "Osoite puuttuu"
            aika_naytto = f"{alku_klo}–{loppu_klo}" if loppu_klo else alku_klo
            avain = f"{nimi}-{alku_klo}-{loc_name}"
            
            if avain in ajat_seen: 
                continue
            ajat_seen.add(avain)

            css_class = luokittele_kulttuuritapahtuma(nimi, loc_name)

            if css_class == "ev-main":
                html_block = (f"<div class='ev-main'>► <b>Klo {aika_naytto}</b>: {nimi}<br>"
                              f"<span class='ev-venue-tag'>📍 {sali_info}</span></div>")
            elif css_class == "ev-ballet":
                html_block = (f"<div class='ev-ballet'>► <b>Klo {aika_naytto}</b>: {nimi}<br>"
                              f"<span class='ev-venue-tag' style='color:#c8b8ff;'>📍 {sali_info}</span></div>")
            elif css_class == "ev-family":
                html_block = (f"<div class='ev-family'>▷ Klo {aika_naytto}: {nimi}<br>"
                              f"<span class='ev-venue-small'>📍 <i>{sali_info}</i></span></div>")
            else:
                html_block = (f"<div class='ev-small'>▷ Klo {aika_naytto}: {nimi}<br>"
                              f"<span class='ev-venue-small'>📍 <i>{sali_info}</i></span></div>")
            
            priority = {"ev-main": 0, "ev-ballet": 1, "ev-family": 2, "ev-small": 3}.get(css_class, 4)
            tulos.append((priority, html_block))

        tulos.sort(key=lambda x: x[0])
        return [html for _, html in tulos]
    return []

def yhdista_kulttuuridata(paikat, pvm_iso: str):
    for p in paikat:
        tapahtumat = hae_tapahtumat_api(p, pvm_iso)
        if tapahtumat:
            p["lopetus_html"] = (
                f"<div style='margin-top:10px;'>"
                f"<span class='live-event'>ESITYKSET TÄNÄÄN:</span><br>"
                f"{''.join(tapahtumat)}"
                f"</div>"
            )
        else:
            p["lopetus_html"] = (
                f"<span class='no-event'>Ei havaittuja esityksiä API:ssa.</span><br>"
                f"<span style='color:#777; font-size:16px;'>ℹ️ {p.get('huomio','')}</span>"
            )
    return paikat

# ==========================================
# JOKERIT - Scraper jokerit.fi/ottelut
# ==========================================

@st.cache_data(ttl=1800, show_spinner=False)
def hae_jokerit_ottelut(pvm_iso: str) -> list:
    # HTML scraping, ei JSON-API - siksi requests suoraan
    pelit = []
    dt = datetime.datetime.strptime(pvm_iso, "%Y-%m-%d")
    
    paiva_formaatit = [
        dt.strftime("%-d.%-m.%Y"), dt.strftime("%d.%m.%Y"), dt.strftime("%-d.%-m"),
        dt.strftime("%d.%m"), dt.strftime("%Y-%m-%d"),
    ]
    
    tunnetut_veniat = {
        "nordis": ("Nordis (Helsingin Jäähalli)", "Nordis"),
        "jäähalli": ("Nordis (Helsingin Jäähalli)", "Nordis"),
        "hartwall": ("Veikkaus Arena", "Veikkaus Arena"),
        "veikkaus": ("Veikkaus Arena", "Veikkaus Arena"),
        "kerava": ("Kerava Arena", "Kerava Arena"),
    }

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get("https://jokerit.fi/ottelut", headers=headers, timeout=12)
        if r.status_code != 200:
            return []
        
        soup = BeautifulSoup(r.text, "html.parser")
        for elem in soup.find_all(["tr", "div", "li", "article"]):
            elem_text = elem.get_text(separator=" ", strip=True)
            if not any(pf in elem_text for pf in paiva_formaatit): continue
            
            time_m = re.search(r'\b([01]?\d|2[0-3]):[0-5]\d\b', elem_text)
            if not time_m: continue
            aika = time_m.group(0)

            team_m = re.search(r'(Jokerit|[A-ZÄÖÅ][a-zäöå\-\.]{2,}(?:\s[A-ZÄÖÅ][a-zäöå]{1,})?)\s*[-–vs]+\s*([A-ZÄÖÅ][a-zäöå\-\.]{2,}(?:\s[A-ZÄÖÅ][a-zäöå]{1,})?)', elem_text)
            koti = team_m.group(1).strip() if team_m else "Jokerit"
            vieras = team_m.group(2).strip() if team_m else "?"

            venue_label = "Veikkaus Arena"
            venue_short = "Veikkaus Arena"
            for kw, (lbl, short) in tunnetut_veniat.items():
                if kw in elem_text.lower():
                    venue_label = lbl
                    venue_short = short
                    break

            tournament = ""
            for kw in ["playoff", "pudotus", "cup", "liiga", "mestis", "champions", "mm"]:
                if kw in elem_text.lower():
                    tournament = kw
                    break

            avain = f"{aika}-{koti}-{vieras}"
            if avain not in [f"{p['aika']}-{p['koti']}-{p['vieras']}" for p in pelit]:
                pelit.append({"aika": aika, "koti": koti, "vieras": vieras, "venue": venue_label, "venue_short": venue_short, "tournament": tournament})
        return pelit
    except Exception:
        return []

# ==========================================
# ERIKOISOTTELUN TUNNISTUS & LIIGA
# ==========================================

def tunnista_erikoispeli(koti: str, vieras: str, tournament: str = "") -> list:
    tags = []
    kl, vl, tl = koti.lower(), vieras.lower(), tournament.lower()
    helsinki_osumia = sum(1 for j in ["hifk", "jokerit", "kiekko-espoo", "blues", "kiekko-vantaa"] if j in kl or j in vl)
    
    if helsinki_osumia >= 2: tags.append("<span class='badge-fire'>🔥 PAIKALLISPELI</span>")
    if any(kw in tl for kw in ["playoff", "pudotus"]): tags.append("<span class='badge-gold'>🏆 PLAYOFFS</span>")
    elif any(kw in tl for kw in ["cup", "kansallinen"]): tags.append("<span class='badge-gold'>🥇 CUP</span>")
    elif any(kw in tl for kw in ["champions"]): tags.append("<span class='badge-gold'>⭐ CHAMPIONS LEAGUE</span>")
    elif any(kw in tl for kw in ["mm", "world"]): tags.append("<span class='badge-gold'>🌍 MM-OTTELU</span>")
    return tags

@st.cache_data(ttl=3600, show_spinner=False)
def hae_liiga_pvm(pvm_iso: str):
    dt_obj = datetime.datetime.strptime(pvm_iso, "%Y-%m-%d")
    kausi_alku = dt_obj.year if dt_obj.month > 7 else dt_obj.year - 1
    pelit = []
    
    for tournament in ["runkosarja", "playoffs"]:
        url = f"https://liiga.fi/api/v2/games?tournament={tournament}&season={kausi_alku}"
        data = _get_json(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if data:
            for p in data:
                if p.get("start", "").startswith(pvm_iso):
                    koti = (p.get("homeTeam") or {}).get("teamName", "")
                    vieras = (p.get("awayTeam") or {}).get("teamName", "")
                    aika = p.get("start", "")[11:16] if len(p.get("start", "")) >= 16 else "??:??"
                    pelit.append({"koti": koti, "vieras": vieras, "aika": aika, "tournament": tournament})
    return pelit

def yhdista_urheiludata(paikat, pvm_iso: str):
    liiga_pelit = hae_liiga_pvm(pvm_iso)
    jokerit_pelit = hae_jokerit_ottelut(pvm_iso)

    for p in paikat:
        nimi_lower = p.get("nimi", "").lower()
        tapahtumat_html = []

        if "hifk" in nimi_lower:
            omat = [g for g in liiga_pelit if "hifk" in g["koti"].lower()]
            for peli in omat:
                tags = tunnista_erikoispeli(peli["koti"], peli["vieras"], peli.get("tournament", ""))
                tag_str = " ".join(tags)
                tapahtumat_html.append(
                    f"<div style='color:#d0d0d0; font-size:21px; margin-bottom:8px;'>"
                    f"► <b>Klo {peli['aika']}</b>: {peli['koti']} – {peli['vieras']}"
                    f"{'<br>' + tag_str if tag_str else ''}</div>"
                )
            if tapahtumat_html:
                p["lopetus_html"] = (f"<div style='margin-top:10px;'><span class='live-event'>KOTIOTTELU TÄNÄÄN – Nordis:</span><br>"
                                     f"{''.join(tapahtumat_html)}<span style='color:#ccc;font-size:17px;display:block;margin-top:4px;'>"
                                     f"ℹ️ Yleisö purkautuu n. 2,5h aloituksesta.</span></div>")
            else: p["lopetus_html"] = "<span class='no-event'>Ei Liiga-kotiottelua tänään.</span>"

        elif "espoo" in nimi_lower:
            omat = [g for g in liiga_pelit if "espoo" in g["koti"].lower()]
            for peli in omat:
                tags = tunnista_erikoispeli(peli["koti"], peli["vieras"], peli.get("tournament", ""))
                tag_str = " ".join(tags)
                tapahtumat_html.append(
                    f"<div style='color:#d0d0d0; font-size:21px; margin-bottom:8px;'>"
                    f"► <b>Klo {peli['aika']}</b>: {peli['koti']} – {peli['vieras']}"
                    f"{'<br>' + tag_str if tag_str else ''}</div>"
                )
            if tapahtumat_html:
                p["lopetus_html"] = (f"<div style='margin-top:10px;'><span class='live-event'>KOTIOTTELU TÄNÄÄN – Metro Areena:</span><br>"
                                     f"{''.join(tapahtumat_html)}<span style='color:#ccc;font-size:17px;display:block;margin-top:4px;'>"
                                     f"ℹ️ Yleisö purkautuu n. 2,5h aloituksesta.</span></div>")
            else: p["lopetus_html"] = "<span class='no-event'>Ei Liiga-kotiottelua tänään.</span>"

        elif "jokerit" in nimi_lower or "veikkaus" in nimi_lower or "nordis" in nimi_lower:
            if jokerit_pelit:
                for peli in jokerit_pelit:
                    tags = tunnista_erikoispeli(peli["koti"], peli["vieras"], peli.get("tournament", ""))
                    if "hifk" in peli.get("vieras", "").lower() or "hifk" in peli.get("koti", "").lower():
                        if "<span class='badge-fire'>" not in " ".join(tags):
                            tags.insert(0, "<span class='badge-fire'>🔥 HELSINKI-DERBY</span>")
                    tag_str = " ".join(tags)
                    venue_badge = f"<span style='color:#aaddff; font-size:17px;'>🏟️ {peli.get('venue_short','')}</span>"
                    tapahtumat_html.append(
                        f"<div style='color:#d0d0d0; font-size:21px; margin-bottom:8px;'>"
                        f"► <b>Klo {peli['aika']}</b>: {peli['koti']} – {peli['vieras']}<br>{venue_badge}"
                        f"{'<br>' + tag_str if tag_str else ''}</div>"
                    )
                p["lopetus_html"] = (f"<div style='margin-top:10px;'><span class='live-event'>KOTIOTTELU TÄNÄÄN – Jokerit:</span><br>"
                                     f"{''.join(tapahtumat_html)}<span style='color:#ccc;font-size:17px;display:block;margin-top:4px;'>"
                                     f"ℹ️ Yleisö purkautuu n. 2,5h aloituksesta.</span></div>")
            else:
                p["lopetus_html"] = (f"<span class='no-event'>Ei Jokereiden ottelua tänään (tai scraper ei löytänyt).</span><br>"
                                     f"<a href='https://jokerit.fi/ottelut' target='_blank' class='taksi-link' style='font-size:17px;'>"
                                     f"Tarkista jokerit.fi →</a>")
    return paikat

def venue_html(paikat):
    html = ""
    for p in paikat:
        html += (f"<div class='eventline'><span class='venue-name'>{p.get('nimi','')}</span><br>"
                 f"<span class='venue-address'>Kapasiteetti: <b>{p.get('kap','')}</b></span><br>"
                 f"{p.get('lopetus_html', '')}<br>")
        if "linkki" in p:
            html += f"<a href='{p['linkki']}' class='taksi-link' target='_blank' style='font-size:16px;'>Viralliset sivut & Liput →</a>"
        html += "</div>"
    return html

# ==========================================
# 5. DASHBOARD
# ==========================================

@st.fragment(run_every=300)
def render_dashboard():
    suomen_aika = datetime.datetime.now(ZoneInfo("Europe/Helsinki"))
    klo = suomen_aika.strftime("%H:%M")
    paiva = suomen_aika.strftime("%A %d.%m.%Y").capitalize()

    st.markdown(
        f"<div class='header-container'>"
        f"<div><div class='app-title'>🚕 TH Taktinen Tutka</div>"
        f"<div class='time-display'>{klo} <span style='font-size:16px;color:#888;'>{paiva}</span></div></div>"
        f"<div style='text-align:right;'>"
        f"<a href='https://www.ilmatieteenlaitos.fi/sade-ja-pilvialueet?area=etela-suomi' class='taksi-link' target='_blank'>Säätutka</a>"
        f" | <a href='https://liikennetilanne.fintraffic.fi/' class='taksi-link' target='_blank'>Liikenne</a></div></div>",
        unsafe_allow_html=True
    )

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

    if junat and junat[0].get("train") not in ("API-virhe", "--"):
        for j in junat:
            merkki = "❄️ " if j["origin"] in ["Rovaniemi", "Kolari", "Kemi", "Oulu", "Kajaani"] else ""
            viive_ui = (f"<span class='badge-red'>+{j['delay']} min</span>"
                        if j['delay'] > 0 else "<span class='badge-green'>Ajassa</span>")
            juna_html += (
                f"<b style='font-size:24px;'>{j['time']}</b> "
                f"<span style='font-size:22px;'>{j['train']}</span> "
                f"<span style='color:#aaa; font-size:20px;'>({merkki}{j['origin']})</span> "
                f"{viive_ui}<br><br>"
            )
    else:
        juna_html += f"<span style='color:#888; font-size:20px;'>{junat[0].get('origin','Ei dataa')}</span>"

    st.markdown(f"<div class='taksi-card'>{juna_html}</div>", unsafe_allow_html=True)

    # ---- LAIVAT + LENNOT ----
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("<div class='section-header'>⛴️ LAIVAT – seuraavat 3</div>", unsafe_allow_html=True)
        averio_ships = get_averio_ships()
        averio_html = ""
        for laiva in averio_ships:
            pax = laiva.get("pax")
            pax_txt = f"{pax} matkustajaa" if pax else "Ei tietoa"
            css_class = "pax-good" if pax and pax > 1500 else "pax-ok"
            averio_html += (
                f"<b style='font-size:24px;'>{laiva['time']}</b> "
                f"<span style='font-size:21px;'>{laiva['ship']}</span><br>"
                f"<span style='font-size:18px; color:#aaa;'>└ {laiva['terminal']}</span> – "
                f"<span class='{css_class}' style='font-size:18px;'>{pax_txt}</span><br><br>"
            )
        st.markdown(
            f"<div class='taksi-card'>{averio_html or 'Ei dataa'}"
            f"<a href='https://averio.fi/laivat' target='_blank' class='taksi-link'>Lähde: Averio →</a></div>",
            unsafe_allow_html=True
        )

    with col_b:
        st.markdown("<div class='section-header'>✈️ LENTOASEMA (HEL)</div>", unsafe_allow_html=True)
        lennot, virhe = get_flights()
        lento_html = f"<span style='color:#ff9999; font-size:19px;'>{virhe}</span><br>" if virhe else ""
        for lento in lennot:
            pax_class = "pax-good" if lento["wb"] else "pax-ok"
            lento_html += (
                f"<b style='font-size:24px;'>{lento['time']}</b> "
                f"<span style='font-size:21px;'>{lento['origin']}</span> "
                f"<span style='color:#aaa; font-size:17px;'>({lento['status']})</span><br>"
                f"<span class='{pax_class}' style='font-size:18px;'>└ {lento['type']}</span>"
                f" – {laske_kysyntakerroin(lento['wb'], lento['time'])}<br><br>"
            )
        st.markdown(
            f"<div class='taksi-card'>{lento_html or 'Ei dataa'}"
            f"<a href='https://www.finavia.fi/fi/lentoasemat/helsinki-vantaa/lennot/saapuvat'"
            f" target='_blank' class='taksi-link'>Finavia Live →</a></div>",
            unsafe_allow_html=True
        )

    # ---- TAPAHTUMAT ----
    st.markdown("<div class='section-header'>🎭 TAPAHTUMAT & KAPASITEETTI</div>", unsafe_allow_html=True)
    col_p1, col_p2, col_p3 = st.columns([1, 1, 4])
    if col_p1.button("Tänään", use_container_width=True, type="primary" if st.session_state.paiva_offset == 0 else "secondary"):
        st.session_state.paiva_offset = 0
        st.rerun()
    if col_p2.button("Huomenna", use_container_width=True, type="primary" if st.session_state.paiva_offset == 1 else "secondary"):
        st.session_state.paiva_offset = 1
        st.rerun()

    kohde_dt = suomen_aika + datetime.timedelta(days=st.session_state.paiva_offset)
    pvm_iso = kohde_dt.strftime("%Y-%m-%d")
    st.markdown(
        f"<p style='color:#8ab4f8; font-weight:bold; font-size:19px;'>"
        f"Näytetään tapahtumat: {kohde_dt.strftime('%A %d.%m.%Y').capitalize()}</p>",
        unsafe_allow_html=True
    )

    tab1, tab2, tab3 = st.tabs(["🎭 Kulttuuri (API)", "🏒 Urheilu (Liiga + Jokerit)", "🎪 Messut & Musiikki"])

    with tab1:
        kulttuuri = [
            {"nimi": "Helsingin Kaupunginteatteri (HKT)", "kap": "Suuri: ~900 hlö",
             "api_text": "kaupunginteatteri", "huomio": "Yleensä ti–su klo 19",
             "linkki": "https://hkt.fi/kalenteri/"},
            {"nimi": "Kansallisooppera ja baletti", "kap": "Suuri: ~1 300 hlö",
             "api_text": "ooppera", "huomio": "Yleensä ohjelmaa klo 19",
             "linkki": "https://oopperabaletti.fi/ohjelmisto-ja-liput/"},
            {"nimi": "Musiikkitalo", "kap": "Suuri: 1 704 hlö",
             "api_text": "musiikkitalo", "huomio": "Konsertit usein klo 19",
             "linkki": "https://musiikkitalo.fi/tapahtumakalenteri/"},
        ]
        st.markdown(
            f"<div class='taksi-card'>{venue_html(yhdista_kulttuuridata(kulttuuri, pvm_iso))}</div>",
            unsafe_allow_html=True
        )

    with tab2:
        urheilu = [
            {"nimi": "HIFK – Nordis (Helsingin Jäähalli)", "kap": "8 200 hlö", "linkki": "https://hifk.fi/"},
            {"nimi": "Kiekko-Espoo – Metro Areena", "kap": "8 500 hlö", "linkki": "https://kiekko-espoo.com/"},
            {"nimi": "Jokerit – Veikkaus Arena / Nordis / Kerava", "kap": "2 000–13 500 hlö", "linkki": "https://jokerit.fi/ottelut"},
        ]
        st.markdown(
            f"<div class='taksi-card'>{venue_html(yhdista_urheiludata(urheilu, pvm_iso))}</div>",
            unsafe_allow_html=True
        )

    with tab3:
        messut = [
            {"nimi": "Messukeskus", "kap": "Jopa 50 000 hlö",
             "lopetus_html": "<span style='color:#d0d0d0; font-size:20px;'>Poistumapiikki tyypillisesti klo 16–18. Tarkista erikoistapahtumat.</span>",
             "linkki": "https://messukeskus.com/tapahtumakalenteri/"},
            {"nimi": "Tavastia & Kaapelitehdas", "kap": "900–3 000 hlö",
             "lopetus_html": "<span style='color:#d0d0d0; font-size:20px;'>Musiikkikeikat loppuvat yleensä klo 23:00–23:30. Katso sivut.</span>",
             "linkki": "https://tavastiaklubi.fi/"},
            {"nimi": "Olympic Stadium / Suurkonsertit", "kap": "~40 000 hlö",
             "lopetus_html": "<span style='color:#ffeb3b; font-size:20px; font-weight:bold;'>⭐ Tarkista tulevat stadionkonsertit! Poistumapiikki heti keikan jälkeen.</span>",
             "linkki": "https://olympiastadion.fi/tapahtumat/"},
        ]
        st.markdown(
            f"<div class='taksi-card'>{venue_html(messut)}</div>",
            unsafe_allow_html=True
        )

if st.session_state.authenticated:
    render_dashboard()

