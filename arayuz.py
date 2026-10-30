import streamlit as st
import time
import requests
import math
import hashlib
from datetime import datetime, timedelta, timezone

# --- SABİTLER VE LİGLER ---
MAJOR_LEAGUES = [
    "Süper Lig", "Premier League", "La Liga", "Serie A", "Bundesliga", 
    "Ligue 1", "UEFA Champions League", "UEFA Europa League", "UEFA Europa Conference League",
    "Türkiye Kupası", "Ziraat Türkiye Kupası", "FA Cup", "EFL Cup", "Copa del Rey", "DFB Pokal", "Coppa Italia"
]

LEAGUE_STYLES = {
    "Premier League": {"xg_mod": 1.10, "korner_mod": 1.15, "tac_mod": 1.05, "kart_mod": 0.85, "faul_mod": 0.90, "tarz": "Yüksek Tempo"},
    "Süper Lig": {"xg_mod": 1.02, "korner_mod": 0.95, "tac_mod": 1.25, "kart_mod": 1.35, "faul_mod": 1.30, "tarz": "Duran Top & Agresif"},
    "La Liga": {"xg_mod": 0.95, "korner_mod": 0.90, "tac_mod": 0.95, "kart_mod": 1.10, "faul_mod": 1.10, "tarz": "Pas, Teknik"},
    "Serie A": {"xg_mod": 0.90, "korner_mod": 1.05, "tac_mod": 0.90, "kart_mod": 1.05, "faul_mod": 1.15, "tarz": "Taktiksel Savunma"},
    "Bundesliga": {"xg_mod": 1.18, "korner_mod": 1.00, "tac_mod": 1.00, "kart_mod": 0.90, "faul_mod": 0.95, "tarz": "Geçiş Oyunu & Bol Gol"},
    "Varsayılan": {"xg_mod": 1.0, "korner_mod": 1.0, "tac_mod": 1.0, "kart_mod": 1.0, "faul_mod": 1.0, "tarz": "Standart Futbol"}
}

# YENİ EKLENEN: SADECE ANA VE 2. LİGLERİ İÇEREN HIZLI TARAMA LİSTESİ (BEYAZ LİSTE)
HIZLI_TARAMA_LIGLERI = [
    "premier league", "championship", "la liga", "segunda", "serie a", "serie b",
    "bundesliga", "2. bundesliga", "ligue 1", "ligue 2", "süper lig", "1. lig",
    "eredivisie", "eerste divisie", "primeira liga", "liga portugal 2", "pro league",
    "challenger pro league", "super league", "premiership", "primera division", "mls", 
    "brasileirão série a", "brasileirão série b", "liga profesional", "uefa champions league", 
    "uefa europa league", "uefa europa conference league", "allsvenskan", "eliteserien", 
    "superliga", "ekstraklasa", "bundesliga 1", "bundesliga 2", "serie a betano", "serie bkt"
]

def ligleri_sirala(lig_listesi):
    def oncelik_belirle(lig_adi):
        is_women = "women" in lig_adi.lower() or "wom" in lig_adi.lower()
        for i, maj_lig in enumerate(MAJOR_LEAGUES):
            if maj_lig.lower() in lig_adi.lower(): return i if not is_women else i + 500
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
        {"profil": "Gegenpressing", "dizilis": "4-3-3 veya 4-2-3-1", "xg_carpan": 1.15, "korner_carpan": 1.20, "renk": "#ef4444"},
        {"profil": "Tiki-Taka / Pas Kontrol", "dizilis": "4-3-3", "xg_carpan": 1.05, "korner_carpan": 1.10, "renk": "#60a5fa"},
        {"profil": "Katı Savunma / Kontra", "dizilis": "5-3-2 veya 5-4-1", "xg_carpan": 0.85, "korner_carpan": 0.80, "renk": "#fbbf24"},
        {"profil": "Dengeli / Taktiksel", "dizilis": "4-4-2 veya 4-2-3-1", "xg_carpan": 1.0, "korner_carpan": 1.0, "renk": "#34d399"}
    ]
    return profiller[h % len(profiller)]

def hash_tabanli_cevresel_veri(kimlik_metni):
    h = int(hashlib.md5(kimlik_metni.encode('utf-8')).hexdigest(), 16)
    havalar = [("Açık Zemin", 1.0, "Pas oyununa uygun."), ("Hafif Yağmurlu", 0.95, "Kaygan zemin."), ("Yoğun Yağışlı", 0.85, "Ağır zemin, xG düşer.")]
    return havalar[h % len(havalar)]

def takim_degeri_hesapla(guc_puani, league_coef):
    base = (guc_puani ** 1.8) * 20 * league_coef
    if league_coef >= 2.0: base *= 3
    elif league_coef >= 1.8: base *= 1.5
    raw_val = max(10.0, min(1400.0, base))
    return raw_val, f"€{raw_val:.1f}M"

# --- POISSON MOTORU VE MATRİS ---
def poisson(k, lambd): return (lambd**k * math.exp(-lambd)) / math.factorial(k)

def gol_yuku_hesapla(g_for, g_ag):
    toplam = g_for + g_ag
    if toplam >= 3.5: return 1.40
    elif toplam >= 2.8: return 1.25
    elif toplam <= 1.8: return 0.85
    return 1.0

def skor_olasiliklarini_hesapla(ev_xg, dep_xg, ev_gol_yuku=1.0, dep_gol_yuku=1.0, is_kupa=False, ev_yorgun=False, yari_modu=0):
    if is_kupa or ev_yorgun: dep_xg *= 1.15
    ev_dinamik_xg, dep_dinamik_xg = ev_xg * ev_gol_yuku, dep_xg * dep_gol_yuku
    
    if yari_modu == 1:
        ev_dinamik_xg *= 0.52
        dep_dinamik_xg *= 0.52
    elif yari_modu == 2:
        ev_dinamik_xg *= 0.65
        dep_dinamik_xg *= 0.65

    ev_olasiliklar = [poisson(i, ev_dinamik_xg) for i in range(10)]
    dep_olasiliklar = [poisson(i, dep_dinamik_xg) for i in range(10)]
    
    if ev_dinamik_xg > 1.8:
        for i in range(4, 10): ev_olasiliklar[i] *= 1.4
    if dep_dinamik_xg > 1.8:
        for i in range(4, 10): dep_olasiliklar[i] *= 1.4

    p1 = pX = p2 = kg_var = ust_55 = ust_35 = ust_25 = ust_15 = ust_05 = 0
    en_olasi_skor, en_yuksek_ihtimal = "0 - 0", 0
    ev_gol_tahmin, dep_gol_tahmin = 0, 0
    
    skor_matrisi = [[0.0 for _ in range(6)] for _ in range(6)]

    for i in range(10):
        for j in range(10):
            ihtimal = ev_olasiliklar[i] * dep_olasiliklar[j]
            if (ev_dinamik_xg + dep_dinamik_xg) < 2.5 and yari_modu == 0:
                if i == 0 and j == 0: ihtimal *= 1.15
                elif i == 1 and j == 1: ihtimal *= 1.10
            
            if i < 6 and j < 6: skor_matrisi[i][j] = ihtimal
                
    if yari_modu == 1 and (ev_dinamik_xg + dep_dinamik_xg) > 0.8:
        sifir_sifir_dususu = skor_matrisi[0][0] * 0.20 
        skor_matrisi[0][0] -= sifir_sifir_dususu
        skor_matrisi[1][0] += sifir_sifir_dususu * 0.50 
        skor_matrisi[0][1] += sifir_sifir_dususu * 0.30 
        skor_matrisi[1][1] += sifir_sifir_dususu * 0.20 

    for i in range(6):
        for j in range(6):
            ihtimal = skor_matrisi[i][j]
            if ihtimal > en_yuksek_ihtimal: 
                en_yuksek_ihtimal, en_olasi_skor, ev_gol_tahmin, dep_gol_tahmin = ihtimal, f"{i} - {j}", i, j
                
            if i > j: p1 += ihtimal
            elif i == j: pX += ihtimal
            else: p2 += ihtimal
            if i > 0 and j > 0: kg_var += ihtimal
            if (i + j) > 5.5: ust_55 += ihtimal
            if (i + j) > 3.5: ust_35 += ihtimal
            if (i + j) > 2.5: ust_25 += ihtimal
            if (i + j) > 1.5: ust_15 += ihtimal
            if (i + j) > 0.5: ust_05 += ihtimal

    toplam = p1 + pX + p2
    if toplam > 0: p1, pX, p2 = p1/toplam, pX/toplam, p2/toplam
    
    matris_toplam = sum(sum(row) for row in skor_matrisi)
    if matris_toplam > 0: skor_matrisi = [[val / matris_toplam for val in row] for row in skor_matrisi]

    if yari_modu == 0:
        if ust_35 > 0.40 and (ev_gol_tahmin + dep_gol_tahmin) <= 3:
            if ev_dinamik_xg > dep_dinamik_xg: en_olasi_skor = f"{ev_gol_tahmin + 1} - {dep_gol_tahmin}"
            elif dep_dinamik_xg > ev_dinamik_xg: en_olasi_skor = f"{ev_gol_tahmin} - {dep_gol_tahmin + 1}"
            else: en_olasi_skor = "2 - 2"
        elif ust_25 > 0.55 and (ev_gol_tahmin + dep_gol_tahmin) <= 2:
            if ev_dinamik_xg > dep_dinamik_xg: en_olasi_skor = f"{ev_gol_tahmin + 1} - {dep_gol_tahmin}"
            elif dep_dinamik_xg > ev_dinamik_xg: en_olasi_skor = f"{ev_gol_tahmin} - {dep_gol_tahmin + 1}"
            else: en_olasi_skor = "1 - 1"
    
    return {
        "p1": p1, "pX": pX, "p2": p2, "kg_var": kg_var, "ust_55": ust_55, "ust_35": ust_35, "ust_25": ust_25, "ust_15": ust_15, "ust_05": ust_05,
        "skor": en_olasi_skor, 
        "ev_05_ust": 1 - (skor_matrisi[0][0] + skor_matrisi[0][1] + skor_matrisi[0][2]),
        "dep_05_ust": 1 - (skor_matrisi[0][0] + skor_matrisi[1][0] + skor_matrisi[2][0]),
        "matris": skor_matrisi
    }

def surpriz_ihtimalleri_hesapla(iy_matris, iy2_matris):
    ht1_ft2 = 0.0
    ht2_ft1 = 0.0
    for i in range(6):
        for j in range(6):
            iy_prob = iy_matris[i][j]
            if iy_prob < 0.001: continue
            for k in range(6):
                for l in range(6):
                    iy2_prob = iy2_matris[k][l]
                    if iy2_prob < 0.001: continue
                    
                    ms_ev = i + k
                    ms_dep = j + l
                    
                    if i > j and ms_ev < ms_dep:
                        ht1_ft2 += iy_prob * iy2_prob
                    if i < j and ms_ev > ms_dep:
                        ht2_ft1 += iy_prob * iy2_prob
                        
    return round(ht1_ft2, 4), round(ht2_ft1, 4)

def yan_bahisleri_hesapla(toplam_xg, lig_karakteristik, hakem_profil, hoca_ev, hoca_dep, carpan):
    hoca_korner = (hoca_ev["korner_carpan"] + hoca_dep["korner_carpan"]) / 2
    return {
        "korner": round(((8.5 + (toplam_xg * 0.8)) * lig_karakteristik["korner_mod"] * hoca_korner) * carpan, 1),
        "tac": round(((38.0 + (toplam_xg * 1.2)) * lig_karakteristik["tac_mod"]) * carpan, 1),
        "kart": round(((4.5 * lig_karakteristik["kart_mod"] * hakem_profil["kart_carpan"])) * carpan, 1),
        "faul": round(((22.5 * lig_karakteristik["faul_mod"] * hakem_profil["faul_carpan"])) * carpan, 1)
    }

# --- API VE VERİ FONKSİYONLARI ---
@st.cache_data(ttl=43200)
def api_football_gercek_veri_getir(api_key):
    now_tr = datetime.now(timezone.utc) + timedelta(hours=3)
    bugun_str = now_tr.strftime("%d.%m.%Y")
    suan_saat_dk = now_tr.strftime("%H:%M")
    ham_ligler = {}

    try:
        url = f"https://v3.football.api-sports.io/fixtures?date={now_tr.strftime('%Y-%m-%d')}"
        headers = {"x-apisports-key": api_key}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            for match in response.json().get("response", []):
                l_name = match.get("league", {}).get("name", "Diğer")
                utc_date_str = match.get("fixture", {}).get("date")
                if not utc_date_str: continue
                dt_tr = datetime.fromisoformat(utc_date_str.replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=3)))
                m_tarih, m_saat = dt_tr.strftime("%d.%m.%Y"), dt_tr.strftime("%H:%M")
                
                if l_name not in ham_ligler: ham_ligler[l_name] = {"logo": match.get("league", {}).get("logo", ""), "maclar": []}
                ham_ligler[l_name]["maclar"].append({
                    "id": match.get("fixture", {}).get("id"), "l_id": match.get("league", {}).get("id"), "season": match.get("league", {}).get("season"),
                    "h_id": match.get("teams", {}).get("home", {}).get("id"), "a_id": match.get("teams", {}).get("away", {}).get("id"), 
                    "saat": m_saat, "tarih": m_tarih, 
                    "ev": match.get("teams", {}).get("home", {}).get("name"), "dep": match.get("teams", {}).get("away", {}).get("name"), 
                    "referee": match.get("fixture", {}).get("referee") or "Atanmadı / Bilinmiyor",
                    "venue": match.get("fixture", {}).get("venue", {}).get("name") or "Bilinmiyor",
                    "ev_logo": match.get("teams", {}).get("home", {}).get("logo", ""), "dep_logo": match.get("teams", {}).get("away", {}).get("logo", ""),
                    "metin": f"📅 {m_tarih} - 🕒 {m_saat} | {match.get('teams', {}).get('home', {}).get('name')} vs {match.get('teams', {}).get('away', {}).get('name')}"
                })
    except: return None, "Bağlantı Hatası"

    filtrelenmis_ligler = {l: d for l, d in ham_ligler.items() if [m for m in d["maclar"] if not (m["tarih"] == bugun_str and m["saat"] <= suan_saat_dk)]}
    for l in filtrelenmis_ligler: filtrelenmis_ligler[l]["maclar"] = [m for m in filtrelenmis_ligler[l]["maclar"] if not (m["tarih"] == bugun_str and m["saat"] <= suan_saat_dk)]
    return filtrelenmis_ligler, "🟢 V125 Master Aktif"

@st.cache_data(ttl=43200)
def puan_durumu_cek(api_key, league_id, season, h_id, a_id):
    headers, url = {"x-apisports-key": api_key}, f"https://v3.football.api-sports.io/standings?league={league_id}&season={season}"
    h_sira_str, a_sira_str = "Bilinmiyor", "Bilinmiyor"
    h_rank, a_rank = 999, 999
    try:
        res = requests.get(url, headers=headers, timeout=3)
        if res.status_code == 200 and res.json().get("response"):
            standings = res.json()["response"][0].get("league", {}).get("standings", [])
            for group in standings:
                for team in group:
                    if team.get("team", {}).get("id") == h_id: 
                        h_rank = team.get('rank')
                        h_sira_str = f"{h_rank}. Sıra ({team.get('points')} Puan)"
                    if team.get("team", {}).get("id") == a_id: 
                        a_rank = team.get('rank')
                        a_sira_str = f"{a_rank}. Sıra ({team.get('points')} Puan)"
    except: pass
    return h_sira_str, a_sira_str, h_rank, a_rank

@st.cache_data(ttl=3600)
def kadro_durumu_ve_getir(api_key, fixture_id, h_id, a_id):
    headers = {"x-apisports-key": api_key}
    url = f"https://v3.football.api-sports.io/fixtures/lineups?fixture={fixture_id}"
    h_kadro, a_kadro = [], []
    durum = False
    try:
        res = requests.get(url, headers=headers, timeout=3)
        data = res.json().get("response", [])
        if data:
            durum = True
            for team_data in data:
                t_id = team_data.get("team", {}).get("id")
                startXI = [p.get("player", {}).get("name") for p in team_data.get("startXI", [])]
                if t_id == h_id: h_kadro = startXI
                elif t_id == a_id: a_kadro = startXI
    except: pass
    return {"resmi": durum, "h_kadro": h_kadro, "a_kadro": a_kadro}

@st.cache_data(ttl=43200)
def sakat_cezali_cek(api_key, fixture_id, h_id, a_id, season):
    headers, url = {"x-apisports-key": api_key}, f"https://v3.football.api-sports.io/injuries?fixture={fixture_id}"
    h_agirlik = a_agirlik = 0.0
    h_onemli, a_onemli = [], []
    try:
        res = requests.get(url, headers=headers, timeout=3)
        if res.status_code == 200:
            for inj in res.json().get("response", []):
                t_id, p_name = inj.get("team", {}).get("id"), inj.get("player", {}).get("name")
                agirlik, etiket = 0.5, "🟠 Sakat/Eksik"
                if t_id == h_id: 
                    h_agirlik += agirlik
                    h_onemli.append(f"{p_name} ({etiket})")
                elif t_id == a_id: 
                    a_agirlik += agirlik
                    a_onemli.append(f"{p_name} ({etiket})")
    except: pass
    return {"h_agirlik": h_agirlik, "a_agirlik": a_agirlik, "h_onemli": h_onemli, "a_onemli": a_onemli}

@st.cache_data(ttl=43200)
def gercek_takim_istatistiklerini_cek(api_key, team_id, is_home):
    headers = {"x-apisports-key": api_key}
    url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=25"
    try:
        res = requests.get(url, headers=headers, timeout=4)
        if res.status_code == 200:
            matches = res.json().get("response", [])
            bitmis_maclar = [m for m in matches if m.get("fixture", {}).get("status", {}).get("short") in ["FT", "AET", "PEN"]]
            if not bitmis_maclar: return None
            now_utc = datetime.now(timezone.utc)
            last_match_date = datetime.fromisoformat(bitmis_maclar[0]["fixture"]["date"].replace("Z", "+00:00")).astimezone(timezone.utc)
            dinlenme_gunu = (now_utc - last_match_date).days
            yorgunluk_carpani = 0.85 if dinlenme_gunu < 4 else 1.0 
            league_names = [m["league"]["name"] for m in bitmis_maclar]
            main_league_name = max(set(league_names), key=league_names.count) if league_names else "Bilinmiyor"
            
            LEAGUE_COEFFICIENTS = {
                "Premier League": 2.0, "La Liga": 1.9, "Serie A": 1.8, "Bundesliga": 1.8, "Ligue 1": 1.7,
                "UEFA Champions League": 2.2, "UEFA Europa League": 1.8, "Süper Lig": 1.4, "DFB Pokal": 1.6,
                "Championship": 1.3, "Eredivisie": 1.5, "Primeira Liga": 1.5
            }
            league_coef = LEAGUE_COEFFICIENTS.get(main_league_name, 0.85)
            
            def analiz_et(mac_listesi, t_id):
                if not mac_listesi: return 0.0, 0.0, "Veri Yok"
                gf_w = ga_w = toplam_agirlik = 0.0
                form_str = ""
                for m in mac_listesi:
                    m_date = datetime.fromisoformat(m["fixture"]["date"].replace("Z", "+00:00")).astimezone(timezone.utc)
                    days_ago = (now_utc - m_date).days
                    if days_ago <= 15: w = 1.5
                    elif days_ago <= 30: w = 1.0
                    else: w = 0.6
                    is_team_home = m["teams"]["home"]["id"] == t_id
                    h_goals, a_goals = m["goals"]["home"] or 0, m["goals"]["away"] or 0
                    if is_team_home:
                        gf_w += h_goals * w; ga_w += a_goals * w; winner = m["teams"]["home"]["winner"]
                    else:
                        gf_w += a_goals * w; ga_w += h_goals * w; winner = m["teams"]["away"]["winner"]
                    toplam_agirlik += w
                    if winner is True: form_str += "W"
                    elif winner is False: form_str += "L"
                    else: form_str += "D"
                return (gf_w / toplam_agirlik if toplam_agirlik > 0 else 0), (ga_w / toplam_agirlik if toplam_agirlik > 0 else 0), form_str[::-1]
            
            g_for_genel, g_ag_genel, form_10 = analiz_et(bitmis_maclar[:10], team_id)
            g_for_saha, g_ag_saha, form_saha_5 = analiz_et([m for m in bitmis_maclar if (m["teams"]["home"]["id"] == team_id and is_home) or (m["teams"]["away"]["id"] == team_id and not is_home)][:5], team_id)
            
            sahte_gol_carpani = 1.0
            return {
                "g_for_saha": g_for_saha, "g_ag_saha": g_ag_saha, "g_for_genel": g_for_genel, "g_ag_genel": g_ag_genel,
                "form_10": form_10, "form_saha_5": form_saha_5, "main_league": main_league_name, "league_coef": league_coef,
                "yorgunluk_carpani": yorgunluk_carpani, "sahte_gol_carpani": sahte_gol_carpani, "dinlenme_gunu": dinlenme_gunu
            }
    except: pass
    return None

@st.cache_data(ttl=43200)
def aralarindaki_maclari_cek(api_key, h_id, a_id):
    headers, url = {"x-apisports-key": api_key}, f"https://v3.football.api-sports.io/fixtures/headtohead?h2h={h_id}-{a_id}&last=5"
    try:
        res = requests.get(url, headers=headers, timeout=3)
        if res.status_code == 200:
            bitmis = [m for m in res.json().get("response", []) if m.get("fixture", {}).get("status", {}).get("short") in ["FT", "AET", "PEN"]]
            if not bitmis: return None
            h_tg = sum([(m["goals"]["home"] or 0) if m["teams"]["home"]["id"] == h_id else (m["goals"]["away"] or 0) for m in bitmis])
            a_tg = sum([(m["goals"]["away"] or 0) if m["teams"]["home"]["id"] == h_id else (m["goals"]["home"] or 0) for m in bitmis])
            return {"h_avg": h_tg / len(bitmis), "a_avg": a_tg / len(bitmis), "count": len(bitmis)}
    except: pass
    return None

def tekil_mac_analizi_yap(api_key, mac_obj, lig_karakteristik):
    ev_data = gercek_takim_istatistiklerini_cek(api_key, mac_obj["h_id"], True)
    dep_data = gercek_takim_istatistiklerini_cek(api_key, mac_obj["a_id"], False)
    if not ev_data or not dep_data: return None
    
    h2h_data = aralarindaki_maclari_cek(api_key, mac_obj["h_id"], mac_obj["a_id"])
    sakatlar = sakat_cezali_cek(api_key, mac_obj["id"], mac_obj["h_id"], mac_obj["a_id"], mac_obj["season"])
    is_kupa = mac_obj["l_id"] in [45, 143, 141, 137, 529] or "kupa" in mac_obj["metin"].lower() or "cup" in mac_obj["metin"].lower()

    ev_guc_puani = ((ev_data["g_for_genel"]+0.1)/(ev_data["g_ag_genel"]+0.1)) * ev_data["league_coef"] * max(1.0 - (sakatlar["h_agirlik"]*0.05), 0.65)
    dep_guc_puani = ((dep_data["g_for_genel"]+0.1)/(dep_data["g_ag_genel"]+0.1)) * dep_data["league_coef"] * max(1.0 - (sakatlar["a_agirlik"]*0.05), 0.65)
    
    ort_guc = (ev_guc_puani + dep_guc_puani) / 2
    ev_guc_carpani, dep_guc_carpani = min(max(ev_guc_puani/ort_guc, 0.2), 3.0), min(max(dep_guc_puani/ort_guc, 0.2), 3.0)
    
    hoca_ev = hoca_analizi_yap(mac_obj["ev"])
    hoca_dep = hoca_analizi_yap(mac_obj["dep"])

    ev_temel_xg = ((ev_data["g_for_saha"]+dep_data["g_ag_saha"])/2) * lig_karakteristik["xg_mod"] * hoca_ev["xg_carpan"] * ev_guc_carpani
    dep_temel_xg = ((dep_data["g_for_saha"]+ev_data["g_ag_saha"])/2) * lig_karakteristik["xg_mod"] * hoca_dep["xg_carpan"] * dep_guc_carpani
    
    if is_kupa:
        if ev_guc_carpani > 1.8: ev_temel_xg *= 0.75
        if dep_guc_carpani > 1.8: dep_temel_xg *= 0.75
    
    ev_gercek_xg = max(0.1, (ev_temel_xg*0.7) + (h2h_data["h_avg"]*0.3)) if h2h_data else max(0.1, ev_temel_xg)
    dep_gercek_xg = max(0.1, (dep_temel_xg*0.7) + (h2h_data["a_avg"]*0.3)) if h2h_data else max(0.1, dep_temel_xg)
    
    ev_g_yuku, dep_g_yuku = gol_yuku_hesapla(ev_data["g_for_genel"], ev_data["g_ag_genel"]), gol_yuku_hesapla(dep_data["g_for_genel"], dep_data["g_ag_genel"])
    ev_yorgun = ev_data["dinlenme_gunu"] < 4

    ms_m = skor_olasiliklarini_hesapla(ev_gercek_xg, dep_gercek_xg, ev_g_yuku, dep_g_yuku, is_kupa, ev_yorgun, yari_modu=0)
    iy_m = skor_olasiliklarini_hesapla(ev_gercek_xg, dep_gercek_xg, ev_g_yuku, dep_g_yuku, is_kupa, ev_yorgun, yari_modu=1)
    iy2_m = skor_olasiliklarini_hesapla(ev_gercek_xg, dep_gercek_xg, ev_g_yuku, dep_g_yuku, is_kupa, ev_yorgun, yari_modu=2)
    
    ht1_ft2, ht2_ft1 = surpriz_ihtimalleri_hesapla(iy_m['matris'], iy2_m['matris'])
    en_iyi_surprizler = {
        "1/2": ht1_ft2,
        "2/1": ht2_ft1,
        "iy_kg": iy_m['kg_var'],
        "ust_55": ms_m['ust_55']
    }
    
    secenekler = []
    if ms_m['p1'] > 0.55: secenekler.append({"bahis": f"MS 1 ({mac_obj['ev']})", "ihtimal": ms_m['p1']})
    elif ms_m['p2'] > 0.50: secenekler.append({"bahis": f"MS 2 ({mac_obj['dep']})", "ihtimal": ms_m['p2']})
    if ms_m['ust_35'] > 0.45: secenekler.append({"bahis": "3.5 Gol Üstü", "ihtimal": ms_m['ust_35']})
    elif ms_m['ust_25'] > 0.55: secenekler.append({"bahis": "2.5 Gol Üstü", "ihtimal": ms_m['ust_25']})
    elif (1 - ms_m['ust_25']) > 0.65: secenekler.append({"bahis": "2.5 Gol Altı", "ihtimal": (1 - ms_m['ust_25'])})
    if ms_m['kg_var'] > 0.60: secenekler.append({"bahis": "Karşılıklı Gol Var", "ihtimal": ms_m['kg_var']})
    
    en_iyi = sorted(secenekler, key=lambda x: x["ihtimal"], reverse=True)[0] if secenekler else {"bahis": "Yok", "ihtimal": 0}
    
    return {
        "ev_data": ev_data, "dep_data": dep_data, "h2h_data": h2h_data, "sakatlar": sakatlar,
        "ev_xg": ev_gercek_xg, "dep_xg": dep_gercek_xg, "ev_guc_puani": ev_guc_puani, "dep_guc_puani": dep_guc_puani,
        "hoca_ev": hoca_ev, "hoca_dep": hoca_dep, "ms_m": ms_m, "iy_m": iy_m, "iy2_m": iy2_m, 
        "en_iyi_bahis": en_iyi, "surprizler": en_iyi_surprizler
    }

# --- GÖRSEL KUTULAR ---
def stat_kutu_olustur(baslik, oran1, yazi1, oran2, yazi2, icon="⚽", renk="#60a5fa"):
    return f"""<div style="border: 1px solid #1e3a8a; border-radius: 10px; padding: 20px; text-align: center; background-color: #0f172a; height: 100%;">
        <div style="color: {renk}; font-weight: 700; margin-bottom: 20px;">{icon} {baslik}</div>
        <div style="border-top: 1px solid #1e293b; margin: 15px 0;"></div>
        <div style="font-size: 22px; font-weight: bold; color: {renk};">{oran1}</div>
        <div style="font-size: 12px; color: #9ca3af; margin-bottom: 15px;">{yazi1}</div>
        <div style="font-size: 22px; font-weight: bold; color: {renk};">{oran2}</div>
        <div style="font-size: 12px; color: #9ca3af;">{yazi2}</div>
    </div>"""

def alt_stat_kutu(baslik, deger, renk, icon):
    return f"""<div style="border: 1px solid #1e293b; border-radius: 8px; padding: 15px; text-align: center; background-color: #111827;">
        <div style="color: {renk}; font-weight: 700; font-size: 13px; margin-bottom: 10px;">{icon} {baslik}</div>
        <div style="font-size: 16px; font-weight: bold; color: #f3f4f6;">{deger}</div>
    </div>"""

def satir_olustur(baslik, ev_deger, dep_deger, ters_oran=False):
    if ev_deger == dep_deger: ev_renk = dep_renk = "#9ca3af"; ev_icon = dep_icon = ""
    elif (ev_deger > dep_deger and not ters_oran) or (ev_deger < dep_deger and ters_oran): ev_renk, dep_renk = "#34d399", "#ef4444"; ev_icon, dep_icon = "🏆", ""
    else: ev_renk, dep_renk = "#ef4444", "#34d399"; ev_icon, dep_icon = "", "🏆"
    ev_gosterim = f"{ev_deger:.2f}" if isinstance(ev_deger, float) else str(ev_deger)
    dep_gosterim = f"{dep_deger:.2f}" if isinstance(dep_deger, float) else str(dep_deger)
    return f'<div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #374151;"><div style="width: 33%; text-align: center; color: {ev_renk}; font-weight: bold;">{ev_icon} {ev_gosterim}</div><div style="width: 34%; text-align: center; color: #ffffff;">{baslik}</div><div style="width: 33%; text-align: center; color: {dep_renk}; font-weight: bold;">{dep_gosterim} {dep_icon}</div></div>'

def render_taktik_kutu(zaman_baslik, m, yan, ev_sahibi, deplasman):
    st.markdown(f"""
    <div style="background: #111827; padding: 15px; border-radius: 8px; border: 1px solid #1e3a8a; text-align: center; margin-bottom: 25px;">
        <span style="color: #9ca3af; font-size: 13px; font-weight: bold;">🎯 YAPAY ZEKA {zaman_baslik.upper()} SKOR TAHMİNİ</span>
        <div style="font-size: 28px; font-weight: 900; color: #34d399; margin-top: 5px;">{m['skor']}</div>
    </div>
    """, unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(stat_kutu_olustur(f"{ev_sahibi} Golü", f"%{m['ev_05_ust']*100:.1f}", "0.5 Üst Olasılığı", f"%{(1-m['ev_05_ust'])*100:.1f}", "0.5 Alt Olasılığı", "🛡️"), unsafe_allow_html=True)
    with c2: st.markdown(stat_kutu_olustur("Toplam Gol", f"%{m['ust_05']*100:.1f}", "0.5 Üst Olasılığı", f"%{m['ust_15']*100:.1f}", "1.5 Üst Olasılığı", "⚽"), unsafe_allow_html=True)
    with c3: st.markdown(stat_kutu_olustur(f"{deplasman} Golü", f"%{m['dep_05_ust']*100:.1f}", "0.5 Üst Olasılığı", f"%{(1-m['dep_05_ust'])*100:.1f}", "0.5 Alt Olasılığı", "✈️"), unsafe_allow_html=True)
    
    st.write("")
    c_alt1, c_alt2, c_alt3, c_alt4 = st.columns(4)
    with c_alt1: st.markdown(alt_stat_kutu(f"Kart", f"{math.floor(yan['kart'])}.5 Üst", "#fbbf24", "🟨"), unsafe_allow_html=True)
    with c_alt2: st.markdown(alt_stat_kutu(f"Korner", f"{math.floor(yan['korner'])}.5 Üst", "#ef4444", "🚩"), unsafe_allow_html=True)
    with c_alt3: st.markdown(alt_stat_kutu(f"Taç", f"{math.floor(yan['tac'])}.5 Üst", "#60a5fa", "📐"), unsafe_allow_html=True)
    with c_alt4: st.markdown(alt_stat_kutu(f"Faul", f"~{int(yan['faul'])}", "#ec4899", "🛑"), unsafe_allow_html=True)


# --- ARAYÜZ BAŞLANGICI ---
st.set_page_config(page_title="Pro Analiz Paneli", page_icon="⚽", layout="wide")
USER_API_KEY = "899fcc53c659a6bb3dac4ff1ef7b211a"
bulten_verisi, aktif_kaynak = api_football_gercek_veri_getir(USER_API_KEY)

if not bulten_verisi: 
    st.error("Maç bulunamadı.")
    st.stop()

col_sol, col_sag = st.columns([1, 3])

# --- SOL MENÜ (MAÇ SEÇİMİ VE SIFIRLAMA MANTIĞI) ---
with col_sol:
    st.markdown("### 🔍 Takım veya Maç Ara")
    arama_sorgusu = st.text_input("Örn: Arsenal, Galatasaray", placeholder="Takım adı yazın...")
    filtrelenmis_ligler = {}
    for l_adi, l_data in bulten_verisi.items():
        eslesen = [m for m in l_data["maclar"] if arama_sorgusu.lower() in m["ev"].lower() or arama_sorgusu.lower() in m["dep"].lower()]
        if eslesen: filtrelenmis_ligler[l_adi] = {"logo": l_data["logo"], "maclar": eslesen}
    
    gosterilecek_veri = filtrelenmis_ligler if arama_sorgusu else bulten_verisi
    if not gosterilecek_veri: 
        st.warning("Maç bulunamadı.")
        st.stop()

    sirali_ligler = ligleri_sirala(list(gosterilecek_veri.keys()))
    if "secili_lig" not in st.session_state or st.session_state["secili_lig"] not in sirali_ligler: 
        st.session_state["secili_lig"] = sirali_ligler[0]

    st.markdown("### 📋 Lig ve Maç Seçimi")
    
    secilen_lig = st.selectbox("Lig Seçiniz:", sirali_ligler, index=sirali_ligler.index(st.session_state["secili_lig"]))
    if secilen_lig != st.session_state["secili_lig"]:
        st.session_state["secili_lig"] = secilen_lig
        st.session_state["secili_mac_metni"] = gosterilecek_veri[secilen_lig]["maclar"][0]["metin"]
        st.session_state["analiz_yapildi"] = False
        st.rerun()

    lig_bilgi = gosterilecek_veri[secilen_lig]
    mac_metinleri = [m["metin"] for m in lig_bilgi["maclar"]]
    mac_idx = mac_metinleri.index(st.session_state.get("secili_mac_metni", mac_metinleri[0])) if st.session_state.get("secili_mac_metni") in mac_metinleri else 0

    secilen_mac_metni = st.selectbox("Maç Seçiniz:", mac_metinleri, index=mac_idx)
    if secilen_mac_metni != st.session_state.get("secili_mac_metni"):
        st.session_state["secili_mac_metni"] = secilen_mac_metni
        st.session_state["analiz_yapildi"] = False
        st.rerun()

    secilen_mac_obj = next((m for m in lig_bilgi["maclar"] if m["metin"] == secilen_mac_metni), lig_bilgi["maclar"][0])


# --- SAĞ MENÜ (ANALİZ EKRANI) ---
with col_sag:
    ev_sahibi, deplasman = secilen_mac_obj["ev"], secilen_mac_obj["dep"]
    hakem_adi = secilen_mac_obj["referee"]
    lig_karakteristik = LEAGUE_STYLES.get(secilen_lig, LEAGUE_STYLES["Varsayılan"])
    
    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;background:linear-gradient(135deg,#1e2530 0%,#111827 100%);padding:22px 30px;border-radius:12px;border:1px solid #374151;margin-bottom:20px;">
        <div style="text-align:center;flex:1;"><img src="{secilen_mac_obj['ev_logo']}" height="65" style="margin-bottom:8px;"><h3 style="color:#fff;margin:0;">{ev_sahibi}</h3></div>
        <div style="text-align:center;padding:0 20px;"><div style="color:#9ca3af;">{secilen_lig}</div><h1 style="color:#ef4444;margin:0;">VS</h1><div style="margin-top:5px;"><span style="color:#34d399;font-weight:bold;">📅 {secilen_mac_obj['tarih']}</span> <span style="color:#fbbf24;font-weight:bold;">🕒 {secilen_mac_obj['saat']}</span></div></div>
        <div style="text-align:center;flex:1;"><img src="{secilen_mac_obj['dep_logo']}" height="65" style="margin-bottom:8px;"><h3 style="color:#fff;margin:0;">{deplasman}</h3></div>
    </div>""", unsafe_allow_html=True)

    if st.button("🚀 Seçili Maç İçin V125 Master Mind Analizini Başlat", use_container_width=True, type="primary"):
        with st.spinner(f"{ev_sahibi} - {deplasman} maçı için veriler işleniyor..."):
            d_analiz = tekil_mac_analizi_yap(USER_API_KEY, secilen_mac_obj, lig_karakteristik)
            if d_analiz:
                is_kupa = any(k in secilen_lig.lower() for k in ["kupa", "cup", "pokal", "trophy", "coppa", "copa"])
                h_sira_str, a_sira_str, h_rank_int, a_rank_int = puan_durumu_cek(USER_API_KEY, secilen_mac_obj["l_id"], secilen_mac_obj["season"], secilen_mac_obj["h_id"], secilen_mac_obj["a_id"]) if not is_kupa else ("Kupa Maçı", "Kupa Maçı", 999, 999)
                kadro_verisi = kadro_durumu_ve_getir(USER_API_KEY, secilen_mac_obj["id"], secilen_mac_obj["h_id"], secilen_mac_obj["a_id"])
                
                hakem_profil = hakem_analizi_yap(hakem_adi)
                hava_ad, hava_carpan, hava_detay = hash_tabanli_cevresel_veri(str(secilen_mac_obj["id"]))
                
                ev_deger_raw, ev_deger_str = takim_degeri_hesapla(d_analiz["ev_guc_puani"], d_analiz["ev_data"]["league_coef"])
                dep_deger_raw, dep_deger_str = takim_degeri_hesapla(d_analiz["dep_guc_puani"], d_analiz["dep_data"]["league_coef"])
                
                toplam_xg = d_analiz["ev_xg"] + d_analiz["dep_xg"]
                
                ms_yan = yan_bahisleri_hesapla(toplam_xg, lig_karakteristik, hakem_profil, d_analiz["hoca_ev"], d_analiz["hoca_dep"], 1.0)
                iy_yan = yan_bahisleri_hesapla(toplam_xg, lig_karakteristik, hakem_profil, d_analiz["hoca_ev"], d_analiz["hoca_dep"], 0.45)
                iy2_yan = yan_bahisleri_hesapla(toplam_xg, lig_karakteristik, hakem_profil, d_analiz["hoca_ev"], d_analiz["hoca_dep"], 0.55)
                
                st.session_state["analiz_datasi"] = {
                    "ev_data": d_analiz["ev_data"], "dep_data": d_analiz["dep_data"], "h2h_data": d_analiz["h2h_data"], "sakatlar": d_analiz["sakatlar"],
                    "ev_xg": d_analiz["ev_xg"], "dep_xg": d_analiz["dep_xg"], "ev_guc_puani": d_analiz["ev_guc_puani"], "dep_guc_puani": d_analiz["dep_guc_puani"],
                    "ev_deger_str": ev_deger_str, "dep_deger_str": dep_deger_str, "ev_deger_raw": ev_deger_raw, "dep_deger_raw": dep_deger_raw, 
                    "h_sira_str": h_sira_str, "a_sira_str": a_sira_str, "h_rank_int": h_rank_int, "a_rank_int": a_rank_int,
                    "kadro_resmi": kadro_verisi["resmi"], "h_kadro": kadro_verisi["h_kadro"], "a_kadro": kadro_verisi["a_kadro"],
                    "hakem_profil": hakem_profil, "hoca_ev": d_analiz["hoca_ev"], "hoca_dep": d_analiz["hoca_dep"], "hava_ad": hava_ad, "hava_detay": hava_detay,
                    "ms_m": d_analiz["ms_m"], "iy_m": d_analiz["iy_m"], "iy2_m": d_analiz["iy2_m"], 
                    "ms_yan": ms_yan, "iy_yan": iy_yan, "iy2_yan": iy2_yan
                }
                st.session_state["analiz_yapildi"] = True

    # SEKMELER
    tab_genel, tab_iy, tab_ikinci_yari, tab_ms, tab_value, tab_top_value, tab_surpriz = st.tabs([
        "🎯 Genel Rapor", "⏱️ 1. Yarı", "⏱️ 2. Yarı", "🏆 Maç Sonu", 
        "💎 Value Bahis", "🌟 Tüm Ligler Top Value", "🔮 Sürpriz Tahminler"
    ])

    with tab_genel:
        if st.session_state.get("analiz_yapildi", False):
            d = st.session_state["analiz_datasi"]
            ev_d, dep_d = d["ev_data"], d["dep_data"]
            ms = d["ms_m"]

            st.markdown(f"""
            <div style="background: #111827; padding: 20px; border-radius: 8px; border: 1px solid #1e3a8a; text-align: center; margin-top: 15px; margin-bottom: 25px;">
                <span style="color: #9ca3af; font-size: 14px; font-weight: bold;">🎯 GERÇEK VERİLİ YZ MAÇ SONU SKOR TAHMİNİ</span>
                <div style="font-size: 36px; font-weight: 900; color: #34d399; margin-top: 5px;">{ms['skor']}</div>
                <div style="font-size: 13px; color: #60a5fa; margin-top: 5px;">(Taraf İhtimali: 1: %{ms['p1']*100:.0f} | X: %{ms['pX']*100:.0f} | 2: %{ms['p2']*100:.0f})</div>
            </div>
            """, unsafe_allow_html=True)
            
            kadro_etiket = "✅ RESMİ İLK 11'LER AÇIKLANDI" if d['kadro_resmi'] else "⚠️ TAHMİNİ İLK 11 (Son Maç Kadrosu)"
            kadro_renk = "#34d399" if d['kadro_resmi'] else "#fbbf24"
            h_kadro_txt = ", ".join(d['h_kadro']) if d['h_kadro'] else "Veri Yok"
            a_kadro_txt = ", ".join(d['a_kadro']) if d['a_kadro'] else "Veri Yok"

            h_rank, a_rank = d['h_rank_int'], d['a_rank_int']
            h_rank_c = "#34d399" if h_rank < a_rank else ("#ef4444" if h_rank > a_rank else "#fff")
            a_rank_c = "#34d399" if a_rank < h_rank else ("#ef4444" if a_rank > h_rank else "#fff")
            sir_yaris = " <span style='font-size:11.5px; color:#fbbf24;'>(🏆 Sıralama Yarışında)</span>" if h_rank != 999 else ""

            ev_v, dep_v = d['ev_deger_raw'], d['dep_deger_raw']
            h_val_c = "#34d399" if ev_v > dep_v else ("#ef4444" if ev_v < dep_v else "#fff")
            a_val_c = "#34d399" if dep_v > ev_v else ("#ef4444" if dep_v < ev_v else "#fff")
            
            st.markdown("### 📋 Taktik ve İstihbarat")
            html_taktik = f"""
            <div style="background-color: #111827; border-radius: 8px; border: 1px solid {kadro_renk}; padding: 15px; margin-bottom: 20px;">
                <div style="text-align: center; margin-bottom: 12px;"><b style="color: {kadro_renk}; font-size: 15px;">{kadro_etiket}</b></div>
                <div style="display: flex; gap: 20px; text-align: left; font-size: 13px; color: #9ca3af;">
                    <div style="flex: 1;"><b style="color: #60a5fa;">🏠 {ev_sahibi} İlk 11:</b><br> {h_kadro_txt}</div>
                    <div style="flex: 1;"><b style="color: #ef4444;">✈️ {deplasman} İlk 11:</b><br> {a_kadro_txt}</div>
                </div>
            </div>
            
            <div style="display: flex; gap: 15px; margin-bottom: 25px;">
                <div style="flex: 1; background-color: #1e293b; border-radius: 8px; padding: 15px; border-left: 4px solid #60a5fa;">
                    <h4 style="color: #60a5fa; margin-top: 0;">🏠 {ev_sahibi}</h4>
                    <p style="color: #fff; font-size: 14px; margin: 5px 0;"><b>Sıralama:</b> <span style="color: {h_rank_c}; font-weight:bold;">{d['h_sira_str']}</span>{sir_yaris}</p>
                    <p style="color: #fff; font-size: 14px; margin: 5px 0;"><b>Kadro Değeri:</b> <span style="color: {h_val_c}; font-weight:bold;">{d['ev_deger_str']}</span> (Tahmini)</p>
                    <p style="color: {d['hoca_ev']['renk']}; font-size: 14px; margin: 5px 0;"><b>Oyun Tarzı:</b> {d['hoca_ev']['profil']}</p>
                    <p style="color: #fff; font-size: 14px; margin: 5px 0;"><b>Diziliş:</b> {d['hoca_ev']['dizilis']}</p>
                </div>
                <div style="flex: 1; background-color: #1e293b; border-radius: 8px; padding: 15px; border-left: 4px solid #ef4444;">
                    <h4 style="color: #ef4444; margin-top: 0;">✈️ {deplasman}</h4>
                    <p style="color: #fff; font-size: 14px; margin: 5px 0;"><b>Sıralama:</b> <span style="color: {a_rank_c}; font-weight:bold;">{d['a_sira_str']}</span>{sir_yaris}</p>
                    <p style="color: #fff; font-size: 14px; margin: 5px 0;"><b>Kadro Değeri:</b> <span style="color: {a_val_c}; font-weight:bold;">{d['dep_deger_str']}</span> (Tahmini)</p>
                    <p style="color: {d['hoca_dep']['renk']}; font-size: 14px; margin: 5px 0;"><b>Oyun Tarzı:</b> {d['hoca_dep']['profil']}</p>
                    <p style="color: #fff; font-size: 14px; margin: 5px 0;"><b>Diziliş:</b> {d['hoca_dep']['dizilis']}</p>
                </div>
            </div>
            """
            st.markdown(html_taktik, unsafe_allow_html=True)
            
            c_alt1, c_alt2, c_alt3 = st.columns(3)
            with c_alt1: st.markdown(f"""<div style="border:1px solid #374151;border-radius:8px;padding:10px;text-align:center;background:#111827;"><span style="color:#9ca3af;font-size:12px;">🏟️ Stadyum</span><br><b style="color:#fff;">{secilen_mac_obj['venue']}</b></div>""", unsafe_allow_html=True)
            with c_alt2: st.markdown(f"""<div style="border:1px solid #374151;border-radius:8px;padding:10px;text-align:center;background:#111827;"><span style="color:#9ca3af;font-size:12px;">👮 Hakem</span><br><b style="color:#fff;">{hakem_adi}</b></div>""", unsafe_allow_html=True)
            with c_alt3: st.markdown(f"""<div style="border:1px solid #374151;border-radius:8px;padding:10px;text-align:center;background:#111827;"><span style="color:#9ca3af;font-size:12px;">🌤️ Hava Durumu</span><br><b style="color:#fff;">{d['hava_ad']}</b></div>""", unsafe_allow_html=True)
            
            st.write("")
            h_eksik_str = ', '.join(d['sakatlar']['h_onemli']) if d['sakatlar']['h_onemli'] else 'Yok'
            a_eksik_str = ', '.join(d['sakatlar']['a_onemli']) if d['sakatlar']['a_onemli'] else 'Yok'
            st.markdown(f"""
            <div style="background-color: #111827; border-radius: 8px; padding: 15px; border: 1px solid #ef4444; margin-bottom: 25px;">
                <h4 style="color: #ef4444; margin-top: 0; margin-bottom: 10px;">🚑 Sakat/Cezalı Raporu</h4>
                <p style="color: #ffffff; font-size: 14px; margin: 5px 0;"><b>{ev_sahibi}:</b> {h_eksik_str}</p>
                <p style="color: #ffffff; font-size: 14px; margin: 5px 0;"><b>{deplasman}:</b> {a_eksik_str}</p>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("### ⚔️ İstatistik Karşılaştırması")
            html_icerik = [
                f'<div style="background-color: #111827; border-radius: 8px; padding: 15px; border: 1px solid #1e3a8a;">',
                f'<div style="display: flex; justify-content: space-between; border-bottom: 2px solid #3b82f6; padding-bottom: 10px; margin-bottom: 10px;">',
                f'<div style="width: 33%; text-align: center; color: #60a5fa; font-size: 16px; font-weight: bold;">{ev_sahibi}</div>',
                f'<div style="width: 34%; text-align: center; color: #9ca3af; font-size: 14px;">Parametre</div>',
                f'<div style="width: 33%; text-align: center; color: #60a5fa; font-size: 16px; font-weight: bold;">{deplasman}</div>',
                f'</div>',
                satir_olustur("V125 Güç Puanı", d["ev_guc_puani"], d["dep_guc_puani"]),
                satir_olustur("Tahmini Gol Beklentisi (Hücum Gücü)", d["ev_xg"], d["dep_xg"]),
                satir_olustur("Ağırlıklı Atılan Gol", ev_d["g_for_genel"], dep_d["g_for_genel"]),
                satir_olustur("Ağırlıklı Yenilen Gol", ev_d["g_ag_genel"], dep_d["g_ag_genel"], ters_oran=True),
                satir_olustur("Eksik Oyuncu Etki Puanı", d["sakatlar"]["h_agirlik"], d["sakatlar"]["a_agirlik"], ters_oran=True),
                satir_olustur("Dinlenme Günü (Yorgunluk)", ev_d["dinlenme_gunu"], dep_d["dinlenme_gunu"]),
                f'</div>'
            ]
            st.markdown("".join(html_icerik), unsafe_allow_html=True)
        else:
            st.info("👆 Seçili maçın verilerini görmek için yukarıdaki 'V125 Master Mind Analizini Başlat' butonuna tıklayın.")

    with tab_iy:
        if st.session_state.get("analiz_yapildi", False):
            render_taktik_kutu("1. Yarı", st.session_state["analiz_datasi"]["iy_m"], st.session_state["analiz_datasi"]["iy_yan"], ev_sahibi, deplasman)
        else:
            st.info("👆 Seçili maçın verilerini görmek için yukarıdaki 'V125 Master Mind Analizini Başlat' butonuna tıklayın.")

    with tab_ikinci_yari:
        if st.session_state.get("analiz_yapildi", False):
            render_taktik_kutu("2. Yarı", st.session_state["analiz_datasi"]["iy2_m"], st.session_state["analiz_datasi"]["iy2_yan"], ev_sahibi, deplasman)
        else:
            st.info("👆 Seçili maçın verilerini görmek için yukarıdaki 'V125 Master Mind Analizini Başlat' butonuna tıklayın.")

    with tab_ms:
        if st.session_state.get("analiz_yapildi", False):
            m = st.session_state["analiz_datasi"]["ms_m"]
            render_taktik_kutu("Maç Sonu", m, st.session_state["analiz_datasi"]["ms_yan"], ev_sahibi, deplasman)
            
            st.markdown("### 🔥 Skor Olasılık Matrisi (Heatmap)")
            heatmap_html = '<table style="width:100%; text-align:center; border-collapse: collapse; background-color:#111827; border: 1px solid #374151; font-size: 14px;">'
            heatmap_html += '<tr><th style="padding:10px; border: 1px solid #374151; color:#9ca3af;">Ev \ Dep</th>'
            for j in range(6): heatmap_html += f'<th style="padding:10px; border: 1px solid #374151; color:#60a5fa;">{j}</th>'
            heatmap_html += '</tr>'
            for i in range(6):
                heatmap_html += f'<tr><td style="padding:10px; border: 1px solid #374151; color:#60a5fa; font-weight:bold;">{i}</td>'
                for j in range(6):
                    prob = m['matris'][i][j] * 100
                    bg_color = f"rgba(52, 211, 153, {min(prob/15, 0.8)})" if prob > 2.0 else "rgba(31, 41, 55, 0.5)"
                    text_color = "#ffffff" if prob > 2.0 else "#6b7280"
                    heatmap_html += f'<td style="padding:10px; border: 1px solid #374151; background-color:{bg_color}; color:{text_color};">%{prob:.1f}</td>'
                heatmap_html += '</tr>'
            heatmap_html += '</table>'
            st.markdown(heatmap_html, unsafe_allow_html=True)
        else:
            st.info("👆 Seçili maçın verilerini görmek için yukarıdaki 'V125 Master Mind Analizini Başlat' butonuna tıklayın.")

    with tab_value:
        if st.session_state.get("analiz_yapildi", False):
            m = st.session_state["analiz_datasi"]["ms_m"]
            secenekler = []
            if m['p1'] > 0.55: secenekler.append({"bahis": f"MS 1 ({ev_sahibi})", "ihtimal": m['p1']})
            elif m['p2'] > 0.50: secenekler.append({"bahis": f"MS 2 ({deplasman})", "ihtimal": m['p2']})
            if m['ust_35'] > 0.45: secenekler.append({"bahis": "3.5 Gol Üstü", "ihtimal": m['ust_35']})
            elif m['ust_25'] > 0.55: secenekler.append({"bahis": "2.5 Gol Üstü", "ihtimal": m['ust_25']})
            elif (1 - m['ust_25']) > 0.65: secenekler.append({"bahis": "2.5 Gol Altı", "ihtimal": (1 - m['ust_25'])})
            if m['kg_var'] > 0.60: secenekler.append({"bahis": "Karşılıklı Gol Var", "ihtimal": m['kg_var']})
            
            if secenekler:
                secenekler.sort(key=lambda x: x["ihtimal"], reverse=True)
                en_iyi = secenekler[0]
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #065f46 0%, #047857 100%); padding: 25px; border-radius: 12px; border: 2px solid #34d399; margin-bottom: 20px;">
                    <h2 style="color: #ffffff; margin: 0 0 10px 0;">🎯 V125 En İyi Seçim: {en_iyi['bahis']}</h2>
                    <p style="color: #e5e7eb; font-size: 15px; margin: 0;"><b>Kazanma İhtimali:</b> %{en_iyi['ihtimal']*100:.1f}</p>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("### 🏦 Kelly Kriteri İle Kasa Yönetimi")
                c_k1, c_k2 = st.columns(2)
                with c_k1: kasa = st.number_input("Mevcut Kasanız (Örn: 1000 TL)", min_value=10.0, value=1000.0, step=100.0)
                with c_k2: oran = st.number_input(f"Büronun '{en_iyi['bahis']}' İçin Verdiği Oran", min_value=1.01, value=1.80, step=0.05)
                
                edge = (en_iyi['ihtimal'] * oran) - 1
                if edge > 0:
                    guvenli_kelly = (edge / (oran - 1)) * 0.5
                    st.success(f"**Value (Değer) Tespit Edildi!** Matematiksel Avantajınız: +{edge:.2f}")
                    st.info(f"💡 **Güvenli Kelly Tavsiyesi:** Bu maça kasadaki paranızın **%{guvenli_kelly*100:.1f}** kadarını, yani **{kasa * guvenli_kelly:.2f} TL** basmanız uzun vadede kasayı koruyarak büyütmek için idealdir.")
                else:
                    st.error("⚠️ Seçilen oran için matematiksel bir avantaj (Value/Edge) bulunamadı. Oran çok düşük kalmış.")
            else:
                st.warning("⚠️ Güvenilir bir bahis bulunamadı.")
        else:
            st.info("👆 Seçili maçın verilerini görmek için yukarıdaki 'V125 Master Mind Analizini Başlat' butonuna tıklayın.")
                
    # --- TÜM LİGLER GLOBAL TOP VALUE ---
    with tab_top_value:
        st.markdown("### 🏆 Hızlı Tarama: Sadece Profesyonel Ana Ligler ve 2. Ligler")
        st.info("Bu araç; Premier Lig, La Liga, Serie A, Süper Lig gibi majör ligler ve onların 2. liglerine odaklanarak hızlandırılmış bir tarama yapar.")
        
        if st.button("🔍 Seçkin Liglerde Fırsatları Tara", key="btn_scan_all_value"):
            with st.spinner("Beyaz listedeki ana ve 2. ligler taranıyor. İşlem saniyeler içinde tamamlanacak..."):
                tum_maclar_listesi = []
                sirali_ligler_keys = ligleri_sirala(list(bulten_verisi.keys()))
                
                # SADECE BELİRLENEN KALİTELİ LİGLERİ İÇERİ AL
                for l_adi in sirali_ligler_keys:
                    l_adi_kucuk = l_adi.lower()
                    
                    # Beyaz listedeki ana lig/2. lig mi?
                    if not any(kriter in l_adi_kucuk for kriter in HIZLI_TARAMA_LIGLERI):
                        continue
                        
                    # İsmi benzese de U19, kadın veya amatörleri kesin olarak dışla
                    if any(x in l_adi_kucuk for x in ["u19", "u21", "u20", "u23", "women", "kadınlar", "reserve", "amateur", "gençler", "paf", "youth"]):
                        continue
                        
                    tum_maclar_listesi.extend(bulten_verisi[l_adi]["maclar"])
                
                firsatlar = []
                
                if not tum_maclar_listesi:
                    st.warning("Şu anki bültende belirlediğimiz elit liglerden maç bulunmamaktadır.")
                else:
                    progress_bar_val = st.progress(0)
                    for idx, m_obj in enumerate(tum_maclar_listesi):
                        m_analiz = tekil_mac_analizi_yap(USER_API_KEY, m_obj, lig_karakteristik)
                        progress_bar_val.progress((idx + 1) / len(tum_maclar_listesi))
                        
                        if m_analiz and m_analiz["en_iyi_bahis"]["bahis"] != "Yok":
                            firsatlar.append({
                                "mac": f"{m_obj['ev']} - {m_obj['dep']}",
                                "lig": [k for k, v in bulten_verisi.items() if m_obj in v["maclar"]][0],
                                "saat": m_obj['saat'],
                                "bahis": m_analiz["en_iyi_bahis"]["bahis"],
                                "ihtimal": m_analiz["en_iyi_bahis"]["ihtimal"]
                            })
                            
                    if firsatlar:
                        firsatlar = sorted(firsatlar, key=lambda x: x["ihtimal"], reverse=True)
                        st.success(f"🚀 Hızlı Tarama Tamamlandı! {len(tum_maclar_listesi)} elit maç arasından çıkan en güçlü tahminler:")
                        for idx, f in enumerate(firsatlar[:15]): 
                            st.markdown(f"**{idx+1}. {f['mac']}** <span style='font-size:12px; color:#9ca3af;'>({f['lig']} - 🕒 {f['saat']})</span> ➔ **{f['bahis']}** (İhtimal: <span style='color:#34d399;'>%{f['ihtimal']*100:.1f}</span>)", unsafe_allow_html=True)
                    else:
                        st.warning("Taranan elit liglerde değerlendirmeye uygun güçlü bir bahis bulunamadı.")
                    
    # --- SÜRPRİZ TAHMİNLER ---
    with tab_surpriz:
        st.markdown("### 🔮 Hızlı Tarama: Sürpriz Tahmin Avcısı")
        st.info("Sadece 1. ve 2. profesyonel ligleri baz alarak; 1'den 2, 2'den 1, İlk Yarı KG Var ve 6+ Gol gibi yüksek oranlı ihtimalleri hesaplar.")
        
        if st.button("🔍 Sürprizleri Tara", key="btn_scan_surpriz"):
            with st.spinner("Seçkin ligler üzerinden sürpriz matrisleri oluşturuluyor..."):
                tum_maclar_listesi = []
                sirali_ligler_keys = ligleri_sirala(list(bulten_verisi.keys()))
                
                # SADECE BEYAZ LİSTE FİLTRESİ
                for l_adi in sirali_ligler_keys:
                    l_adi_kucuk = l_adi.lower()
                    if not any(kriter in l_adi_kucuk for kriter in HIZLI_TARAMA_LIGLERI):
                        continue
                    if any(x in l_adi_kucuk for x in ["u19", "u21", "u20", "u23", "women", "kadınlar", "reserve", "amateur", "gençler", "paf", "youth"]):
                        continue
                    tum_maclar_listesi.extend(bulten_verisi[l_adi]["maclar"])
                
                if not tum_maclar_listesi:
                    st.warning("Şu anki bültende belirlediğimiz elit liglerden maç bulunmamaktadır.")
                else:
                    liste_1_2 = []
                    liste_2_1 = []
                    liste_iy_kg = []
                    liste_ust_55 = []
                    
                    progress_bar = st.progress(0)
                    
                    for idx, m_obj in enumerate(tum_maclar_listesi):
                        m_analiz = tekil_mac_analizi_yap(USER_API_KEY, m_obj, lig_karakteristik)
                        progress_bar.progress((idx + 1) / len(tum_maclar_listesi))
                        
                        if m_analiz:
                            mac_adi = f"{m_obj['ev']} - {m_obj['dep']}"
                            lig_adi = [k for k, v in bulten_verisi.items() if m_obj in v["maclar"]][0]
                            s = m_analiz["surprizler"]
                            
                            if s["1/2"] > 0.02:
                                liste_1_2.append({"mac": mac_adi, "lig": lig_adi, "saat": m_obj['saat'], "oran": s["1/2"]})
                            if s["2/1"] > 0.02:
                                liste_2_1.append({"mac": mac_adi, "lig": lig_adi, "saat": m_obj['saat'], "oran": s["2/1"]})
                            if s["iy_kg"] > 0.35:
                                liste_iy_kg.append({"mac": mac_adi, "lig": lig_adi, "saat": m_obj['saat'], "oran": s["iy_kg"]})
                            if s["ust_55"] > 0.08:
                                liste_ust_55.append({"mac": mac_adi, "lig": lig_adi, "saat": m_obj['saat'], "oran": s["ust_55"]})
                                
                    st.success(f"🚀 Sürpriz Taraması Tamamlandı! {len(tum_maclar_listesi)} elit maç içinden en yüksek potansiyelliler:")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("#### 🔄 1'den 2 (İlk Yarı 1 / Maç Sonu 2)")
                        liste_1_2.sort(key=lambda x: x["oran"], reverse=True)
                        for f in liste_1_2[:5]:
                            st.markdown(f"**{f['mac']}** <span style='font-size:11px;color:#9ca3af;'>({f['lig']})</span> ➔ İhtimal: <span style='color:#fbbf24;'>%{f['oran']*100:.1f}</span>", unsafe_allow_html=True)
                        if not liste_1_2: st.write("Kriterlere uygun maç bulunamadı.")
                        
                        st.markdown("#### 🔄 2'den 1 (İlk Yarı 2 / Maç Sonu 1)")
                        liste_2_1.sort(key=lambda x: x["oran"], reverse=True)
                        for f in liste_2_1[:5]:
                            st.markdown(f"**{f['mac']}** <span style='font-size:11px;color:#9ca3af;'>({f['lig']})</span> ➔ İhtimal: <span style='color:#fbbf24;'>%{f['oran']*100:.1f}</span>", unsafe_allow_html=True)
                        if not liste_2_1: st.write("Kriterlere uygun maç bulunamadı.")
                        
                    with col2:
                        st.markdown("#### ⚽ İY Karşılıklı Gol Var")
                        liste_iy_kg.sort(key=lambda x: x["oran"], reverse=True)
                        for f in liste_iy_kg[:5]:
                            st.markdown(f"**{f['mac']}** <span style='font-size:11px;color:#9ca3af;'>({f['lig']})</span> ➔ İhtimal: <span style='color:#34d399;'>%{f['oran']*100:.1f}</span>", unsafe_allow_html=True)
                        if not liste_iy_kg: st.write("Kriterlere uygun maç bulunamadı.")
                        
                        st.markdown("#### 🚀 6+ Gol (5.5 Üst)")
                        liste_ust_55.sort(key=lambda x: x["oran"], reverse=True)
                        for f in liste_ust_55[:5]:
                            st.markdown(f"**{f['mac']}** <span style='font-size:11px;color:#9ca3af;'>({f['lig']})</span> ➔ İhtimal: <span style='color:#ef4444;'>%{f['oran']*100:.1f}</span>", unsafe_allow_html=True)
                        if not liste_ust_55: st.write("Kriterlere uygun maç bulunamadı.")
