"""
TOOL_import_vieux_evenements_Serge_DURAND.py
============================================
Import en une seule passe de TOUS les événements iMFR
depuis le début de l'année scolaire jusqu'à aujourd'hui.

Les événements sont fusionnés dans calendar_state.json
au même format que calendar_agent_console_v5_6.py.

Dépendance supplémentaire :
    pip install beautifulsoup4

Configuration :
    Éditer TOOL_import_session_Serge_DURAND.json avec les valeurs copiées depuis
    Chrome DevTools → Application → Cookies → uzes.imfr.fr
    (les cookies expirent à la fermeture du navigateur ;
     si le script échoue avec des erreurs 403/401,
     recopier les valeurs fraîches depuis Chrome)
"""

import json
import datetime
import time
import logging
import re
import sys

import pytz
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[{asctime}] {message}",
    style="{",
    datefmt="%H:%M:%S"
)

# ---------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------
PLANNING_URL = "https://uzes.imfr.fr/V2/iplanning/monplanning/version_affichage"
STATE_FILE   = "stats_history.json"
SESSION_FILE = "TOOL_import_session_Serge_DURAND.json"
TIMEZONE     = pytz.timezone("Europe/Paris")

DELAY_BETWEEN_REQUESTS = 1.5   # secondes entre chaque requête (soyez polis)

# ---------------------------------------------------------------------
# Chargement de la configuration de session
# ---------------------------------------------------------------------
try:
    with open(SESSION_FILE, "r", encoding="utf-8") as f:
        SESSION = json.load(f)
except FileNotFoundError:
    logging.error(f"Fichier {SESSION_FILE} introuvable. Créez-le d'abord.")
    sys.exit(1)

COOKIE_IMFR    = SESSION["cookie_imfr"]
COOKIE_CSRF    = SESSION["cookie_csrf"]
S_ID_FORMATEUR = int(SESSION["s_id_formateur"])
CAL_NAME       = SESSION["cal_name"]
START_DATE     = datetime.date.fromisoformat(SESSION["start_date"])

# ---------------------------------------------------------------------
# Session HTTP
# ---------------------------------------------------------------------
http = requests.Session()
http.cookies.set("imfr",       COOKIE_IMFR,  domain="uzes.imfr.fr")
http.cookies.set("CSRF_igesti", COOKIE_CSRF,  domain="uzes.imfr.fr")
http.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Referer"   : "https://uzes.imfr.fr/V2/iplanning/monplanning/",
})

# ---------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------
def minutes_to_dt(date: datetime.date, minutes: int) -> datetime.datetime:
    """Convertit des minutes depuis minuit en datetime localisé."""
    dt = datetime.datetime.combine(date, datetime.time.min) + datetime.timedelta(minutes=minutes)
    return TIMEZONE.localize(dt)

def load_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        logging.warning(f"Lecture {STATE_FILE} échouée ({e}), on repart de zéro")
        return {}

def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------------------
# Requête vers iMFR
# ---------------------------------------------------------------------
def fetch_week(date_jour: datetime.date) -> str | None:
    """
    Envoie le POST pour la semaine contenant date_jour.
    Retourne le HTML brut, ou None en cas d'erreur.
    """
    payload = {
        "hauteur_scroll"  : "436",
        "version_affichage": "4",
        "version_mobile"  : "0",
        "s_id_formateur"  : str(S_ID_FORMATEUR),
        "date_jour"       : date_jour.isoformat(),
        "version_pdf"     : "0",
        "CSRF_igesti_token": COOKIE_CSRF,
    }
    try:
        resp = http.post(PLANNING_URL, data=payload, timeout=20)
        if resp.status_code == 200:
            return resp.text
        logging.warning(f"  HTTP {resp.status_code} pour {date_jour}")
        return None
    except Exception as e:
        logging.warning(f"  Erreur réseau pour {date_jour} : {e}")
        return None

# ---------------------------------------------------------------------
# Parsing HTML
# ---------------------------------------------------------------------
_DIV_ID_RE        = re.compile(r'^MONPLANNING_imperatif_(\d+)$')
_DIV_TTJOURNEE_RE = re.compile(r'^MONPLANNING_imperatif_ttjournee_(\d+)$')
_JOUR_CLASS_RE    = re.compile(r'monplanning_jour_(\d+)_journee')

def _ttjournee_date(div, week_start: datetime.date) -> datetime.date | None:
    """
    Remonte les ancêtres du div ttjournee pour trouver la class
    'monplanning_jour_N_journee' (N=1→lundi, N=2→mardi, …, N=5→vendredi).
    Retourne la date correspondante, ou None si introuvable.
    """
    ancestor = div.parent
    depth = 0
    while ancestor and ancestor.name and depth < 8:
        classes = ancestor.get("class") or []
        if isinstance(classes, str):
            classes = [classes]
        for cls in classes:
            m = _JOUR_CLASS_RE.match(cls)
            if m:
                day_num = int(m.group(1))   # 1 = lundi, 2 = mardi, …
                return week_start + datetime.timedelta(days=day_num - 1)
        ancestor = ancestor.parent
        depth += 1
    return None


def _extract_event(soup: "BeautifulSoup", div, is_ttjournee: bool,
                   week_start: datetime.date | None = None) -> tuple | None:
    """
    Extrait un événement depuis un div MONPLANNING_imperatif_* ou _ttjournee_*.
    Retourne (key, event_dict) ou None si on doit ignorer ce div.
    """
    div_id  = div["id"]
    imfr_id = div.get("data-id", "")

    if is_ttjournee:
        # La date n'est pas dans les attributs du div — on la déduit de l'ancêtre
        if week_start is None:
            return None
        event_date = _ttjournee_date(div, week_start)
        if event_date is None:
            logging.debug(f"  {div_id} : impossible de déterminer la date")
            return None
        date_str = event_date.isoformat()
    else:
        date_str = div.get("data-jour", "")
        if not date_str:
            return None
        event_date = datetime.date.fromisoformat(date_str)

    if is_ttjournee:
        # Les événements ttjournee (Serv : Midi, Serv : Soir, etc.) sont tout-jour
        # On les stocke comme événements tout-jour (00:00–23:59) ;
        # la durée réelle est gérée par _DURATION_OVERRIDES dans statistiques_v15.py
        start_dt = TIMEZONE.localize(
            datetime.datetime.combine(event_date, datetime.time(0, 0))
        )
        end_dt = TIMEZONE.localize(
            datetime.datetime.combine(event_date, datetime.time(23, 59))
        )
        # Le titre est dans un div enfant avec class contenant "monplanning_imperatif_calque"
        calque = div.find("div", class_=re.compile(r'monplanning_imperatif_calque'))
        if calque:
            summary = calque.get_text(" ", strip=True)
        else:
            summary = div.get_text(" ", strip=True)
        summary = re.sub(r'\s+', ' ', summary).strip()
        # Supprimer le préfixe "NomFormateur • " ajouté par iMFR dans le texte du calque
        if " • " in summary:
            summary = summary.split(" • ", 1)[1].strip()
        description = ""
        # data-id vaut souvent "0" pour tous les ttjournee → on construit un uid
        # unique à partir de la date + le titre normalisé pour éviter les collisions
        # (ex. Serv:Midi et Serv:Soir le même jour)
        safe_summary = re.sub(r'[^a-zA-Z0-9]', '_', summary)
        imfr_id = f"ttj_{date_str}_{safe_summary}"
    else:
        min_debut = int(div.get("data-min_debut", 0))
        min_fin   = int(div.get("data-min_fin", 0))
        all_day   = div.get("data-toutelajournee", "0") == "1"

        if all_day:
            start_dt = TIMEZONE.localize(
                datetime.datetime.combine(event_date, datetime.time(0, 0))
            )
            end_dt = TIMEZONE.localize(
                datetime.datetime.combine(event_date, datetime.time(23, 59))
            )
        else:
            start_dt = minutes_to_dt(event_date, min_debut)
            end_dt   = minutes_to_dt(event_date, min_fin)

        # Titre de l'événement
        motif_div = soup.find(id=f"{div_id}_motif")
        summary   = motif_div.get_text(" ", strip=True) if motif_div else ""
        summary   = re.sub(r'\s+', ' ', summary).strip()

        # Description (observations)
        obs_div     = soup.find(id=f"{div_id}_obs")
        description = obs_div.get_text(" ", strip=True) if obs_div else ""
        description = re.sub(r'\s+', ' ', description).strip()

    uid = f"imfr_{imfr_id}"
    key = f"{uid}_{start_dt.isoformat()}"

    return key, {
        "uid"        : uid,
        "summary"    : summary,
        "description": description,
        "start_iso"  : start_dt.isoformat(),
        "end_iso"    : end_dt.isoformat(),
    }


def parse_week(html: str, week_start: datetime.date) -> dict:
    """
    Extrait les événements du HTML d'une semaine.
    Retourne un dict {event_key: event_dict} au format calendar_state.json.
    """
    soup   = BeautifulSoup(html, "html.parser")
    events = {}

    # Événements normaux (cours, RDV, etc.)
    for div in soup.find_all("div", id=_DIV_ID_RE):
        try:
            result = _extract_event(soup, div, is_ttjournee=False)
            if result:
                key, ev = result
                events[key] = ev
        except Exception as e:
            logging.debug(f"  Skip {div['id']} : {e}")

    # Événements tout-jour (Serv : Midi, Serv : Soir, etc.)
    for div in soup.find_all("div", id=_DIV_TTJOURNEE_RE):
        try:
            result = _extract_event(soup, div, is_ttjournee=True, week_start=week_start)
            if result:
                key, ev = result
                events[key] = ev
                logging.info(f"  → ttjournee : {ev['summary']}  ({ev['start_iso'][:10]})")
        except Exception as e:
            logging.warning(f"  Skip ttjournee {div['id']} : {e}")

    return events

# ---------------------------------------------------------------------
# Boucle principale
# ---------------------------------------------------------------------
def main():
    today      = datetime.date.today()
    state      = load_state()
    cal_events = state.get(CAL_NAME, {})

    existing   = len(cal_events)
    total_new  = 0
    total_seen = 0

    # Itère semaine par semaine (lundi de chaque semaine)
    # On commence au lundi de la semaine contenant start_date
    current = START_DATE - datetime.timedelta(days=START_DATE.weekday())
    weeks   = []
    while current <= today:
        weeks.append(current)
        current += datetime.timedelta(weeks=1)

    logging.info(f"Import iMFR pour {CAL_NAME}")
    logging.info(f"Période : {START_DATE} → {today}  ({len(weeks)} semaines)")
    logging.info(f"Événements déjà stockés : {existing}")
    logging.info("-" * 50)

    # ------------------------------------------------------------------
    # Vérification de session sur la 1ère semaine avant de tout lancer
    # ------------------------------------------------------------------
    logging.info("Vérification de la session iMFR ...")
    test_html = fetch_week(weeks[0])
    if test_html is None:
        logging.error("Impossible de joindre le serveur. Vérifiez votre connexion.")
        sys.exit(1)
    if "MONPLANNING_imperatif" not in test_html and "MONPLANNING_planning_tmp" not in test_html:
        logging.error(
            "La session iMFR est expirée ou invalide.\n"
            "  → Ouvrez Chrome, reconnectez-vous sur uzes.imfr.fr\n"
            "  → Copiez les nouvelles valeurs des cookies 'imfr' et 'CSRF_igesti'\n"
            "  → Mettez à jour TOOL_import_session_Serge_DURAND.json\n"
            "  → Relancez ce script"
        )
        sys.exit(1)
    logging.info("Session valide. Démarrage de l'import ...")
    logging.info("-" * 50)

    for i, week_start in enumerate(weeks, 1):
        date_label = week_start.strftime("%d/%m/%Y")
        logging.info(f"Semaine {i:>2}/{len(weeks)}  ({date_label}) ...")

        if i == 1:
            html = test_html  # déjà récupéré pour la vérification
        else:
            html = fetch_week(week_start)

        if html is None:
            logging.warning(f"  → échec réseau, semaine ignorée")
            time.sleep(DELAY_BETWEEN_REQUESTS)
            continue

        # Détection session expirée en cours de route
        if "MONPLANNING_imperatif" not in html and "MONPLANNING_planning_tmp" not in html:
            logging.error(
                f"Session expirée à la semaine {i}. "
                f"Relancez le script avec des cookies frais. "
                f"Les {total_new} événements déjà importés sont sauvegardés."
            )
            state[CAL_NAME] = cal_events
            save_state(state)
            sys.exit(1)

        week_events = parse_week(html, week_start)
        total_seen += len(week_events)

        nb_new = 0
        for key, ev in week_events.items():
            if key not in cal_events:
                cal_events[key] = ev
                nb_new += 1
        total_new += nb_new

        logging.info(f"  → {len(week_events)} événements trouvés, {nb_new} nouveaux")

        # Sauvegarde intermédiaire toutes les 5 semaines
        if i % 5 == 0:
            state[CAL_NAME] = cal_events
            save_state(state)
            logging.info(f"  [sauvegarde intermédiaire — {len(cal_events)} événements au total]")

        time.sleep(DELAY_BETWEEN_REQUESTS)

    # Sauvegarde finale
    state[CAL_NAME] = cal_events
    save_state(state)

    logging.info("-" * 50)
    logging.info(f"Terminé.")
    logging.info(f"  Événements trouvés sur iMFR   : {total_seen}")
    logging.info(f"  Nouveaux ajoutés au state     : {total_new}")
    logging.info(f"  Total dans calendar_state.json : {len(cal_events)}")
    logging.info(f"")
    logging.info(f"Vous pouvez maintenant lancer calendar_agent_console_v5_6.py")

# ---------------------------------------------------------------------
if __name__ == "__main__":
    main()
