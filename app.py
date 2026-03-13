@st.cache_data(ttl=600, show_spinner=False)
def get_averio_ships():
    """Palauttaa seuraavat 3 saapuvaa laivaa kellonajasta riippumatta."""
    nykyhetki = datetime.datetime.now(ZoneInfo("Europe/Helsinki"))
    laivat_kaikki = []
    try:
        r = requests.get("https://averio.fi/laivat/", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Käydään läpi HTML-taulukon rivit px.txt -tiedoston ohjeen mukaisesti
        for tr in soup.select("table tr"):
            tds = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if len(tds) >= 4:
                aika_str = tds[0]
                satama = tds[1]
                laiva = tds[2]
                pax_str = tds[3]
                
                # Ohitetaan otsikkorivit
                if "aika" in aika_str.lower() or "laiva" in laiva.lower() or "saapuu" in aika_str.lower():
                    continue
                    
                # Poimitaan vain kellonaika (esim. 18:00)
                m = re.search(r"(\d{1,2}:\d{2})", aika_str)
                if not m:
                    continue
                aika_puhdas = m.group(1)
                
                # Poimitaan matkustajien määrä numeerisena (poistaa välilyönnit yms)
                pax = None
                pax_digits = re.sub(r"[^\d]", "", pax_str)
                if pax_digits:
                    pax = int(pax_digits)
                
                # Muutetaan aika datetime-objektiksi vertailua varten
                dt_laiva = None
                try:
                    tunnit, minuutit = map(int, aika_puhdas.split(":"))
                    dt_laiva = nykyhetki.replace(hour=tunnit, minute=minuutit, second=0, microsecond=0)
                    
                    # Jos laivan aika on mennyt yli 30 min sitten, oletetaan sen olevan huomisen puolella
                    if dt_laiva < nykyhetki - datetime.timedelta(minutes=30):
                        dt_laiva += datetime.timedelta(days=1)  
                except Exception: 
                    pass
                
                # Yhtenäistetään satamien nimet nätimmiksi
                term = satama
                if "t2" in satama.lower() or "länsi" in satama.lower():
                    term = "Länsiterminaali T2"
                elif "katajanokka" in satama.lower():
                    term = "Katajanokan terminaali"
                elif "olympia" in satama.lower():
                    term = "Olympiaterminaali"

                laivat_kaikki.append({
                    "ship": laiva,
                    "terminal": term,
                    "time": aika_puhdas,
                    "pax": pax,
                    "dt": dt_laiva
                })

        # Järjestetään aikajärjestykseen ja otetaan 3 seuraavaa
        laivat_kaikki.sort(key=lambda x: x["dt"] if x["dt"] else datetime.datetime.max.replace(tzinfo=ZoneInfo("Europe/Helsinki")))
        return laivat_kaikki[:3]
    except Exception: 
        return []
