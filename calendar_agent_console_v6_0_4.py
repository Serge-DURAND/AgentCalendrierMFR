# =====================================================================
# Historique des versions
#
# v1.0  : Version initiale
# v1.1  : Ajout d'un fichier config.json pour gérer les paramètres
# v1.5  : Ajout du mécanisme de double-cycle pour confirmer les suppressions
# v1.6  : Correction bug de normalisation des titres
# v1.7  : Ajout filtrage de certains faux positifs
# v1.8  : Nettoyage périodique des fichiers de log
# v1.9  : Amélioration robustesse sur les suppressions temporaires
# v1.10 : Amélioration gestion faux positifs (changement de salle doublé)
#
# v2.0  : (majeure) Ajout robustesse (graceful shutdown, lock file, timeout réseau),
#         logging structuré, détection fine des changements (titre, horaire, lieu,
#         description), regroupement notifications
# v2.1  : Correction affichage console (horodatage sans décimales secondes)
# v2.2  : Regroupement des ajouts/suppressions/modifications dans les mails
# v2.3  : Amélioration du lock file, persistance des suppressions en attente
# v2.4  : Correction bug serialize_log + suppression automatique du lock file
# v2.5  : Restauration lecture config.json (intervalle, calendriers, mails, etc.)
# v2.6  : Consolidation – réintégration complète des fonctionnalités v1.x + améliorations v2.x
# v2.7  : Restauration parsing ICS (fin bug JSON)
# v2.8  : Regroupement console par bloc + envoi mail robuste (test SMTP)
#
# v3.0  : (avec Le Chat, Mistral AI) Ajout docstrings, messages de modification plus lisibles
# v3.1  : Suppression de l'affichage "Lieu:" si le champ est vide
# v3.5  : Correction des faux positifs de suppression : clé plus stable + logs de débogage
# v3.6  : Ignore les suppressions si le calendrier est inaccessible
#         et modifications cosmétiques sur la console (sauts de ligne)
#
# v4.0  : Ajout du rappel quotidien des événements (mail + log)
# v4.1  : Modifications cosmétiques du mail de rappel quotidien
# v4.2  : Ajout de "Bonne journée !" et gestion de l'envoi par config.json
# v4.3  : Pas d'envoi de mails quotidiens les samedis et dimanches
# v4.4  : Suppression du test spécifique pour "Serge DURAND"
# v4.5  : Ajout d'un message si aucun événement aujourd'hui
# v4.6  : Amélioration de la détection des suppressions pour réduire les faux positifs
# v4.7  : Les suppressions sont différenciées passé/futur et ne sont plus envoyées par mail
# v4.8  : Rotation des logs, normalisation des espaces, couleurs console,
#         correction bug sérialisation datetime
# v4.9  : Affichage console des suppressions passées
#
# v5.0  : Refonte du moteur de comparaison (correction faux positifs)
#         - Clé d'événement uid|start_datetime au lieu de uid seul
#         - Comparaison des datetime comme objets (plus comme str)
#         - Normalisation agressive des champs texte
#         - Suppressions futures réactivées par mail (TEMP : limitées à Serge DURAND)
#         - Migration automatique depuis l'ancien format d'état
#         - Suppression de normalize_summary (inutilisée depuis v2.x)
#
# v5.1  : Améliorations cosmétiques et fonctionnelles
#         - Pied de page dans tous les mails (séparateur + mention de version)
#         - Message de vérification console enrichi : date, heure et version
#         - Suppressions généralisées à tous les calendriers (fin du mode test)
#         - Toutes les suppressions signalées par mail : futures et passées récentes
#         - Suppressions d'événements vieux de plus de 3 mois ignorées complètement
#         - Pluralisation correcte partout : "1 ajout", "2 ajouts" (plus de "(s)")
#
# v5.2  : Corrections cosmétiques console et footer mail
#         - Console : suppressions futures renommées "Suppression(s)" (sans le mot "future")
#         - Console : pluralisation correcte des suppressions via pluriel()
#         - Console : suppression du mot "détectée(s)" devenu inutile
#         - Footer mail : suppression de la ligne vide entre "----" et la mention de version
#
# v5.3  : Refonte de l'affichage des modifications dans les mails
#         - Ordre inversé : événement affiché en premier, détail des changements entre crochets
#         - Contenu des crochets enrichi : "champ : ancienne valeur : X, nouvelle valeur : Y"
#         - Plusieurs changements séparés par " | "
#         - Champs start_dt/end_dt groupés intelligemment (date / heure / date et heure)
#         - Labels utilisateur : "summary" → "Nature", "description" → "Détail"
#         - Suppression de format_changes() remplacée par format_changes_with_values()
#
# v5.4  : Enrichissement de l'affichage des événements
#         - Ajout du "Détail" (description) entre parenthèses après chaque événement
#           (parenthèses absentes si le champ est vide)
#         - Modifications : crochet et contenu affichés sur la ligne suivante,
#           décalés de 12 espaces
#         - Toutes les dates précédées du jour de la semaine abrégé sur 3 caractères
#           (ex : "Lun. 26/03/2026", "Mar.", "Mer.", "Jeu.", "Ven.", "Sam.", "Dim.")
#
# v5.5  : Correction de deux bugs
#         - Bug 1 : suppressions affichées deux fois dans la console — suppression
#           du bloc de logging redondant hors de la boucle sections
#         - Bug 2 : modification d'heure/date détectée comme suppression + ajout
#           → ajout d'une passe de réconciliation : si un UID apparaît à la fois
#           dans les ajouts apparents et les suppressions apparentes (1 pour 1),
#           la paire est reclassée comme modification avant tout logging
#         - Refactorisation : extraction de detect_field_changes() pour éviter
#           la duplication de la logique de comparaison de champs
#
# v5.6  : Renommage du fichier (anciennement calendar_agent_console_v5_5_1.py)
#
# v5.7  : Correction faux positifs "suppression dans le passé" dus à la fenêtre glissante
#         - Les événements dont le début est antérieur à (aujourd'hui - fetch_window_past_days)
#           ne sont plus signalés comme supprimés : ils ont simplement quitté la fenêtre iMFR
#         - Paramètre configurable via "fetch_window_past_days" dans config.json (défaut : 14)
#
# v6.0  : (majeure) Notifications fenêtre pour les événements imminents
#         - Affiche une fenêtre tkinter (bas-droite, toujours au premier plan) quand un
#           événement du propriétaire commence dans les N prochaines minutes
#           (configurable : notification_window_minutes)
#         - Reste à l'écran jusqu'au clic (contrairement aux toasts Windows auto-effacées)
#         - Bouton "OK" : acquittement définitif, plus de rappel pour cet événement
#         - Bouton "Snooze" : rappel après N minutes (configurable : notification_snooze_minutes)
#         - Si la fenêtre est fermée (croix), comportement identique au Snooze
#         - Si l'utilisateur n'est pas là : la fenêtre reste visible indéfiniment
#         - Propriétaire identifié par notification_owner_name dans config.json
#         - Anti-doublon en mémoire (simple, sans persistance)
#         - Aucune dépendance supplémentaire (tkinter inclus dans Python)
#
# v6.0.2: Correction crash "Tcl_AsyncDelete: async handler deleted by the wrong thread"
#         - Un seul thread Tkinter persistant (tk.Tk() créé une seule fois)
#         - Les fenêtres de notification utilisent Toplevel au lieu de Tk()
#         - Communication main→Tk via queue.Queue + root.after() (thread-safe)
#
# v6.0.3: Correction lock file fantôme au redémarrage après crash
#         - create_lock() lit le PID dans le lock file et vérifie si le processus
#           est encore vivant (os.kill(pid, 0))
#         - Si le processus est mort → lock fantôme → suppression silencieuse + démarrage
#         - Si le processus tourne → vraie collision → message d'erreur + arrêt (inchangé)
#
# v6.0.4: Correction faux positifs sur les champs "Dédoublement"
#         - iMFR retourne parfois les sous-groupes d'un dédoublement dans un ordre différent
#           sans que le contenu ait changé → faux positif de modification détectée
#         - Nouvelle fonction normalize_description_for_compare() : si la description
#           commence par "Dédoublement :", les segments sont triés alphabétiquement
#           avant comparaison → un simple swap d'ordre ne déclenche plus de notification
#
# v6.1  : Robustesse envoi mail
#         - send_email() retourne True/False selon succès ou échec
#         - Si le mail échoue, l'état du calendrier n'est PAS mis à jour :
#           les changements seront inclus dans le prochain mail réussi
# =====================================================================

import os
import re
import sys
import json
import time
import logging
import signal
import atexit
import queue
import threading
import tkinter as tk
import unicodedata
import requests
import datetime
import pytz
import smtplib
from typing import Dict, List, Tuple, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from icalendar import Calendar

VERSION = "6.0.4"

JOURS = ["Lun.", "Mar.", "Mer.", "Jeu.", "Ven.", "Sam.", "Dim."]

INDENT_CHANGEMENT = "&nbsp;" * 12

# --- Constantes et configuration ---
try:
    with open("config.json", "r", encoding="utf-8") as f:
        CONFIG = json.load(f)
except Exception as e:
    print(f"ERREUR: Impossible de lire config.json ({e})")
    sys.exit(1)

TIMEZONE            = pytz.timezone(CONFIG.get("timezone", "Europe/Paris"))
CHECK_INTERVAL      = CONFIG.get("check_interval", 600)
CALENDARS           = CONFIG.get("calendars", [])
STATE_FILE          = CONFIG.get("state_file", "calendar_state.json")
LOG_FILE            = CONFIG.get("log_file", "events_log.json")
LOCK_FILE           = CONFIG.get("lock_file", "calendar_agent.lock")
DAILY_REMINDER_FILE = CONFIG.get("daily_reminder_file", "daily_reminder_sent.json")
EMAIL_SENDER        = CONFIG.get("email_sender", "")
SMTP_SERVER         = CONFIG.get("smtp_server", "")
SMTP_PORT           = CONFIG.get("smtp_port", 587)
EMAIL_PASSWORD      = os.getenv(CONFIG.get("email_password_env", ""))
LOG_ROTATION_DAYS   = CONFIG.get("log_rotation_days", 30)

SUPPRESSION_IGNORE_DAYS  = 90
FETCH_WINDOW_PAST_DAYS   = CONFIG.get("fetch_window_past_days", 14)

NOTIFICATION_OWNER_NAME    = CONFIG.get("notification_owner_name", "")
NOTIFICATION_WINDOW_MIN    = CONFIG.get("notification_window_minutes", 30)
NOTIFICATION_SNOOZE_MIN    = CONFIG.get("notification_snooze_minutes", 10)

EMAIL_FOOTER = (
    "<br>"
    "<p>--------------------</p>"
    f"<p><i>Mail généré avec l'outil AgentCalendrierMFR version {VERSION}.</i></p>"
)

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="[{asctime}] {levelname}: {message}",
    style="{",
    datefmt="%d/%m/%Y %H:%M"
)

# --- Gestion du lock file ---
def create_lock() -> None:
    if os.path.exists(LOCK_FILE):
        pid = None
        try:
            with open(LOCK_FILE, "r") as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            # os.kill(pid, 0) a réussi → processus toujours vivant → vraie collision
            logging.error("Une instance est déjà en cours !")
            sys.exit(1)
        except OSError:
            # ProcessLookupError : PID inexistant → lock fantôme (crash précédent)
            pass
        except ValueError:
            pass
        logging.warning(
            f"Lock file fantôme détecté (PID {pid}), "
            "le processus précédent s'est terminé anormalement. Démarrage..."
        )
        os.remove(LOCK_FILE)
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

def remove_lock() -> None:
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
        logging.info("Lock file supprimé proprement.")

def handle_exit(signum=None, frame=None) -> None:
    remove_lock()
    sys.exit(0)

atexit.register(remove_lock)
signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)

# --- Fonctions utilitaires ---
def ensure_datetime(dt) -> datetime.datetime:
    if isinstance(dt, datetime.date) and not isinstance(dt, datetime.datetime):
        dt = datetime.datetime.combine(dt, datetime.time.min)
    if dt.tzinfo is None:
        dt = TIMEZONE.localize(dt)
    else:
        dt = dt.astimezone(TIMEZONE)
    return dt

def jour_semaine(dt: datetime.datetime) -> str:
    return JOURS[dt.weekday()]

def format_start_end(start_dt, end_dt) -> str:
    start_dt  = ensure_datetime(start_dt)
    end_dt    = ensure_datetime(end_dt)
    start_str = f"{jour_semaine(start_dt)} {start_dt.strftime('%d/%m/%Y %H:%M')}"
    if start_dt.date() == end_dt.date():
        end_str = end_dt.strftime("%H:%M")
    else:
        end_str = f"{jour_semaine(end_dt)} {end_dt.strftime('%d/%m/%Y %H:%M')}"
    return f"{start_str}-{end_str}"

def format_time_only(start_dt, end_dt) -> str:
    start_dt = ensure_datetime(start_dt)
    end_dt   = ensure_datetime(end_dt)
    return f"{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}"

def format_date_with_day(dt: datetime.datetime) -> str:
    return f"{jour_semaine(dt)} {dt.strftime('%d/%m/%Y')}"

def normalize_aggressive(s: str) -> str:
    return re.sub(r'\s+', ' ', s.lower()).strip()

def normalize_description_for_compare(s: str) -> str:
    """Normalise une description pour comparaison.
    Si la valeur est un champ Dédoublement, trie les sous-groupes alphabétiquement
    pour éviter les faux positifs quand iMFR change juste leur ordre."""
    normalized = normalize_aggressive(s)
    m = re.match(r'^(d[eé]doublement\s*:\s*)(.*)', normalized)
    if not m:
        return normalized
    segments = re.split(r',\s+', m.group(2))
    return m.group(1) + ", ".join(sorted(segments))

def pluriel(n: int, singulier: str, pluriel_forme: str = None) -> str:
    if n == 1:
        return f"1 {singulier}"
    return f"{n} {pluriel_forme if pluriel_forme else singulier + 's'}"

def make_event_key(ev: Dict[str, Any]) -> str:
    start = ensure_datetime(ev["start_dt"]).strftime("%Y-%m-%d %H:%M")
    return f"{ev['uid']}|{start}"

def detect_field_changes(ev_new: Dict, ev_old: Dict) -> List[str]:
    """Retourne la liste des champs qui ont changé entre deux versions d'un événement."""
    changes = []
    for field in ["summary", "start_dt", "end_dt", "location", "description"]:
        new_val = ev_new.get(field)
        old_val = ev_old.get(field)
        if field in ("start_dt", "end_dt"):
            if ensure_datetime(new_val) != ensure_datetime(old_val):
                changes.append(field)
        elif field == "description":
            if normalize_description_for_compare(str(new_val)) != normalize_description_for_compare(str(old_val)):
                changes.append(field)
        else:
            if normalize_aggressive(str(new_val)) != normalize_aggressive(str(old_val)):
                changes.append(field)
    return changes

def format_event_line(ev: Dict[str, Any]) -> str:
    """Formate une ligne d'événement : date/heure + nature + (Détail si non vide)."""
    lieu       = f" – Lieu: {ev.get('location','')}" if ev.get("location") else ""
    detail     = (ev.get("description") or "").strip()
    detail_str = f" ({detail})" if detail else ""
    return (
        f"{format_start_end(ev['start_dt'], ev['end_dt'])} "
        f"{ev['summary']}{lieu}{detail_str}"
    )

def format_changes_with_values(ev_new: Dict, ev_old: Dict, changes: List[str]) -> str:
    """Formate le détail des changements avec anciennes et nouvelles valeurs."""
    parts = []

    has_start = "start_dt" in changes
    has_end   = "end_dt"   in changes
    if has_start or has_end:
        old_start = ensure_datetime(ev_old["start_dt"])
        old_end   = ensure_datetime(ev_old["end_dt"])
        new_start = ensure_datetime(ev_new["start_dt"])
        new_end   = ensure_datetime(ev_new["end_dt"])

        date_changed = old_start.date() != new_start.date()
        time_changed = (old_start.time() != new_start.time()
                        or old_end.time() != new_end.time())

        if date_changed and time_changed:
            label   = "Date et heure"
            old_val = f"{format_date_with_day(old_start)} {format_time_only(old_start, old_end)}"
            new_val = f"{format_date_with_day(new_start)} {format_time_only(new_start, new_end)}"
        elif date_changed:
            label   = "Date"
            old_val = format_date_with_day(old_start)
            new_val = format_date_with_day(new_start)
        else:
            label   = "Heure"
            old_val = format_time_only(old_start, old_end)
            new_val = format_time_only(new_start, new_end)

        parts.append(f"{label} : ancienne valeur : {old_val}, nouvelle valeur : {new_val}")

    field_labels = {
        "summary":     "Nature",
        "location":    "lieu",
        "description": "Détail",
    }
    for field in ["summary", "location", "description"]:
        if field in changes:
            label   = field_labels[field]
            old_val = str(ev_old.get(field, ""))
            new_val = str(ev_new.get(field, ""))
            parts.append(f"{label} : ancienne valeur : {old_val}, nouvelle valeur : {new_val}")

    return " | ".join(parts)

def send_email(to_addr: str, subject: str, body: str) -> bool:
    """Envoie un mail. Retourne True si succès, False si échec."""
    if not to_addr:
        return True
    if not SMTP_SERVER:
        logging.error("SMTP non configuré, mail non envoyé")
        return False
    try:
        msg = MIMEMultipart()
        msg["From"]    = EMAIL_SENDER
        msg["To"]      = to_addr
        msg["Subject"] = subject
        msg.attach(MIMEText(body + EMAIL_FOOTER, "html", "utf-8"))
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            if EMAIL_PASSWORD:
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        logging.error(f"Erreur envoi mail via {SMTP_SERVER}:{SMTP_PORT} → {e}")
        return False

def fetch_events(url: str) -> Tuple[Dict[str, Dict[str, Any]], bool]:
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        cal = Calendar.from_ical(resp.text)
        events = {}
        for component in cal.walk("VEVENT"):
            uid         = str(component.get("UID"))
            summary     = str(component.get("SUMMARY", ""))
            location    = str(component.get("LOCATION", ""))
            description = str(component.get("DESCRIPTION", ""))
            start_dt    = ensure_datetime(component.decoded("DTSTART"))
            end_dt      = ensure_datetime(component.decoded("DTEND"))
            ev = {
                "uid":         uid,
                "summary":     summary,
                "location":    location,
                "description": description,
                "start_dt":    start_dt,
                "end_dt":      end_dt,
            }
            events[make_event_key(ev)] = ev
        return events, True
    except Exception as e:
        logging.error(f"Erreur récupération {url}: {e}")
        return {}, False

def serialize_events(events: Dict) -> Dict:
    serialized = {}
    for cal_id, cal_events in events.items():
        serialized[cal_id] = {}
        for key, ev in cal_events.items():
            ev_copy = ev.copy()
            ev_copy["start_dt"] = ev_copy["start_dt"].isoformat()
            ev_copy["end_dt"]   = ev_copy["end_dt"].isoformat()
            serialized[cal_id][key] = ev_copy
    return serialized

def deserialize_events(raw: Dict) -> Tuple[Dict, bool]:
    result = {}
    for cal_id, cal_events in raw.items():
        for key in cal_events:
            if "|" not in key:
                logging.warning(
                    "Ancien format d'état détecté (clé = UID seul). "
                    "Démarrage à zéro pour éviter les faux positifs v4→v5."
                )
                return {}, True
        result[cal_id] = {}
        for key, ev in cal_events.items():
            ev_copy = ev.copy()
            ev_copy["start_dt"] = datetime.datetime.fromisoformat(ev_copy["start_dt"])
            ev_copy["end_dt"]   = datetime.datetime.fromisoformat(ev_copy["end_dt"])
            result[cal_id][key] = ev_copy
    return result, False

def serialize_log(log: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    s_log = []
    for entry in log:
        entry_copy = entry.copy()
        if isinstance(entry_copy.get("timestamp"), datetime.datetime):
            entry_copy["timestamp"] = entry_copy["timestamp"].isoformat()
        if "event" in entry_copy and isinstance(entry_copy["event"], dict):
            ev_copy = entry_copy["event"].copy()
            for field in ["start_dt", "end_dt"]:
                if field in ev_copy and isinstance(ev_copy[field], datetime.datetime):
                    ev_copy[field] = ev_copy[field].isoformat()
            entry_copy["event"] = ev_copy
        s_log.append(entry_copy)
    return s_log

def rotate_logs() -> None:
    if not os.path.exists(LOG_FILE):
        return
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
        now    = datetime.datetime.now(TIMEZONE)
        cutoff = now - datetime.timedelta(days=LOG_ROTATION_DAYS)
        filtered = [
            log for log in logs
            if datetime.datetime.fromisoformat(log["timestamp"]) >= cutoff
        ]
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(filtered, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Erreur rotation des logs: {e}")

def extract_event_nature(summary: str) -> str:
    if ":" in summary:
        nature_part = summary.split(":")[0].strip()
        rest_part   = summary.split(":")[1].split("-")[0].strip()
        return f"{nature_part} {rest_part}"
    return summary

def format_french_date(dt: datetime.datetime) -> str:
    months = [
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre"
    ]
    return f"{jour_semaine(dt)} {dt.day} {months[dt.month - 1]} {dt.year}"

def should_send_daily_reminder() -> bool:
    now = datetime.datetime.now(TIMEZONE)
    if now.hour < 7:
        return False
    if now.weekday() >= 5:
        return False
    if os.path.exists(DAILY_REMINDER_FILE):
        try:
            with open(DAILY_REMINDER_FILE, "r", encoding="utf-8") as f:
                last_sent = json.load(f)
            if last_sent.get("date") == now.strftime("%Y-%m-%d"):
                return False
        except Exception:
            pass
    with open(DAILY_REMINDER_FILE, "w", encoding="utf-8") as f:
        json.dump({"date": now.strftime("%Y-%m-%d")}, f)
    return True

def send_daily_reminder(cal_id: str, events: Dict[str, Dict[str, Any]], to_addr: str) -> None:
    now_dt       = datetime.datetime.now(TIMEZONE)
    today        = now_dt.date()
    today_events = []
    for key, ev in events.items():
        if ensure_datetime(ev["start_dt"]).date() == today:
            nature = extract_event_nature(ev["summary"])
            lieu   = f", salle: {ev.get('location', '')}" if ev.get("location") else ""
            today_events.append({
                "time":   format_time_only(ev["start_dt"], ev["end_dt"]),
                "nature": nature,
                "detail": ev["summary"],
                "lieu":   lieu,
            })
    date_str = format_french_date(now_dt)
    if not today_events:
        logging.info(f"Aucun événement aujourd'hui pour {cal_id}, mail envoyé avec mention.")
        html_body = (
            f'<h2 style="color: #404040;">Votre journée du {date_str}</h2>'
            f"<p>Pas d'événement pour aujourd'hui.</p>"
            f"<p>Bonne journée !</p>"
        )
    else:
        html_body = f'<h2 style="color: #404040;">Votre journée du {date_str}</h2><ul>'
        for ev in sorted(today_events, key=lambda x: x["time"]):
            detail_part = ev["detail"].split("-")[1].strip() if "-" in ev["detail"] else ev["detail"]
            html_body += f"<li>{ev['time']} : {ev['nature']} : {detail_part}{ev['lieu']}</li>"
        html_body += "</ul><p>Bonne journée !</p>"
    send_email(to_addr, "Votre journée", html_body)
    logging.info(f"Mail de rappel quotidien envoyé pour {cal_id}")


# =====================================================================
# Notifications fenêtre tkinter (v6.0.2 — thread Tk unique)
# =====================================================================
#
# ARCHITECTURE :
#   - Un seul thread Tkinter (_tk_thread_func) tourne en arrière-plan.
#   - Il possède la seule instance tk.Tk() (racine cachée).
#   - Toutes les fenêtres de notification sont des tk.Toplevel() créées
#     et détruites dans ce thread → plus de "wrong thread".
#   - Le thread principal communique via _tk_queue (queue.Queue).
#   - _poll_tk_queue() est appelée toutes les 200 ms par root.after(),
#     ce qui garantit l'exécution dans le thread Tk.

# État en mémoire des notifications : clé événement → dict
# {
#   "last_notified_at": datetime,
#   "acknowledged":     bool,
#   "snoozed_until":    datetime | None,
# }
_notification_state: Dict[str, Dict] = {}
_notification_lock  = threading.Lock()
_open_windows_count = 0   # nombre de fenêtres de notification actuellement ouvertes

_tk_queue: "queue.Queue" = queue.Queue()
_tk_root  = None                  # instance unique tk.Tk(), créée dans le thread Tk
_tk_ready = threading.Event()     # signale que _tk_root est initialisé


def _poll_tk_queue() -> None:
    """Dépile les requêtes de toast. Appelée toutes les 200 ms dans le thread Tk."""
    try:
        while True:
            func, args = _tk_queue.get_nowait()
            func(*args)
    except queue.Empty:
        pass
    _tk_root.after(200, _poll_tk_queue)


def _tk_thread_func() -> None:
    """Thread Tkinter unique : crée la racine cachée et tourne indéfiniment."""
    global _tk_root
    _tk_root = tk.Tk()
    _tk_root.withdraw()   # racine invisible — sert uniquement de parent aux Toplevel
    _tk_ready.set()
    _poll_tk_queue()
    _tk_root.mainloop()


def _ensure_tk_thread() -> None:
    """Démarre le thread Tkinter unique s'il n'est pas encore lancé."""
    if not _tk_ready.is_set():
        t = threading.Thread(target=_tk_thread_func, daemon=True, name="TkNotifThread")
        t.start()
        _tk_ready.wait(timeout=3)


def _normalize_for_match(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )

def format_notification_summary(summary: str) -> str:
    """Formate le summary iMFR pour l'affichage dans la notification.

    Cours  → "classe, [module] nom"
    Autres → summary brut
    """
    if not summary:
        return summary
    low = _normalize_for_match(summary)
    if "cours" not in low:
        return summary
    try:
        idx   = low.find("cours")
        after = summary[idx + 5:].lstrip(" :–-").strip()
        if "-" not in after:
            return summary
        left, right = after.split("-", 1)
        classe = left.strip()
        if not classe:
            return summary
        parts = right.strip().split()
        if len(parts) < 2:
            return summary
        module = parts[1]
        nom    = " ".join(parts[2:]) if len(parts) > 2 else ""
        # Tronquer avant "salle" si présent
        idx_s = nom.lower().find("salle")
        if idx_s != -1:
            nom = nom[:idx_s].rstrip()
        return f"{classe}, [{module}] {nom}".strip()
    except Exception:
        return summary


def _create_toast_window(ev: Dict[str, Any], key: str, window_index: int, minutes_until: int) -> None:
    """Crée une fenêtre Toplevel. DOIT être appelée uniquement depuis le thread Tk."""
    global _open_windows_count

    BG      = "#2C3E50"
    FG_HEAD = "#F39C12"
    FG_BODY = "#FFFFFF"
    FG_SUB  = "#BDC3C7"

    w, h, gap = 360, 120, 8
    sw = _tk_root.winfo_screenwidth()
    sh = _tk_root.winfo_screenheight()
    x  = sw - w - 20
    y  = sh - (h + gap) * (window_index + 1) - 60 + gap

    win = tk.Toplevel(_tk_root)
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    win.attributes("-alpha", 0.95)
    win.geometry(f"{w}x{h}+{x}+{y}")
    win.configure(bg=BG)

    start   = ensure_datetime(ev["start_dt"])
    end     = ensure_datetime(ev["end_dt"])
    horaire = format_time_only(start, end)
    lieu    = f"  |  Salle : {ev['location']}" if ev.get("location") else ""

    lbl_countdown = tk.Label(win, text="",
                              bg=BG, fg=FG_HEAD, font=("Segoe UI", 11, "bold"),
                              anchor="w")
    lbl_countdown.pack(fill="x", padx=14, pady=(10, 0))

    def update_countdown():
        if not win.winfo_exists():
            return
        delta = int((start - datetime.datetime.now(TIMEZONE)).total_seconds() / 60)
        if delta > 0:
            lbl_countdown.config(text=f"Dans {delta} min")
        elif delta == 0:
            lbl_countdown.config(text="Commence maintenant !")
        else:
            lbl_countdown.config(text=f"En cours (commencé il y a {-delta} min)")
        win.after(60000, update_countdown)

    update_countdown()

    tk.Label(win, text=format_notification_summary(ev["summary"]),
             bg=BG, fg=FG_BODY, font=("Segoe UI", 10),
             anchor="w").pack(fill="x", padx=14)

    tk.Label(win, text=f"{horaire}{lieu}",
             bg=BG, fg=FG_SUB, font=("Segoe UI", 9),
             anchor="w").pack(fill="x", padx=14)

    def _decrement():
        global _open_windows_count
        with _notification_lock:
            _open_windows_count = max(0, _open_windows_count - 1)

    def on_close():
        _decrement()
        win.destroy()

    def on_ok():
        with _notification_lock:
            if key in _notification_state:
                _notification_state[key]["acknowledged"] = True
        logging.info(f"[Notif] Acquitté : {ev['summary']}")
        _decrement()
        win.destroy()

    def on_snooze():
        snooze_until = datetime.datetime.now(TIMEZONE) + datetime.timedelta(minutes=NOTIFICATION_SNOOZE_MIN)
        with _notification_lock:
            if key in _notification_state:
                _notification_state[key]["snoozed_until"] = snooze_until
        logging.info(
            f"[Notif] Snooze activé pour '{ev['summary']}' "
            f"(rappel à {snooze_until.strftime('%H:%M')})"
        )
        _decrement()
        win.destroy()

    # Fermeture via la croix → traité comme Snooze
    win.protocol("WM_DELETE_WINDOW", on_snooze)

    btn_frame = tk.Frame(win, bg=BG)
    btn_frame.pack(pady=(8, 0), padx=14, anchor="e")

    tk.Button(btn_frame, text=f"Snooze {NOTIFICATION_SNOOZE_MIN} min",
              command=on_snooze,
              bg="#7F8C8D", fg="white", relief="flat",
              padx=8, pady=3, cursor="hand2").pack(side="left", padx=(0, 8))

    tk.Button(btn_frame, text="OK",
              command=on_ok,
              bg="#27AE60", fg="white", relief="flat",
              padx=14, pady=3, cursor="hand2").pack(side="left")


def _fire_toast(ev: Dict[str, Any], key: str, minutes_until: int) -> None:
    """Enfile une requête de notification dans la queue du thread Tk unique."""
    global _open_windows_count

    _ensure_tk_thread()

    with _notification_lock:
        window_index = _open_windows_count
        _open_windows_count += 1

    _tk_queue.put((_create_toast_window, (ev, key, window_index, minutes_until)))
    logging.info(f"[Notif] Fenêtre affichée : Dans {minutes_until} min — {ev['summary']}")


def check_and_notify(events: Dict[str, Dict[str, Any]]) -> None:
    """Vérifie les événements imminents et affiche une fenêtre de notification si nécessaire."""
    if not NOTIFICATION_OWNER_NAME:
        return

    now          = datetime.datetime.now(TIMEZONE)
    window_end   = now + datetime.timedelta(minutes=NOTIFICATION_WINDOW_MIN)
    snooze_delta = datetime.timedelta(minutes=NOTIFICATION_SNOOZE_MIN)

    for key, ev in events.items():
        start = ensure_datetime(ev["start_dt"])

        in_forward_window  = now < start <= window_end
        recently_started   = (now - snooze_delta) < start <= now

        if not in_forward_window and not recently_started:
            continue  # événement hors fenêtre

        # Pour un événement déjà commencé, n'agir que si un snooze est en attente
        if recently_started and not in_forward_window:
            with _notification_lock:
                st = _notification_state.get(key)
            if not st or st.get("acknowledged") or not st.get("snoozed_until"):
                continue

        minutes_until = max(0, int((start - now).total_seconds() / 60))

        with _notification_lock:
            state = _notification_state.get(key)

            if state is None:
                # Première notification pour cet événement
                _notification_state[key] = {
                    "last_notified_at": now,
                    "acknowledged":     False,
                    "snoozed_until":    None,
                }
                should_notify = True

            elif state["acknowledged"]:
                should_notify = False

            elif state["snoozed_until"] is not None:
                # L'utilisateur a cliqué Snooze : respecter l'heure demandée
                # Petite tolérance d'une minute pour compenser le décalage cycle/clic
                should_notify = (now >= state["snoozed_until"] - datetime.timedelta(seconds=60))
                if should_notify:
                    state["snoozed_until"]    = None
                    state["last_notified_at"] = now

            else:
                # Pas d'action sur la fenêtre précédente (timeout) :
                # re-notifier après snooze_delta comme pour un vrai snooze
                should_notify = (now >= state["last_notified_at"] + snooze_delta)
                if should_notify:
                    state["last_notified_at"] = now

        if should_notify:
            _fire_toast(ev, key, minutes_until)


# =====================================================================
# Boucle principale
# =====================================================================

def main() -> None:
    if not NOTIFICATION_OWNER_NAME:
        logging.warning(
            "Paramètre 'notification_owner_name' absent de config.json. "
            "Les notifications sont désactivées."
        )
    else:
        logging.info(
            f"Notifications activées pour '{NOTIFICATION_OWNER_NAME}' "
            f"(fenêtre : {NOTIFICATION_WINDOW_MIN} min, snooze : {NOTIFICATION_SNOOZE_MIN} min)"
        )

    create_lock()
    logging.info(f">>> Agent calendrier démarré (v{VERSION}) <<<")

    previous_state = {}
    events_log     = []
    first_run      = True

    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            previous_state, forced_first_run = deserialize_events(raw)
            first_run = forced_first_run
        except Exception as e:
            logging.warning(f"Impossible de lire {STATE_FILE} ({e}), démarrage à zéro.")
            previous_state = {}
            first_run      = True

    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                events_log_raw = json.load(f)
            for entry in events_log_raw:
                entry["timestamp"] = datetime.datetime.fromisoformat(entry["timestamp"])
            events_log = events_log_raw
        except Exception:
            logging.warning(f"{LOG_FILE} invalide, création d'un nouveau log.")
            events_log = []

    while True:
        now = datetime.datetime.now(TIMEZONE)
        print()
        logging.info(
            f"--- Vérification le {now.strftime('%d/%m/%Y')} à {now.strftime('%H:%M')}"
            f"   (AgentCalendrierMFR version {VERSION}) ---"
        )

        # --- Rappels quotidiens ---
        if should_send_daily_reminder():
            for cal_cfg in CALENDARS:
                cal_id = cal_cfg.get("name", "Inconnu")
                logging.info(f"Préparation du mail quotidien pour {cal_id}...")
                new_events, success = fetch_events(cal_cfg.get("url"))
                if not success:
                    continue
                if not cal_cfg.get("send_daily_reminder", False):
                    logging.info(f"Mail quotidien désactivé pour {cal_id} (config).")
                    continue
                if cal_cfg.get("email"):
                    send_daily_reminder(cal_id, new_events, cal_cfg["email"])

        # --- Vérification des calendriers ---
        for cal_cfg in CALENDARS:
            cal_id = cal_cfg.get("name", "Inconnu")
            logging.info(f"Vérification calendrier {cal_id}...")
            new_events, success = fetch_events(cal_cfg.get("url"))
            if not success:
                logging.warning(f"Calendrier {cal_id} inaccessible, vérification ignorée.")
                continue

            # --- Notifications toast (propriétaire uniquement) ---
            if cal_id == NOTIFICATION_OWNER_NAME:
                check_and_notify(new_events)

            old_events = previous_state.get(cal_id, {})
            added_initial = []
            modified      = []

            # Étape 1 : détection des ajouts et modifications par clé exacte (uid|start)
            for key, ev in new_events.items():
                old_ev = old_events.get(key)
                if not old_ev:
                    added_initial.append(ev)
                else:
                    changes = detect_field_changes(ev, old_ev)
                    if changes:
                        modified.append((ev, old_ev, changes))

            # Étape 2 : détection des suppressions apparentes (sans logger encore)
            now_dt             = datetime.datetime.now(TIMEZONE)
            ignore_before      = now_dt - datetime.timedelta(days=SUPPRESSION_IGNORE_DAYS)
            fetch_window_start = now_dt - datetime.timedelta(days=FETCH_WINDOW_PAST_DAYS)
            apparent_removed = []
            for key in old_events.keys() - new_events.keys():
                ev_old   = old_events[key]
                ev_start = ensure_datetime(ev_old["start_dt"])
                if ev_start < fetch_window_start:
                    continue  # sorti de la fenêtre iMFR — faux positif attendu, ignoré
                if ev_start >= ignore_before:
                    apparent_removed.append(ev_old)

            # Étape 3 : réconciliation — ajout apparent + suppression apparente avec même UID
            # (cas non ambigu : exactement 1 pour 1) → reclassé comme modification
            added_by_uid   = {}
            for ev in added_initial:
                added_by_uid.setdefault(ev["uid"], []).append(ev)

            removed_by_uid = {}
            for ev in apparent_removed:
                removed_by_uid.setdefault(ev["uid"], []).append(ev)

            reclassified_uids = set()
            for uid in list(added_by_uid.keys()):
                if uid in removed_by_uid:
                    if len(added_by_uid[uid]) == 1 and len(removed_by_uid[uid]) == 1:
                        ev_new_c = added_by_uid[uid][0]
                        ev_old_c = removed_by_uid[uid][0]
                        changes  = detect_field_changes(ev_new_c, ev_old_c)
                        if changes:
                            modified.append((ev_new_c, ev_old_c, changes))
                        reclassified_uids.add(uid)

            added = [ev for ev in added_initial   if ev["uid"] not in reclassified_uids]
            real_removed = [ev for ev in apparent_removed if ev["uid"] not in reclassified_uids]

            # Étape 4 : classification futur/passé et logging des vraies suppressions
            removed_future = []
            removed_past   = []
            for ev_old in real_removed:
                start = ensure_datetime(ev_old["start_dt"])
                if start >= now_dt:
                    removed_future.append(ev_old)
                    events_log.append({"timestamp": now_dt, "action": "suppression_future", "event": ev_old})
                else:
                    removed_past.append(ev_old)
                    events_log.append({"timestamp": now_dt, "action": "suppression_passee", "event": ev_old})

            # --- Notifications console et mail ---
            timestamp = datetime.datetime.now(TIMEZONE)
            sections = [
                ("Ajout",                     "Ajouts",                     added),
                ("Modification",              "Modifications",              modified),
                ("Suppression",               "Suppressions",               removed_future),
                ("Suppression dans le passé", "Suppressions dans le passé", removed_past),
            ]
            total_changes = len(added) + len(modified) + len(removed_future) + len(removed_past)

            if not first_run and total_changes > 0:
                html_msg = f'<h2 style="color: #404040;">{cal_id} — Résumé des modifications</h2>'
                for sing, plur, evts in sections:
                    if not evts:
                        continue
                    count_str = pluriel(len(evts), sing, plur)
                    logging.info(f"[{timestamp.strftime('%d/%m/%Y %H:%M')}] {count_str}")
                    html_msg += f'<h3 style="color: #00008B; margin-bottom: 0;">{count_str}</h3><ul style="margin-top: 0;">'
                    for ev in evts:
                        if sing == "Modification":
                            ev_new, ev_old, changes = ev
                            change_str = format_changes_with_values(ev_new, ev_old, changes)
                            msg_line = (
                                f"{format_event_line(ev_new)}"
                                f"<br>{INDENT_CHANGEMENT}[{change_str}]"
                            )
                        else:
                            msg_line = format_event_line(ev)
                        html_msg += f"<li>{msg_line}</li>"
                    html_msg += "</ul>"

                mail_ok = True
                if cal_cfg.get("email"):
                    mail_ok = send_email(
                        cal_cfg["email"],
                        pluriel(total_changes, "événement"),
                        html_msg
                    )
                if not mail_ok:
                    logging.warning(
                        f"Mail non envoyé pour {cal_id} — état non mis à jour, "
                        "les changements seront renvoyés au prochain cycle."
                    )
                    continue

            previous_state[cal_id] = new_events

        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(serialize_events(previous_state), f, indent=2, ensure_ascii=False)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(serialize_log(events_log), f, indent=2, ensure_ascii=False)
        rotate_logs()

        if first_run:
            logging.info(">>> Première exécution terminée : aucune notification envoyée <<<")
            first_run = False

        minutes     = CHECK_INTERVAL / 60
        minutes_str = f"{minutes:.1f}" if minutes % 1 else f"{int(minutes)}"
        logging.info(
            f"--- Fin vérification ({datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}), "
            f"prochaine vérification dans {minutes_str} minutes ---"
        )
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
