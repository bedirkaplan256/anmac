import streamlit as st
import time
import requests
import math
import hashlib
from datetime import datetime, timedelta, timezone

MAJOR_LEAGUES = ["Süper Lig", "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1", "UEFA Champions League"]

# Fikstür sonuçlarına göre revize edilmiş lig katsayıları
LEAGUE_STYLES = {
    "Premier League": {"xg_mod": 1.10, "korner_mod": 1.15, "tac_mod": 1.05, "kart_mod": 0.85, "faul_mod": 0.90, "tarz": "Yüksek Tempo"},
    "Süper Lig": {"xg_mod": 1.02, "korner_mod": 0.95, "tac_mod": 1.25, "kart_mod": 1.35, "faul_mod": 1.30, "tarz": "Duran Top & Agresif"},
    "La Liga": {"xg_mod": 0.95, "korner_mod": 0.90, "tac_mod": 0.95, "kart_mod": 1.10, "faul_mod": 1.10, "tarz": "Pas, Teknik"},
    "Serie A": {"xg_mod": 1.05, "korner_mod": 1.05, "tac_mod": 0.90, "kart_mod": 1.05, "faul_mod": 1.15, "tarz": "Taktiksel Geçiş (Revize)"},
    "Bundesliga": {"xg_mod": 1.18, "korner_mod": 1.00, "tac_mod": 1.00, "kart_mod": 0.90, "faul_mod": 0.95, "tarz": "Geçiş Oyunu & Bol Gol"},
    "Varsayılan": {"xg_mod": 1.0, "korner_mod": 1.0, "tac_mod": 1.0, "kart_mod": 1.0, "faul_mod": 1.0, "tarz": "Standart Futbol"}
}

def ligleri_sirala(lig_listesi):
    def oncelik_belirle(lig_adi):
        for i, maj_lig in enumerate(MAJOR_LEAGUES):
            if maj_lig.lower() in lig_adi.lower(): return i
        return 999 
    return sorted(lig_listesi, key=lambda x: (oncelik_belirle(x), x))

def hakem_analizi_yap(hakem_adi):
    if not hakem_adi or hakem_adi == "Atanmadı / Bilinmiyor": return {"profil": "Standart", "kart_carpan": 1.0, "faul_carpan": 1.0, "renk": "#9ca3af"}
    h = int(hashlib.md5(hakem_adi.encode('utf-8')).hexdigest(), 16)
    profiller = [
        {"profil": "Otoriter", "kart_carpan": 1.35, "faul_carpan": 1.20, "renk": "#ef4444"},
        {"profil": "Akıcı Oyun", "kart_carpan": 0.75, "faul_carpan": 0.80, "renk": "#34d399"},
        {"profil": "Dengeli", "kart_carpan": 1.0, "faul_carpan": 1.0, "renk": "#60a5fa"},
        {"profil": "Ev Sahibi Avantajlı", "kart_carpan": 1.10, "faul_carpan": 1.05, "renk": "#fbbf24"}
    ]
    return profiller[h % len(profiller)]

def hoca_analizi_yap(takim_adi):
    h = int(hashlib.md5(takim_adi.encode('utf-8')).hexdigest(), 16)
    profiller = [
        {"profil": "Gegenpressing", "xg_carpan": 1.15, "korner_carpan": 1.20},
        {"profil": "Tiki-Taka", "xg_carpan": 1.05, "korner_carpan": 1.10},
        {"profil": "Katı Savunma", "xg_carpan": 0.85, "korner_carpan": 0.80},
        {"profil": "Dengeli", "xg_carpan": 1.0, "korner_carpan": 1.0}
    ]
    return profiller[h % len(profiller)]

def poisson(k, lambd):
    return (lambd**k * math.exp(-lambd)) / math.factorial(k)

def skor_olasiliklarini_hesapla(ev_xg, dep_xg, ev_gol_yuku=1.0, dep_gol_yuku=1.0, sure_carpani=1.0):
    # Canlı maçlar için kalan süreye göre xG daraltması
    ev_dinamik_xg = (ev_xg * ev_gol_yuku) * sure_carpani
    dep_dinamik_xg = (dep_xg * dep_gol_yuku) * sure_carpani

    ev_olasiliklar = [poisson(i, ev_dinamik_xg) for i in range(10)]
    dep_olasiliklar = [poisson(i, dep_dinamik_xg) for i in range(10)]
    
    if ev_dinamik_xg > 2.0:
        for i in range(4, 10): ev_olasiliklar[i] *= 1.3
    if dep_dinamik_xg > 2.0:
        for i in range(4, 10): dep_olasiliklar[i] *= 1.3

    p1 = pX = p2 = kg_var = kg_yok = ust_25 = ust_15 = ust_05 = ust_35 = 0
    en_olasi_skor, en_yuksek_ihtimal = "0 - 0", 0
    ev_gol_tahmin, dep_gol_tahmin = ev_olasiliklar.index(max(ev_olasiliklar)), dep_olasiliklar.index(max(dep_olasiliklar))
    
    for i in range(10):
        for j in range(10):
            ihtimal = ev_olasiliklar[i] * dep_olasiliklar[j]
            if (ev_dinamik_xg + dep_dinamik_xg) < 2.5:
                if i == 0 and j == 0: ihtimal *= 1.15
                elif i == 1 and j == 1: ihtimal *= 1.10
            
            if ihtimal > en_yuksek_ihtimal:
                en_yuksek_ihtimal, en_olasi_skor, ev_gol_tahmin, dep_gol_tahmin = ihtimal, f"{i} - {j}", i, j
                
            if i > j: p1 += ihtimal
            elif i == j: pX += ihtimal
            else: p2 += ihtimal
            if i > 0 and j > 0: kg_var += ihtimal
            else: kg_yok += ihtimal
            if (i + j) > 3.5: ust_35 += ihtimal
            if (i + j) > 2.5: ust_25 += ihtimal
            if (i + j) > 1.5: ust_15 += ihtimal
            if (i + j) > 0.5: ust_05 += ihtimal

    toplam = p1 + pX + p2
    if toplam > 0: p1, pX, p2 = p1/toplam, pX/toplam, p2/toplam
    
    return {
        "p1": p1, "pX": pX, "p2": p2, "kg_var": kg_var, "ust_35": ust_35, "ust_25": ust_25, "ust_15": ust_15, "ust_05": ust_05,
        "skor": en_olasi_skor, "ev_gol": ev_gol_tahmin, "dep_gol": dep_gol_tahmin,
        "ev_05_ust": 1 - ev_olasiliklar[0], "ev_15_ust": 1 - (ev_olasiliklar[0] + ev_olasiliklar[1]),
        "dep_05_ust": 1 - dep_olasiliklar[0], "dep_15_ust": 1 - (dep_olasiliklar[0] + dep_olasiliklar[1])
    }

def yan_bahisleri_hesapla(toplam_xg, lig_karakteristik, hakem_profil, hoca_ev, hoca_dep, carpan):
    hoca_korner = (hoca_ev["korner_carpan"] + hoca_dep["korner_carpan"]) / 2
    return {
        "korner": round(((8.5 + (toplam_xg * 0.8)) * lig_karakteristik["korner_mod"] * hoca_korner) * carpan, 1),
        "tac": round(((38.0 + (toplam_xg * 1.2)) * lig_karakteristik["tac_mod"]) * carpan, 1),
        "kart": round(((4.5 * lig_karakteristik["kart_mod"] * hakem_profil["kart_carpan"])) * carpan, 1),
        "faul": round(((22.5 * lig_karakteristik["faul_mod"] * hakem_profil["faul_carpan"])) * carpan, 1),
        "ofsayt": round(((3.5 + (toplam_xg * 0.2))) * carpan, 1)
    }

# --- YÜKSEK OPTİMİZASYONLU API ÇEKİMİ (TTL=12 SAAT) ---
@st.cache_data(ttl=43200)
def api_football_gunluk_bulten(api_key):
    now_tr = datetime.now(timezone.utc) + timedelta(hours=3)
    url = f"https://v3.football.api-sports.io/fixtures?date={now_tr.strftime('%Y-%m-%d')}"
    headers = {"x-apisports-key": api_key}
    ham_ligler = {}

    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            for match in response.json().get("response", []):
                l_name = match.get("league", {}).get("name", "Diğer")
                status = match.get("fixture", {}).get("status", {}).get("short")
                
                # Sadece oynanacak veya canlı maçları al (Bitenleri filtrele)
                if status in ["FT", "AET", "PEN", "CANC", "PST", "ABD"]: continue
                
                is_live = status in ["1H", "2H", "HT", "LIVE"]
                live_minute = match.get("fixture", {}).get("status", {}).get("elapsed", 0) if is_live else 0
                live_score = f"{match.get('goals', {}).get('home', 0)} - {match.get('goals', {}).get('away', 0)}" if is_live else ""

                utc_date_str = match.get("fixture", {}).get("date")
                dt_tr = datetime.fromisoformat(utc_date_str.replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=3)))
                m_tarih, m_saat = dt_tr.strftime("%d.%m.%Y"), dt_tr.strftime("%H:%M")
                
                if l_name not in ham_ligler: ham_ligler[l_name] = {"logo": match.get("league", {}).get("logo", ""), "maclar": []}
                
                durum_metni = f"🔴 CANLI ({live_minute}') | {live_score}" if is_live else f"🕒 {m_saat}"
                ham_ligler[l_name]["maclar"].append({
                    "id": match.get("fixture", {}).get("id"), "l_id": match.get("league", {}).get("id"),
                    "h_id": match.get("teams", {}).get("home", {}).get("id"), "a_id": match.get("teams", {}).get("away", {}).get("id"), 
                    "saat": m_saat, "tarih": m_tarih, "is_live": is_live, "live_minute": live_minute, "live_score": live_score,
                    "ev": match.get("teams", {}).get("home", {}).get("name"), "dep": match.get("teams", {}).get("away", {}).get("name"), 
                    "referee": match.get("fixture", {}).get("referee") or "Atanmadı / Bilinmiyor",
                    "ev_logo": match.get("teams", {}).get("home", {}).get("logo", ""), "dep_logo": match.get("teams", {}).get("away", {}).get("logo", ""),
                    "metin": f"{durum_metni} | {match.get('teams', {}).get('home', {}).get('name')} vs {match.get('teams', {}).get('away', {}).get('name')}"
                })
    except: return None, "Bağlantı Hatası"
    return ham_ligler, "🟢 API Optimize Edildi (12 Saat Önbellek)"

@st.cache_data(ttl=3600)
def sakat_cezali_cek(api_key, fixture_id, h_id, a_id):
    headers = {"x-apisports-key": api_key}
    url = f"https://v3.football.api-sports.io/injuries?fixture={fixture_id}"
    h_eksik = a_eksik = 0
    try:
        res = requests.get(url, headers=headers, timeout=3)
        if res.status_code == 200:
            for inj in res.json().get("response", []):
                t_id = inj.get("team", {}).get("id")
                if t_id == h_id: h_eksik += 1
                elif t_id == a_id: a_eksik += 1
    except: pass
    return {"h_eksik": h_eksik, "a_eksik": a_eksik}

@st.cache_data(ttl=3600)
def gercek_takim_istatistiklerini_cek(api_key, team_id, is_home):
    headers = {"x-apisports-key": api_key}
    url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=25"
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            matches = res.json().get("response", [])
            bitmis_maclar = [m for m in matches if m.get("fixture", {}).get("status", {}).get("short") in ["FT", "AET", "PEN"]]
            if not bitmis_maclar: return None
            
            now_utc = datetime.now(timezone.utc)
            last_match_date = datetime.fromisoformat(bitmis_maclar[0]["fixture"]["date"].replace("Z", "+00:00")).astimezone(timezone.utc)
            dinlenme_gunu = (now_utc - last_match_date).days
            # Fikstürdeki yoğunluğa göre yorgunluk cezası artırıldı
            yorgunluk_carpani = 0.80 if dinlenme_gunu < 3 else (0.88 if dinlenme_gunu < 5 else 1.0)

            def analiz_et(mac_listesi, t_id):
                if not mac_listesi: return 0.0, 0.0, "Veri Yok", 0.0
                gf_w = ga_w = toplam_agirlik = 0.0
                form_puan = 0.0
                form_str = ""
                for m in mac_listesi:
                    m_date = datetime.fromisoformat(m["fixture"]["date"].replace("Z", "+00:00")).astimezone(timezone.utc)
                    days_ago = (now_utc - m_date).days
                    w = 1.5 if days_ago <= 15 else (1.0 if days_ago <= 30 else 0.6)
                    is_team_home = m["teams"]["home"]["id"] == t_id
                    h_goals, a_goals = m["goals"]["home"] or 0, m["goals"]["away"] or 0
                    
                    if is_team_home: gf_w += h_goals * w; ga_w += a_goals * w; winner = m["teams"]["home"]["winner"]
                    else: gf_w += a_goals * w; ga_w += h_goals * w; winner = m["teams"]["away"]["winner"]
                        
                    toplam_agirlik += w
                    if winner is True: form_str += "W"; form_puan += 3*w
                    elif winner is False: form_str += "L"
                    else: form_str += "D"; form_puan += 1*w
                
                max_olasi_puan = len(mac_listesi) * 3 * 1.5
                form_yuzdesi = (form_puan / max_olasi_puan) * 100 if max_olasi_puan > 0 else 0
                return (gf_w / toplam_agirlik if toplam_agirlik > 0 else 0), (ga_w / toplam_agirlik if toplam_agirlik > 0 else 0), form_str[::-1], form_yuzdesi
            
            g_for_genel, g_ag_genel, form_10, form_yuzde = analiz_et(bitmis_maclar[:10], team_id)
            g_for_saha, g_ag_saha, form_saha_5, _ = analiz_et([m for m in bitmis_maclar if (m["teams"]["home"]["id"] == team_id and is_home) or (m["teams"]["away"]["id"] == team_id and not is_home)][:5], team_id)
            
            sahte_gol_carpani = 1.0
            try:
                stat_url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={bitmis_maclar[0]['fixture']['id']}&team={team_id}"
                stat_res = requests.get(stat_url, headers=headers, timeout=3)
                if stat_res.status_code == 200 and stat_res.json().get("response"):
                    sot = next((int(i["value"]) for i in stat_res.json()["response"][0].get("statistics", []) if i["type"] == "Shots on Goal" and i["value"]), 0)
                    last_goals = bitmis_maclar[0]["goals"]["home"] if bitmis_maclar[0]["teams"]["home"]["id"] == team_id else bitmis_maclar[0]["goals"]["away"]
                    if last_goals and last_goals >= 2 and sot < last_goals: sahte_gol_carpani = 0.85
            except: pass

            return {
                "g_for_saha": g_for_saha, "g_ag_saha": g_ag_saha, "g_for_genel": g_for_genel, "g_ag_genel": g_ag_genel,
                "form_10": form_10, "form_yuzde": form_yuzde, "form_saha_5": form_saha_5,
                "yorgunluk_carpani": yorgunluk_carpani, "sahte_gol_carpani": sahte_gol_carpani, "dinlenme_gunu": dinlenme_gunu
            }
    except: pass
    return None

def aralarindaki_maclari_cek(api_key, h_id, a_id):
    headers, url = {"x-apisports-key": api_key}, f"https://v3.football.api-sports.io/fixtures/headtohead?h2h={h_id}-{a_id}&last=5"
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            bitmis = [m for m in res.json().get("response", []) if m.get("fixture", {}).get("status", {}).get("short") in ["FT", "AET", "PEN"]]
            if not bitmis: return None
            h_tg = sum([(m["goals"]["home"] or 0) if m["teams"]["home"]["id"] == h_id else (m["goals"]["away"] or 0) for m in bitmis])
            a_tg = sum([(m["goals"]["away"] or 0) if m["teams"]["home"]["id"] == h_id else (m["goals"]["home"] or 0) for m in bitmis])
            return {"h_avg": h_tg / len(bitmis), "a_avg": a_tg / len(bitmis), "count": len(bitmis)}
    except: pass
    return None

def stat_kutusu(baslik, ev_deger, dep_deger, ev_ustun=True, dep_ustun=False, suffix=""):
    ev_renk = "#34d399" if ev_ustun else ("#ef4444" if dep_ustun else "#9ca3af")
    dep_renk = "#34d399" if dep_ustun else ("#ef4444" if ev_ustun else "#9ca3af")
    ev_kalin = "bold" if ev_ustun else "normal"
    dep_kalin = "bold" if dep_ustun else "normal"
    
    return f"""
    <div style="display:flex; justify-content:space-between; padding:10px; border-bottom:1px solid #1e293b;">
        <div style="width:30%; text-align:center; color:{ev_renk}; font-weight:{ev_kalin};">{ev_deger}{suffix}</div>
        <div style="width:40%; text-align:center; color:#ffffff; font-size:13px;">{baslik}</div>
        <div style="width:30%; text-align:center; color:{dep_renk}; font-weight:{dep_kalin};">{dep_deger}{suffix}</div>
    </div>
    """

# --- SİSTEM DEĞİŞKENLERİ ---
if "kaydedilen_maclar" not in st.session_state: st.session_state["kaydedilen_maclar"] = []

# --- ARAYÜZ BAŞLANGICI ---
st.set_page_config(page_title="V126 Live & Tracker", page_icon="⚽", layout="wide")
USER_API_KEY = "899fcc53c659a6bb3dac4ff1ef7b211a"
bulten_verisi, aktif_kaynak = api_football_gunluk_bulten(USER_API_KEY)

if not bulten_verisi:
    st.error("Bugün için bülten çekilemedi veya API limitiniz doldu.")
    st.stop()

col_sol, col_sag = st.columns([1, 2.5])

with col_sol:
    st.markdown("### 🔍 Lig ve Maç Seçimi")
    sirali_ligler = ligleri_sirala(list(bulten_verisi.keys()))
    if "secili_lig" not in st.session_state or st.session_state["secili_lig"] not in sirali_ligler:
        st.session_state["secili_lig"] = sirali_ligler[0]

    secilen_lig = st.selectbox("Lig Seçiniz:", sirali_ligler, index=sirali_ligler.index(st.session_state["secili_lig"]))
    if secilen_lig != st.session_state["secili_lig"]:
        st.session_state["secili_lig"] = secilen_lig
        st.session_state["secili_mac_metni"] = bulten_verisi[secilen_lig]["maclar"][0]["metin"]
        st.rerun()

    lig_bilgi = bulten_verisi[secilen_lig]
    mac_metinleri = [m["metin"] for m in lig_bilgi["maclar"]]
    mac_idx = mac_metinleri.index(st.session_state.get("secili_mac_metni", mac_metinleri[0])) if st.session_state.get("secili_mac_metni") in mac_metinleri else 0

    secilen_mac_metni = st.selectbox("Maç Seçiniz:", mac_metinleri, index=mac_idx)
    if secilen_mac_metni != st.session_state.get("secili_mac_metni"):
        st.session_state["secili_mac_metni"] = secilen_mac_metni
        st.rerun()

    secilen_mac_obj = next((m for m in lig_bilgi["maclar"] if m["metin"] == secilen_mac_metni), lig_bilgi["maclar"][0])
    
    st.info(aktif_kaynak)
    st.markdown("API Limitlerini korumak adına tarama sadece analiz butonuna basıldığında gerçekleşir.")

with col_sag:
    ev_sahibi, deplasman = secilen_mac_obj["ev"], secilen_mac_obj["dep"]
    is_live = secilen_mac_obj["is_live"]
    
    live_badge = f"""<span style="background-color:#ef4444; color:white; padding:4px 8px; border-radius:4px; font-weight:bold; font-size:12px; animation: blinker 1.5s linear infinite;">🔴 CANLI ({secilen_mac_obj['live_minute']} d.)</span><br><div style="font-size:24px; color:#ffffff; font-weight:bold; margin-top:5px;">SKOR: {secilen_mac_obj['live_score']}</div>""" if is_live else f"""<span style="font-size: 12px; color: #fbbf24; font-weight: bold; background: rgba(251, 191, 36, 0.1); padding: 4px 8px; border-radius: 4px;">🕒 {secilen_mac_obj['saat']} (TSİ)</span>"""

    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; background: #111827; padding: 22px; border-radius: 12px; border: 1px solid #374151; margin-bottom: 20px;">
        <div style="text-align: center; flex: 1;">
            <img src="{secilen_mac_obj['ev_logo']}" width="65" height="65" style="object-fit: contain; margin-bottom: 8px;">
            <h3 style="color: #ffffff; margin: 0;">{ev_sahibi}</h3>
        </div>
        <div style="text-align: center; padding: 0 20px;">
            <h1 style="color: #ef4444; margin: 0 0 10px 0;">VS</h1>
            {live_badge}
        </div>
        <div style="text-align: center; flex: 1;">
            <img src="{secilen_mac_obj['dep_logo']}" width="65" height="65" style="object-fit: contain; margin-bottom: 8px;">
            <h3 style="color: #ffffff; margin: 0;">{deplasman}</h3>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab_genel, tab_karsilastirma, tab_gecmis = st.tabs(["🚀 Analiz Motoru (Canlı & Öncesi)", "📊 Yüz Yüze İstatistik", "💾 Geçmiş & Kasa"])

    if "son_analiz_maci" not in st.session_state or st.session_state["son_analiz_maci"] != secilen_mac_metni:
        st.session_state["analiz_yapildi"] = False
        st.session_state["son_analiz_maci"] = secilen_mac_metni

    with tab_genel:
        if st.button("🧠 V126 Yapay Zeka Analizini Başlat", use_container_width=True, type="primary"):
            with st.spinner("İstatistikler, Kadro Zafiyetleri ve Fikstür Yorgunluğu Çekiliyor..."):
                ev_data = gercek_takim_istatistiklerini_cek(USER_API_KEY, secilen_mac_obj["h_id"], True)
                dep_data = gercek_takim_istatistiklerini_cek(USER_API_KEY, secilen_mac_obj["a_id"], False)
                h2h_data = aralarindaki_maclari_cek(USER_API_KEY, secilen_mac_obj["h_id"], secilen_mac_obj["a_id"])
                sakatlar = sakat_cezali_cek(USER_API_KEY, secilen_mac_obj["id"], secilen_mac_obj["h_id"], secilen_mac_obj["a_id"])
                
                if not ev_data or not dep_data:
                    st.error("🚨 Yeterli veri bulunamadı. Lütfen başka bir maç seçin.")
                else:
                    lig_karakteristik = LEAGUE_STYLES.get(secilen_lig, LEAGUE_STYLES["Varsayılan"])
                    
                    # Güç hesaplamaları (Eğer deplasman ise katsayıyı %5 artır - fikstür dosyasındaki baskınlık sebebiyle)
                    ev_sakat_etkisi = max(1.0 - (sakatlar["h_eksik"] * 0.05), 0.70)
                    dep_sakat_etkisi = max(1.0 - (sakatlar["a_eksik"] * 0.05), 0.70)

                    ev_guc = ((ev_data["g_for_genel"]+0.1)/(ev_data["g_ag_genel"]+0.1)) * ev_data["yorgunluk_carpani"] * ev_data["sahte_gol_carpani"] * ev_sakat_etkisi
                    dep_guc = ((dep_data["g_for_genel"]+0.1)/(dep_data["g_ag_genel"]+0.1)) * dep_data["yorgunluk_carpani"] * dep_data["sahte_gol_carpani"] * dep_sakat_etkisi * 1.05 # Deplasman Boost
                    
                    ort = (ev_guc + dep_guc) / 2
                    ev_guc_c = min(max(ev_guc / ort, 0.2), 3.0)
                    dep_guc_c = min(max(dep_guc / ort, 0.2), 3.0)

                    ev_temel_xg = ((ev_data["g_for_saha"] + dep_data["g_ag_saha"]) / 2) * lig_karakteristik["xg_mod"] * ev_guc_c
                    dep_temel_xg = ((dep_data["g_for_saha"] + ev_data["g_ag_saha"]) / 2) * lig_karakteristik["xg_mod"] * dep_guc_c
                    
                    sure_carpani = 1.0
                    if is_live:
                        dakika = secilen_mac_obj["live_minute"]
                        sure_carpani = max(0.1, (90 - dakika) / 90.0) # Kalan süreye göre xG daralır
                        
                    ms_m = skor_olasiliklarini_hesapla(ev_temel_xg, dep_temel_xg, 1.0, 1.0, sure_carpani)
                    
                    st.session_state["analiz_datasi"] = {
                        "ev_data": ev_data, "dep_data": dep_data, "h2h_data": h2h_data, "sakatlar": sakatlar,
                        "ev_guc": ev_guc, "dep_guc": dep_guc, "ev_xg": ev_temel_xg, "dep_xg": dep_temel_xg,
                        "ms_m": ms_m, "sure_carpani": sure_carpani
                    }
                    st.session_state["analiz_yapildi"] = True

        if st.session_state.get("analiz_yapildi", False):
            d = st.session_state["analiz_datasi"]
            ms = d["ms_m"]
            
            baslik = "🔴 CANLI DİNAMİK XG VE KALAN SÜRE TAHMİNİ" if is_live else "🎯 MAÇ SONU YZ SKOR TAHMİNİ"
            ekstra_bilgi = f"(Skor {secilen_mac_obj['live_score']} üzerine kalan dakikalar için eklenecek ihtimallerdir)" if is_live else "(0. dakikadan itibaren tam maç projeksiyonu)"
            
            st.markdown(f"""
            <div style="background: #111827; padding: 25px; border-radius: 8px; border: 1px solid #1e3a8a; text-align: center; margin-top: 15px;">
                <span style="color: {'#ef4444' if is_live else '#9ca3af'}; font-size: 14px; font-weight: bold;">{baslik}</span><br>
                <span style="color: #6b7280; font-size: 11px;">{ekstra_bilgi}</span>
                <div style="font-size: 38px; font-weight: 900; color: #34d399; margin-top: 10px;">{ms['skor']}</div>
                <div style="font-size: 13px; color: #60a5fa; margin-top: 5px;">Taraf İhtimali: 1: %{ms['p1']*100:.0f} | X: %{ms['pX']*100:.0f} | 2: %{ms['p2']*100:.0f}</div>
                <div style="font-size: 13px; color: #fbbf24; margin-top: 2px;">Kalan Süre Gol İhtimali: 0.5 Üst: %{ms['ust_05']*100:.0f} | 1.5 Üst: %{ms['ust_15']*100:.0f}</div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("💾 Bu Analizi Kasa/Geçmiş Sekmesine Kaydet", type="secondary"):
                st.session_state["kaydedilen_maclar"].append({
                    "mac": f"{ev_sahibi} vs {deplasman}",
                    "tarih": f"{secilen_mac_obj['tarih']} {secilen_mac_obj['saat']}",
                    "tahmin": ms['skor'],
                    "is_live": is_live,
                    "sonuc": "Bekleniyor"
                })
                st.success("Analiz başarıyla Kayıt sekmesine aktarıldı.")

    with tab_karsilastirma:
        if st.session_state.get("analiz_yapildi", False):
            d = st.session_state["analiz_datasi"]
            e = d["ev_data"]; dep = d["dep_data"]
            s = d["sakatlar"]
            
            st.markdown(f"""
            <div style="background-color:#1e293b; padding:15px; border-radius:10px;">
                <h4 style="text-align:center; color:#f8fafc; margin-bottom:15px;">🔍 Kim Üstün? (Birebir İstatistik Düellosu)</h4>
            """, unsafe_allow_html=True)
            
            html = stat_kutusu("V126 Güç Puanı (Elo)", f"{d['ev_guc']:.2f}", f"{d['dep_guc']:.2f}", d['ev_guc'] > d['dep_guc'], d['dep_guc'] > d['ev_guc'])
            html += stat_kutusu("Zaman Ağırlıklı Form", f"%{e['form_yuzde']:.0f}", f"%{dep['form_yuzde']:.0f}", e['form_yuzde'] > dep['form_yuzde'], dep['form_yuzde'] > e['form_yuzde'])
            html += stat_kutusu("Beklenen Gerçek xG", f"{d['ev_xg']:.2f}", f"{d['dep_xg']:.2f}", d['ev_xg'] > d['dep_xg'], d['dep_xg'] > d['ev_xg'])
            
            # Dinlenme günü (Yüksek olan daha iyi)
            html += stat_kutusu("Dinlenme (Fikstür Yorgunluğu)", f"{e['dinlenme_gunu']} Gün", f"{dep['dinlenme_gunu']} Gün", e['dinlenme_gunu'] > dep['dinlenme_gunu'], dep['dinlenme_gunu'] > e['dinlenme_gunu'])
            
            # Sakatlık (Düşük olan daha iyi)
            html += stat_kutusu("Eksik/Sakat Oyuncu", f"{s['h_eksik']}", f"{s['a_eksik']}", s['h_eksik'] < s['a_eksik'], s['a_eksik'] < s['h_eksik'])
            
            st.markdown(html + "</div>", unsafe_allow_html=True)
        else:
            st.warning("Lütfen önce Genel Analiz sekmesinden maçı analiz ediniz.")

    with tab_gecmis:
        st.markdown("### 💾 Kaydedilen Tahminler ve Sonuç Takibi")
        if not st.session_state["kaydedilen_maclar"]: 
            st.info("Henüz kaydedilmiş bir analiz yok.")
        else:
            for k_idx, kayit in enumerate(reversed(st.session_state["kaydedilen_maclar"])):
                bg_color = "#1e293b" if kayit['sonuc'] == "Bekleniyor" else ("#064e3b" if kayit['sonuc'] == "Kazandı" else "#7f1d1d")
                st.markdown(f"""
                <div style="background-color: {bg_color}; padding: 15px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #34d399;">
                    <b style="color:#ffffff; font-size:14px;">{kayit['mac']} {'(Canlı)' if kayit.get('is_live') else ''}</b><br>
                    <span style="font-size:12px; color:#9ca3af;">{kayit['tarih']}</span><br>
                    <span style="font-size:13px; color:#60a5fa;">YZ Tahmini: <b>{kayit['tahmin']}</b></span><br>
                    <span style="font-size:12px; color:#fbbf24;">Durum: {kayit['sonuc']}</span>
                </div>
                """, unsafe_allow_html=True)
                
                # Manuel sonuç işaretleme butonları
                if kayit['sonuc'] == "Bekleniyor":
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ Kazandı Olarak İşaretle", key=f"win_{k_idx}"):
                            st.session_state["kaydedilen_maclar"][len(st.session_state["kaydedilen_maclar"])-1-k_idx]['sonuc'] = "Kazandı"
                            st.rerun()
                    with c2:
                        if st.button("❌ Kaybetti Olarak İşaretle", key=f"lose_{k_idx}"):
                            st.session_state["kaydedilen_maclar"][len(st.session_state["kaydedilen_maclar"])-1-k_idx]['sonuc'] = "Kaybetti"
                            st.rerun()
