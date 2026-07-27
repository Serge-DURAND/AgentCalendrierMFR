# =====================================================================
# Historique des versions  (résumé)
#
# v5.14 : Menu plat 1-4 stats + 5 détail, RTT/CONGÉS séparés,
#          en-tête année fusionné, séances 15 min ignorées
#
# v5.15 :
#   - Double ligne "---" supprimée (THIN retiré de _disp_year_header)
#   - Option 1 : pas de ligne vide entre les classes
#   - Option 1 : pas de cycle [filière] dans les libellés de COURS
#   - Options 2/3 : pas de répétition des titres colonnes avant TOTAL
#   - En-têtes colonnes sur 2 lignes :
#       ligne 1 : "HEURES"| "HEURES STANDARD"
#       ligne 2 : "Passées" "Planif." "Total" (x2)
#   - Section 4 : TOTAL RTT+CONGÉS seulement si les 2 catégories présentes
#   - Section 5 : alignement tableau corrigé (format unique header/data),
#                 "heures réelles" et "heures standardisées" sur le total
#
# v5.16 :
#   - Option 1 : colonnes numériques alignées avec GRAND TOTAL
#   - Nouveau moteur : heures élève entières (seuil 50 min) +
#     heures formateur brutes (dédoublé naturel, regroupé × 0.5)
#   - Format  ELEVE: Xh (Xh + Xh fut.)| FORMATEUR: Xhxx (...)
#   - Mise en forme ANSI : gras sur cycles, classes, TOTAL, GRAND TOTAL
#
# v5.19 : Factorisation : _current_cn_sy, _ev_start/_ev_end, _fmt_ded_reg,
#          _row_yellow/_row_dim/_row_bold, _print_green_header, _compute_contributions
#
# v5.20 : Option 7 "Prochaines séquences"
#          - Tableau classe × cours × séances cette semaine × prochain cours
#          - "Cette semaine" = lun–ven de la semaine calendaire courante
#            (si sam/dim : la semaine passée est affichée, indiquée comme telle)
#          - "Prochain cours" = toutes les séances de la semaine du premier cours
#            à partir du lundi suivant
#          - "-" si aucune séance pour la colonne concernée
#          - Plusieurs lignes si plusieurs séances cette semaine ou prochaine fois
#          - Tri : par classe (CLASS_ORDER) puis par cours
#          - L'ancienne option 7 "Changer d'année scolaire" devient l'option 8
#
# v5.21 : Option 7 — troncature du nom de cours pour aligner les colonnes de dates
#
# v5.22 : Option 7 — suppression des séparateurs ··· entre classes,
#          colonne COURS élargie de 5 caractères (28 → 33)
#          Titre simplifié "Prochaines séquences", plage de dates sous "CETTE SEMAINE"
#
# v5.23 : Chargement automatique et silencieux des données au démarrage
#          - Extraction de _load_data() (fetch + analyse sans affichage)
#          - _load_and_show() l'appelle puis affiche
#          - main() l'appelle au lancement : les options 4-7 sont utilisables immédiatement
#
# v6.0  : Option 8 "Analyse de l'année en cours"
#          - Tableau hebdomadaire de l'année scolaire sélectionnée
#          - 1 ligne par semaine : plage de dates + heures formateur brutes + % / 20h
#          - Couleurs alternantes blanc/cyan par semaine
#          - Alerte jaune "alerte"  si 100% ≤ charge ≤ 120%
#          - Alerte rouge "ALERTE"  si charge ≥ 121%
#          - L'ancienne option 8 "Changer d'année scolaire" devient option 9
# =====================================================================

import os
import sys
import json

# Active les codes ANSI dans cmd.exe Windows 10+ (sans effet ailleurs)
if os.name == "nt":
    os.system("")

# Codes ANSI
_B   = "\033[1m"    # gras
_UL  = "\033[4m"    # souligné (visible même si bold ignoré)
_DM  = "\033[2m"    # dim (grisé)
_Y   = "\033[33m"   # jaune
_GRN = "\033[32m"   # vert
_RED = "\033[36m"   # cyan
_RGE = "\033[31m"   # rouge vrai
_R   = "\033[0m"    # reset

def _bold(s: str) -> str:
    return f"{_B}{s}{_R}"

def _dim(s: str) -> str:
    return f"{_DM}{s}{_R}"

def _green(s: str) -> str:
    return f"{_B}{_GRN}{s}{_R}"

def _red(s: str) -> str:
    return f"{_B}{_RED}{s}{_R}"

def _yellow(s: str) -> str:
    return f"{_B}{_Y}{s}{_R}"
import logging
import signal
import atexit
import re
import unicodedata
import requests
import datetime
import pytz
import psutil
from typing import Dict, List, Tuple, Optional
from icalendar import Calendar

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

TIMEZONE      = pytz.timezone(CONFIG.get("timezone", "Europe/Paris"))
CALENDARS     = CONFIG.get("calendars", [])
LOCK_FILE      = CONFIG.get("stats_lock_file", "stats.lock")
STATE_FILE     = CONFIG.get("stats_state_file", "stats_history.json")
ANALYSIS_FILE  = CONFIG.get("analysis_file", "analysis.json")
OBJECTIFS_FILE = "objectifs.json"

_sy      = CONFIG.get("school_year", {})
SY_MONTH = int(_sy.get("start_month", 7))
SY_DAY   = int(_sy.get("start_day", 25))

_raw_labels  = CONFIG.get("event_labels", [])
EVENT_LABELS = sorted(_raw_labels, key=len, reverse=True)

MY_CALENDARS = [c for c in CALENDARS if c.get("enable_course_hours", False)]

_SPECIAL_LABELS = {"RTT", "CONGES"}
_SUIVI_LABELS   = {"Suivi", "Observation", "Remarque"}
_DURATION_OVERRIDES = {"Serv : midi": 1.5, "Serv : soir": 1.5}  # durée réelle en heures

_last_state:    Dict = {}
_last_analysis: Dict = {}
_selected_sy:   str  = ""   # année scolaire sélectionnée

# ---------------------------------------------------------------------
# Logging : sans horodatage, sans préfixe INFO
# ---------------------------------------------------------------------
class _CleanFormatter(logging.Formatter):
    def format(self, record):
        if record.levelno >= logging.ERROR:
            return f"ERREUR: {record.getMessage()}"
        return record.getMessage()

_handler = logging.StreamHandler()
_handler.setFormatter(_CleanFormatter())
logging.root.handlers = []
logging.root.addHandler(_handler)
logging.root.setLevel(logging.INFO)

# ---------------------------------------------------------------------
# Lock
# ---------------------------------------------------------------------
def create_lock():
    if os.path.exists(LOCK_FILE):
        with open(LOCK_FILE, "r") as f:
            pid = int(f.read())
        if psutil.pid_exists(pid):
            logging.error("Une instance est déjà en cours")
            sys.exit(1)
        os.remove(LOCK_FILE)
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

atexit.register(lambda: os.path.exists(LOCK_FILE) and os.remove(LOCK_FILE))
signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

# ---------------------------------------------------------------------
# Utilitaires temps
# ---------------------------------------------------------------------
def ensure_datetime(dt):
    if isinstance(dt, datetime.date) and not isinstance(dt, datetime.datetime):
        dt = datetime.datetime.combine(dt, datetime.time.min)
    return TIMEZONE.localize(dt) if dt.tzinfo is None else dt.astimezone(TIMEZONE)

def round_to_quarter(hours: float) -> float:
    return round((hours * 60) / 15) * 15 / 60

def format_hours_hm(hours: float) -> str:
    m = int(round(hours * 60))
    return f"{m // 60}h{m % 60:02d}"

def eleve_hours(duration_h: float):
    """
    Retourne (h: float entier, warn: bool).
    < 30 min  → 0h, pas de warning.
    30-49 min → 0h, warn=True (slot non comptabilisable).
    ≥ 50 min  → entier le plus proche avec seuil à 50 min.
    """
    mins = round(duration_h * 60)
    if mins < 30:
        return 0.0, False
    if mins < 50:
        return 0.0, True
    h = mins // 60
    if mins % 60 >= 50:
        h += 1
    return float(h), False

def format_eleve_h(h: float) -> str:
    return f"{int(round(h))}h"

def _fmt_eleve(p: float, f: float) -> str:
    t = p + f
    if t == 0:
        return "0h"
    if p > 0 and f > 0:
        return f"{format_eleve_h(t)} ({int(round(p))}h + {int(round(f))}h fut.)"
    if f > 0:
        return f"{format_eleve_h(f)} (futur)"
    return format_eleve_h(p)

def _fmt_fmt(p: float, f: float, ded: float = 0.0, reg: float = 0.0) -> str:
    t = p + f
    dont_parts = []
    if ded > 0.001:
        dont_parts.append(f"{format_hours_hm(ded)} déd.")
    if reg > 0.001:
        dont_parts.append(f"{format_hours_hm(reg)} reg.")
    dont_str = (" -- dont " + " + ".join(dont_parts)) if dont_parts else ""

    if t == 0:
        return "0h00"
    if p > 0 and f > 0:
        return f"{format_hours_hm(t)} ({format_hours_hm(p)} + {format_hours_hm(f)} fut.{dont_str})"
    if f > 0:
        return f"{format_hours_hm(f)} (futur{dont_str})"
    if dont_str:
        return f"{format_hours_hm(p)}{dont_str}"
    return format_hours_hm(p)

# ---------------------------------------------------------------------
# Normalisation texte
# ---------------------------------------------------------------------
def normalize_for_match(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )

EVENT_LABELS_NORM = [(normalize_for_match(l), l) for l in EVENT_LABELS]

_SMALL_WORDS = {"de", "des", "du"}

def normalize_display(label: str) -> str:
    words = label.split()
    return " ".join(
        w.lower() if i > 0 and w.lower() in _SMALL_WORDS else w[0].upper() + w[1:]
        for i, w in enumerate(words)
    )

# ---------------------------------------------------------------------
# Année scolaire
# ---------------------------------------------------------------------
def get_school_year_label(d: datetime.date) -> str:
    sy = datetime.date(d.year, SY_MONTH, SY_DAY)
    return f"{d.year}-{d.year+1}" if d >= sy else f"{d.year-1}-{d.year}"

def school_year_bounds(label: str) -> Tuple[datetime.date, datetime.date]:
    y = int(label.split("-")[0])
    return (datetime.date(y, SY_MONTH, SY_DAY),
            datetime.date(y+1, SY_MONTH, SY_DAY) - datetime.timedelta(days=1))

# ---------------------------------------------------------------------
# Ordre pédagogique des classes
# ---------------------------------------------------------------------
CLASS_ORDER = [
    "4ème", "3ème A", "3ème B", "Sde PV", "Sde NJPF",
    "1ère CPH", "1ère AP", "Term CPH", "Term AP",
    "BTSA1 MVAOE", "BTSA2 MVAOE",
    "CAPA1JP A", "CAPA1JP B", "CAPA2 JP A", "TJEP1", "TJEP2"
]
CLASS_ORDER_INDEX = {c: i for i, c in enumerate(CLASS_ORDER)}

CYCLE_GROUPS = [
    ("4e / 3e",  ["4ème", "3ème A", "3ème B"]),
    ("2ndes",    ["Sde PV", "Sde NJPF"]),
    ("Bac Pro",  ["1ère CPH", "1ère AP", "Term CPH", "Term AP"]),
    ("BTSA",     ["BTSA1 MVAOE", "BTSA2 MVAOE"]),
    ("CAPA",     ["CAPA1JP A", "CAPA1JP B", "CAPA2 JP A"]),
    ("TJEP",     ["TJEP1", "TJEP2"]),
]
CLASS_TO_CYCLE = {cl: cycle for cycle, classes in CYCLE_GROUPS for cl in classes}

def class_sort_key(c):
    return (CLASS_ORDER_INDEX.get(c, 999), c)

# ---------------------------------------------------------------------
# Parsing SUMMARY — cours
# ---------------------------------------------------------------------
def is_dedouble(summary: str, description: str) -> bool:
    """
    Vrai dédoublement = classe scindée en 2 groupes (cours différents en parallèle).
    Faux positif = plusieurs enseignants sur le MÊME cours (le mot 'Dédoublement'
    apparaît dans la description mais tous les profs enseignent la même matière).
    Règle : si le cours du résumé apparaît ≥ 2 fois dans la description → pas un
    vrai dédoublement.
    """
    if "doublement" not in description.lower():
        return False
    m = re.search(r' - (.+?) salle:', summary, re.IGNORECASE)
    if not m:
        return True   # pas de cours identifiable → on garde l'ancien comportement
    course_name = m.group(1).strip()
    return description.lower().count(course_name.lower()) < 2


def parse_course_summary(summary: str) -> Optional[Tuple[str, str, str, str]]:
    if not summary:
        return None
    low = normalize_for_match(summary)
    if "cours" not in low:
        return None
    try:
        idx   = low.find("cours")
        after = summary[idx + 5:].lstrip(" :–-").strip()
        if "-" not in after:
            return None
        left, right = after.split("-", 1)
        classe = left.strip()
        if not classe:
            return None
        parts = right.strip().split()
        if len(parts) < 2:
            return None
        filiere = parts[0]
        module  = parts[1]
        nom     = " ".join(parts[2:]) if len(parts) > 2 else ""
        idx_s = nom.lower().find("salle")
        if idx_s != -1:
            nom = nom[:idx_s].rstrip()
        return classe, filiere, module, nom
    except Exception:
        return None

def course_label(filiere: str, module: str, nom: str) -> str:
    return f"[{filiere}] {module} {nom}".strip().rstrip()

def course_label_short(module: str, nom: str) -> str:
    return f"{module} {nom}".strip()

# ---------------------------------------------------------------------
# Correspondance libellé non-cours
# ---------------------------------------------------------------------
def match_event_label(summary: str) -> Optional[str]:
    s = normalize_for_match(summary.strip())
    for ln, lc in EVENT_LABELS_NORM:
        if s.startswith(ln):
            return lc
    return None

# ---------------------------------------------------------------------
# State file
# ---------------------------------------------------------------------
def load_state() -> Dict:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.warning(f"Lecture state impossible ({e})")
        return {}

def save_state(state: Dict):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Écriture state impossible : {e}")

def merge_events(stored: Dict, fresh: Dict, today: datetime.date) -> Tuple[Dict, int, int]:
    merged     = dict(fresh)
    nb_new     = sum(1 for k in fresh if k not in stored)
    nb_dropped = 0
    for key, ev in stored.items():
        if key in merged:
            continue
        try:
            if datetime.datetime.fromisoformat(ev["end_iso"]).date() < today:
                merged[key] = ev
            else:
                nb_dropped += 1
        except Exception:
            merged[key] = ev
    return merged, nb_new, nb_dropped

# ---------------------------------------------------------------------
# Extraction ICS
# ---------------------------------------------------------------------
def fetch_events(cal_config: Dict) -> Tuple[Dict, bool]:
    base = cal_config["url"]
    dp   = cal_config.get("fetch_date_params")
    urls = []
    if dp:
        sep = "&" if "?" in base else "?"
        urls.append(("élargie", base + sep + "&".join(f"{k}={v}" for k, v in dp.items())))
    urls.append(("standard", base))

    for label, url in urls:
        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            events: Dict = {}
            for c in Calendar.from_ical(resp.text).walk("VEVENT"):
                try:
                    uid  = str(c.get("UID", ""))
                    summ = str(c.get("SUMMARY", ""))
                    desc = str(c.get("DESCRIPTION", ""))
                    dts  = ensure_datetime(c.decoded("DTSTART"))
                    dte  = ensure_datetime(c.decoded("DTEND")) if "DTEND" in c else dts
                    key  = f"{uid}_{dts.isoformat()}"
                    events[key] = {"uid": uid, "summary": summ, "description": desc,
                                   "start_iso": dts.isoformat(), "end_iso": dte.isoformat()}
                except Exception:
                    pass
            return events, True
        except Exception:
            pass
    logging.error("Toutes les tentatives de récupération ICS ont échoué")
    return {}, False

# ---------------------------------------------------------------------
# Analyse par année scolaire
# ---------------------------------------------------------------------
def _empty_bucket(sy_label: str) -> Dict:
    first, last = school_year_bounds(sy_label)
    return {
        "sy_start": first.isoformat(), "sy_end": last.isoformat(),
        "period_start": None, "period_end": None,
        "course_hours": {
            "total_past": 0.0, "total_future": 0.0,
            "total_past_fmt": 0.0, "total_future_fmt": 0.0,
            "total_ded_past": 0.0, "total_ded_future": 0.0,
            "total_reg_past": 0.0, "total_reg_future": 0.0,
            "by_class": {}, "by_course": {}, "by_class_and_course": {},
        },
        "event_counts": {}, "unrecognized": {},
    }

def analyze_events(events: Dict, today: datetime.date) -> Dict:
    # Pré-passe : détection des regroupements
    # Un créneau est "regroupé" si plusieurs classes ont le même cours au même moment
    slot_classes: Dict = {}
    for ev in events.values():
        parsed = parse_course_summary(ev.get("summary", ""))
        if not parsed:
            continue
        cl2, fil2, mod2, nom2 = parsed
        s = ev.get("start_iso") or ev.get("start_dt", "")
        e = ev.get("end_iso")   or ev.get("end_dt",   "")
        key = (s, e, fil2, mod2, nom2)
        slot_classes.setdefault(key, set()).add(cl2)
    regroupement_slots = {k for k, classes in slot_classes.items() if len(classes) > 1}

    by_year: Dict = {}
    seen_slots: set = set()  # déduplication par (start_iso, end_iso, summary)

    for ev in events.values():
        s_raw = ev.get("start_iso") or ev.get("start_dt", "")
        e_raw = ev.get("end_iso")   or ev.get("end_dt",   "")
        slot = (s_raw, e_raw, ev.get("summary", ""))
        if slot in seen_slots:
            continue
        seen_slots.add(slot)
        summ = ev.get("summary", "")
        try:
            start = datetime.datetime.fromisoformat(s_raw)
            end   = datetime.datetime.fromisoformat(e_raw)
        except Exception:
            continue

        sy = get_school_year_label(start.date())
        if sy not in by_year:
            by_year[sy] = _empty_bucket(sy)
        bk = by_year[sy]

        s_iso = start.date().isoformat()
        e_iso = end.date().isoformat()
        if bk["period_start"] is None or s_iso < bk["period_start"]: bk["period_start"] = s_iso
        if bk["period_end"]   is None or e_iso > bk["period_end"]:   bk["period_end"]   = e_iso

        past     = end.date() < today
        duration = (end - start).total_seconds() / 3600

        parsed = parse_course_summary(summ)
        if parsed:
            classe, filiere, module, nom = parsed
            ch       = bk["course_hours"]
            regroupe = (s_raw, e_raw, filiere, module, nom) in regroupement_slots
            dedouble = is_dedouble(ev.get("summary", ""), ev.get("description", ""))

            # --- Heures élève ---
            eh_raw, warn = eleve_hours(duration)
            if warn:
                logging.warning(
                    f"  /!\\ Slot {round(duration*60)}min (30-49 min) non comptabilisé"
                    f" (élève) : {summ[:50]} le {s_iso}"
                )
            coeff_eleve = 0.5 if (dedouble and not regroupe) else 1.0
            eleve_h = eh_raw * coeff_eleve

            # --- Heures formateur ---
            coeff_fmt   = 0.5 if regroupe else 1.0
            dur_fmt     = duration * coeff_fmt
            ded_contrib = duration if (dedouble and not regroupe) else 0.0
            reg_contrib = dur_fmt  if regroupe                    else 0.0

            ch["total_past"      if past else "total_future"    ] += eleve_h
            ch["total_past_fmt"  if past else "total_future_fmt"] += dur_fmt
            ch["total_ded_past"  if past else "total_ded_future"] += ded_contrib
            ch["total_reg_past"  if past else "total_reg_future"] += reg_contrib

            # Vecteur : [ep, ef, fp, ff, dp, df, rp, rf]
            def _acc(d, key):
                if key not in d: d[key] = [0.0] * 8
                d[key][0 if past else 1] += eleve_h
                d[key][2 if past else 3] += dur_fmt
                d[key][4 if past else 5] += ded_contrib
                d[key][6 if past else 7] += reg_contrib

            _acc(ch["by_class"], classe)
            ck = f"{filiere}|{module}|{nom}"
            _acc(ch["by_course"], ck)
            if classe not in ch["by_class_and_course"]:
                ch["by_class_and_course"][classe] = {}
            _acc(ch["by_class_and_course"][classe], ck)
            continue

        label = match_event_label(summ)
        if label:
            dur_label = _DURATION_OVERRIDES.get(label, duration)
            ec = bk["event_counts"]
            if label not in ec: ec[label] = {"count": 0, "past_h": 0.0, "fut_h": 0.0}
            ec[label]["count"] += 1
            ec[label]["past_h" if past else "fut_h"] += dur_label
            continue

        ur = bk["unrecognized"]
        if summ not in ur: ur[summ] = {"count": 0, "first": s_iso, "last": e_iso}
        ur[summ]["count"] += 1
        if s_iso < ur[summ]["first"]: ur[summ]["first"] = s_iso
        if e_iso > ur[summ]["last"]:  ur[summ]["last"]  = e_iso

    return by_year

# ---------------------------------------------------------------------
# Sauvegarde analysis.json
# ---------------------------------------------------------------------
def save_analysis(all_analysis: Dict):
    def _fmtv(v):
        return {
            "eleve_past": v[0], "eleve_fut": v[1], "eleve_total": v[0]+v[1],
            "fmt_past":   v[2], "fmt_fut":   v[3], "fmt_total":   v[2]+v[3],
            "ded":        v[4]+v[5], "reg":   v[6]+v[7],
        }
    output = {}
    for cn, by_year in all_analysis.items():
        output[cn] = {}
        for sy, bk in by_year.items():
            ch = bk["course_hours"]
            output[cn][sy] = {
                "sy_start": bk["sy_start"], "sy_end": bk["sy_end"],
                "period_start": bk["period_start"], "period_end": bk["period_end"],
                "course_hours": {
                    "eleve_past":  ch["total_past"],   "eleve_fut":  ch["total_future"],
                    "fmt_past":    ch["total_past_fmt"],"fmt_fut":    ch["total_future_fmt"],
                    "ded_past":    ch["total_ded_past"],"ded_fut":    ch["total_ded_future"],
                    "reg_past":    ch["total_reg_past"],"reg_fut":    ch["total_reg_future"],
                    "by_class":  {k: _fmtv(v) for k, v in ch["by_class"].items()},
                    "by_course": {k: _fmtv(v) for k, v in ch["by_course"].items()},
                    "by_class_and_course": {
                        cl: {ck: _fmtv(v) for ck, v in courses.items()}
                        for cl, courses in ch["by_class_and_course"].items()
                    },
                },
                "event_counts": bk["event_counts"],
                "unrecognized_count": len(bk["unrecognized"]),
                "unrecognized_list": dict(sorted(bk["unrecognized"].items(),
                                                 key=lambda x: -x[1]["count"])),
            }
    try:
        with open(ANALYSIS_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Écriture analysis impossible : {e}")

# ---------------------------------------------------------------------
# Affichage — constantes et helpers
# ---------------------------------------------------------------------
SEP  = "=" * 80
THIN = "-" * 80
CW   = 20   # largeur colonne libellé (sections principales)
CW2  = 18   # largeur colonne libellé (sections indentées)

_OBJ_E_W  = 18   # largeur cellule ELEVE  (ex: "88h/99h (89%)" = 14 chars max)
_OBJ_F_W  = 22   # largeur cellule FORMATEUR (ex: "102h20/99h00 (103%)" = 19 chars max)
_OBJ_LBL  = 32   # largeur colonne label (tronquée si dépassée)
_OBJ_CW   = 30   # largeur label cours (objectifs)

def _tr(s: str, w: int) -> str:
    return s if len(s) <= w else s[:w-1] + "…"

def _fd(iso: Optional[str]) -> str:
    return datetime.date.fromisoformat(iso).strftime("%d/%m/%Y") if iso else "?"

_ELEVE_W = 23   # largeur fixe colonne ELEVE : "999h (999h + 999h fut.)"

def _line_cours(label: str, v: list, cw: int = None, nested: bool = False) -> str:
    """Ligne : label  ELEVE: ...| FORMATEUR: ..."""
    if cw is None:
        cw = CW2 if nested else CW
    indent = "      " if nested else "    "
    ep, ef = v[0], v[1]
    fp, ff = v[2], v[3]
    ded    = v[4] + v[5]
    reg    = v[6] + v[7]
    return (f"{indent}{_tr(label, cw):<{cw}}"
            f"  ELEVE: {_fmt_eleve(ep, ef):<{_ELEVE_W}}"
            f"| FORMATEUR: {_fmt_fmt(fp, ff, ded, reg)}")

# ---------------------------------------------------------------------
# Helpers factorisation v5.19
# ---------------------------------------------------------------------

def _current_cn_sy() -> tuple:
    """Retourne (calendar_name, school_year) courants."""
    cn = next(iter(_last_analysis), "")
    sy = sorted(_last_analysis.get(cn, {}).keys())[-1] if cn else ""
    return cn, sy


def _ev_start(ev: dict) -> str:
    return ev.get("start_iso") or ev.get("start_dt", "")

def _ev_end(ev: dict) -> str:
    return ev.get("end_iso") or ev.get("end_dt", "")


def _fmt_ded_reg(ded: float, reg: float) -> str:
    """Retourne ' (dt XhXX D + XhXX R)' ou '' si rien."""
    parts = []
    if ded > 0.001: parts.append(f"{format_hours_hm(ded)} D")
    if reg > 0.001: parts.append(f"{format_hours_hm(reg)} R")
    return f" (dt {' + '.join(parts)})" if parts else ""


def _row_yellow(lbl_f: str, e_padded: str, f_str: str) -> str:
    return f"{_B}{_Y}      {lbl_f} : {e_padded}|  {f_str}{_R}"

def _row_dim(lbl_f: str, e_padded: str, f_str: str) -> str:
    return (f"{_DM}      {lbl_f} : {_R}"
            f"{_B}{_RED}{e_padded}{_R}"
            f"|  "
            f"{_DM}{f_str}{_R}")

def _row_bold(lbl_f: str, e_padded: str, f_str: str) -> str:
    return (f"{_B}      {lbl_f} : {_R}"
            f"{_B}{_RED}{e_padded}{_R}"
            f"|  "
            f"{_R}{f_str}{_R}")


def _print_green_header(cn: str, sy: str = ""):
    """Imprime le bloc d'en-tête vert standard (SEP + CALENDRIER + ANNEE + SEP)."""
    print(_green(f"\n  {SEP}"))
    if cn:
        print(_green(f"  CALENDRIER : {cn}"))
    if sy:
        print(_green(f"  ANNEE SCOLAIRE {sy}"))
    print(_green(f"  {SEP}"))


def _compute_contributions(dur: float, dedouble: bool, regroupe: bool,
                           faux_positif: bool = False) -> tuple:
    """Retourne (eh, fh, dc, rc) — contributions heures élève, formateur, dédoublé, regroupé."""
    eh_raw, _ = eleve_hours(dur)
    coeff_el  = 0.5 if (dedouble and not regroupe and not faux_positif) else 1.0
    coeff_fmt = 0.5 if regroupe else 1.0
    eh = eh_raw * coeff_el
    fh = dur * coeff_fmt
    dc = dur if (dedouble and not regroupe and not faux_positif) else 0.0
    rc = fh  if regroupe else 0.0
    return eh, fh, dc, rc

# ---------------------------------------------------------------------
# Blocs d'affichage par section
# ---------------------------------------------------------------------

def _disp_year_header(sy: str, bk: Dict):
    """En-tête d'année : une seule ligne + avertissement si données tardives."""
    sy_start = datetime.date.fromisoformat(bk["sy_start"])
    ps = bk["period_start"]
    pe = bk["period_end"]
    period_str = f"  ({_fd(ps)} → {_fd(pe)})" if (ps and pe) else ""
    logging.info(_green(f"  ANNEE SCOLAIRE {sy}{period_str}"))
    # Pas de THIN ici : chaque section display function commence par THIN


def _compact_line(label: str, v: list, bold: bool = False, yellow: bool = False) -> str:
    """Ligne compacte label : Elève ... | Formateur ... sans progression."""
    e_str, f_str = _compact_parts(v, {})
    lbl_f    = f"{_trunc_lbl(label):<{_PROG_LBL_W}}"
    e_padded = f"{e_str:<{_PROG_ELEVE_W}}"
    if yellow:
        return _row_yellow(lbl_f, e_padded, f_str)
    if bold:
        return _row_bold(lbl_f, e_padded, f_str)
    return _row_dim(lbl_f, e_padded, f_str)


def _disp_course_total(ch: Dict):
    """Ligne TOTAL HEURES DE COURS."""
    v = [
        ch["total_past"],     ch["total_future"],
        ch["total_past_fmt"], ch["total_future_fmt"],
        ch["total_ded_past"], ch["total_ded_future"],
        ch["total_reg_past"], ch["total_reg_future"],
    ]
    ep, ef, fp, ff = v[0], v[1], v[2], v[3]
    ded = v[4] + v[5]
    reg = v[6] + v[7]
    if round(ef) > 0:
        e_str = f"Elève : {int(round(ep))}h + {int(round(ef))}h (p) = {int(round(ep + ef))}h"
    else:
        e_str = f"Elève : {int(round(ep))}h"
    dont_str = _fmt_ded_reg(ded, reg)
    if ff > 0.01:
        f_str = f"Formateur : {format_hours_hm(fp)} + {format_hours_hm(ff)} (p) = {format_hours_hm(fp + ff)}{dont_str}"
    else:
        f_str = f"Formateur : {format_hours_hm(fp)}{dont_str}"
    lbl_f    = f"{'TOTAL HEURES DE COURS':<{_PROG_LBL_W}}"
    e_padded = f"{e_str:<{_PROG_ELEVE_W}}"
    logging.info(SEP)
    logging.info(_row_yellow(lbl_f, e_padded, f_str))


def _disp_par_classe(ch: Dict):
    """Section : HEURES par CLASSE."""
    if not ch["by_class"]:
        logging.info("    (aucune CLASSE)")
        return
    logging.info(_bold("  HEURES par CLASSE"))
    for cl in sorted(ch["by_class"], key=class_sort_key):
        logging.info(_compact_line(cl, ch["by_class"][cl], bold=True))




def _compact_parts(v: list, obj: dict) -> tuple:
    """Retourne (eleve_str, fmt_str) en texte brut pour l'affichage compact."""
    ep, ef, fp, ff = v[0], v[1], v[2], v[3]
    ce = float(obj.get("eleve", 0)) if obj else 0
    cf = float(obj.get("fmt",   0)) if obj else 0

    if ce > 0:
        pct_act = int(round(ep / ce * 100))
        pct_tot = int(round((ep + ef) / ce * 100))
        if round(ef) > 0:
            e_str = (f"Elève : {int(round(ep))}h ({pct_act}%)"
                     f" + {int(round(ef))}h (p)"
                     f" = {int(round(ep + ef))}h [/{int(round(ce))}h, {pct_tot}%]")
        else:
            e_str = f"Elève : {int(round(ep))}h ({pct_act}%) [/{int(round(ce))}h, {pct_tot}%]"
    else:
        if round(ef) > 0:
            e_str = f"Elève : {int(round(ep))}h + {int(round(ef))}h (p) = {int(round(ep + ef))}h"
        else:
            e_str = f"Elève : {int(round(ep))}h"

    if cf > 0:
        pct_act = int(round(fp / cf * 100))
        pct_tot = int(round((fp + ff) / cf * 100))
        if ff > 0.01:
            f_str = (f"Formateur : {format_hours_hm(fp)} ({pct_act}%)"
                     f" + {format_hours_hm(ff)} (p)"
                     f" = {format_hours_hm(fp + ff)} [/{format_hours_hm(cf)}, {pct_tot}%]")
        else:
            f_str = f"Formateur : {format_hours_hm(fp)} ({pct_act}%) [/{format_hours_hm(cf)}, {pct_tot}%]"
    else:
        if ff > 0.01:
            f_str = f"Formateur : {format_hours_hm(fp)} + {format_hours_hm(ff)} (p) = {format_hours_hm(fp + ff)}"
        else:
            f_str = f"Formateur : {format_hours_hm(fp)}"

    return e_str, f_str


_PROG_LBL_W   = 38   # largeur fixe du label cours (troncature si dépassé)
_PROG_ELEVE_W = 47   # largeur fixe de la colonne ELEVE (padding si plus court)

def _trunc_lbl(s: str) -> str:
    return s if len(s) <= _PROG_LBL_W else s[:_PROG_LBL_W - 1] + "…"


def _disp_par_classe_et_cours(ch: Dict):
    """Section : Par CLASSE et Par COURS, groupées par cycle."""
    if not ch["by_class_and_course"]:
        logging.info("    (aucun COURS)")
        return
    logging.info("  Par CLASSE et Par COURS")

    objectifs = load_objectifs()
    cn, sy = _current_cn_sy()

    grand = [0.0] * 8
    current_cycle = None

    for cl in sorted(ch["by_class_and_course"], key=class_sort_key):
        cycle = CLASS_TO_CYCLE.get(cl, "Autres")
        if cycle != current_cycle:
            if current_cycle is not None:
                logging.info("")
            current_cycle = cycle
            dashes = "─" * max(1, 20 - len(cycle))
            logging.info(_bold(f"  ── {cycle} {dashes}"))

        v_cl = ch["by_class"][cl]
        for i in range(8):
            grand[i] += v_cl[i]

        logging.info(_bold(f"    {cl}"))
        courses = ch["by_class_and_course"][cl]

        # Collecte des lignes (lbl_fixed, eleve_str, fmt_str, is_total)
        lines_data = []
        for ck in sorted(courses):
            fil, mod, nom = ck.split("|", 2)
            lbl = _trunc_lbl(course_label_short(mod, nom))
            obj = objectifs.get(cn, {}).get(sy, {}).get(cl, {}).get(ck, {})
            e_str, f_str = _compact_parts(courses[ck], obj)
            lines_data.append((f"{lbl:<{_PROG_LBL_W}}", e_str, f_str, False))
        if len(courses) > 1:
            e_str, f_str = _compact_parts(v_cl, {})
            lines_data.append((f"{'TOTAL':<{_PROG_LBL_W}}", e_str, f_str, True))

        # Affichage : label fixe + ELEVE padé à _PROG_ELEVE_W → | toujours aligné
        for lbl_f, e_str, f_str, is_total in lines_data:
            e_padded = f"{e_str:<{_PROG_ELEVE_W}}"
            if is_total:
                line = _row_yellow(lbl_f, e_padded, f_str)
            else:
                line = _row_dim(lbl_f, e_padded, f_str)
            logging.info(line)

    logging.info(SEP)
    ep, ef, fp, ff = grand[0], grand[1], grand[2], grand[3]
    ded = grand[4] + grand[5]
    reg = grand[6] + grand[7]

    # Somme des objectifs sur toutes les classes/cours
    obj_all = objectifs
    cn, sy = _current_cn_sy()
    sum_ce = sum(float(v.get("eleve", 0))
                 for cl_d in obj_all.get(cn, {}).get(sy, {}).values()
                 for v in cl_d.values())
    sum_cf = sum(float(v.get("fmt", 0))
                 for cl_d in obj_all.get(cn, {}).get(sy, {}).values()
                 for v in cl_d.values())

    cible_e = (f" [/{int(round(sum_ce))}h, {int(round((ep + ef) / sum_ce * 100))}%]"
               if sum_ce > 0 else "")
    if round(ef) > 0:
        e_gt = f"Elève : {int(round(ep))}h + {int(round(ef))}h (p) = {int(round(ep + ef))}h{cible_e}"
    else:
        e_gt = f"Elève : {int(round(ep))}h{cible_e}"

    dont_str = _fmt_ded_reg(ded, reg)
    cible_f = (f" [/{format_hours_hm(sum_cf)}, {int(round((fp + ff) / sum_cf * 100))}%]"
               if sum_cf > 0 else "")
    if ff > 0.01:
        f_gt = f"Formateur : {format_hours_hm(fp)} + {format_hours_hm(ff)} (p) = {format_hours_hm(fp + ff)}{dont_str}{cible_f}"
    else:
        f_gt = f"Formateur : {format_hours_hm(fp)}{dont_str}{cible_f}"

    lbl_gt   = f"{'GRAND TOTAL':<{_PROG_LBL_W}}"
    e_padded = f"{e_gt:<{_PROG_ELEVE_W}}"
    logging.info(_row_yellow(lbl_gt, e_padded, f_gt))


def _disp_autres_evenements(bk: Dict):
    """Section : Événements Hors COURS.
    RTT et CONGÉS séparés après le total principal.
    Sous-total RTT+CONGÉS uniquement si les deux catégories sont présentes.
    """
    logging.info("  Événements Hors COURS")
    ec = bk["event_counts"]

    main_ec    = {k: v for k, v in ec.items() if k not in _SPECIAL_LABELS and k not in _SUIVI_LABELS}
    special_ec = {k: v for k, v in ec.items() if k in _SPECIAL_LABELS}
    suivi_ec   = {k: v for k, v in ec.items() if k in _SUIVI_LABELS}

    sep_full = "    " + "─" * 68
    sep_nb   = "    " + "─" * 41

    def _section(titre, data, counts_only=False):
        logging.info("")
        if counts_only:
            logging.info(f"{_B}{_Y}    {titre:<35}{_R}  {'Nb':>4}")
            logging.info(sep_nb)
        else:
            logging.info(f"{_B}{_Y}    {titre:<35}{_R}  {'Nb':>4}  {'Passées':>8}  {'Planif.':>8}  {'Total':>8}")
            logging.info(sep_full)
        tot_n = tot_ph = tot_fh = 0
        for lbl in sorted(data):
            d  = data[lbl]
            ph = d["past_h"]; fh = d["fut_h"]
            tot_n += d["count"]; tot_ph += ph; tot_fh += fh
            if counts_only:
                logging.info(f"    {normalize_display(lbl):<35}  {d['count']:>4}")
            else:
                logging.info(
                    f"    {normalize_display(lbl):<35}  {d['count']:>4}  "
                    f"{format_hours_hm(ph):>8}  {format_hours_hm(fh):>8}  "
                    f"{format_hours_hm(ph+fh):>8}"
                )
        if counts_only:
            logging.info(sep_nb)
            logging.info(_yellow(f"    {'TOTAL':<35}  {tot_n:>4}"))
        else:
            logging.info(sep_full)
            logging.info(_yellow(
                f"    {'TOTAL':<35}  {tot_n:>4}  "
                f"{format_hours_hm(tot_ph):>8}  {format_hours_hm(tot_fh):>8}  "
                f"{format_hours_hm(tot_ph+tot_fh):>8}"
            ))

    _section("Autres",        main_ec)
    _section("RTT et CONGÉS", special_ec)
    _section("Discipline",    suivi_ec, counts_only=True)


def _disp_non_reconnus(bk: Dict):
    """Avertissement libellés non reconnus."""
    ur = bk["unrecognized"]
    if ur:
        firsts = [v["first"] for v in ur.values()]
        lasts  = [v["last"]  for v in ur.values()]
        logging.warning(
            f"  /!\\ {len(ur)} libellé(s) non reconnu(s) "
            f"(du {_fd(min(firsts))} au {_fd(max(lasts))})"
        )
        logging.warning("      → Complétez event_labels dans config.json :")
        for txt, data in sorted(ur.items(), key=lambda x: -x[1]["count"]):
            d1 = _fd(data["first"]); d2 = _fd(data["last"])
            logging.warning(
                f"      [{data['count']:>3}x]  {txt:<45}  "
                f"({'→'.join([d1, d2]) if d1 != d2 else d1})"
            )

# ---------------------------------------------------------------------
# Chargement des données (sans affichage)
# ---------------------------------------------------------------------
def _load_data(state: Dict) -> Dict:
    """Récupère, fusionne et analyse les calendriers. Met à jour les globaux.
    Silencieux : aucun affichage. Retourne le state mis à jour."""
    global _last_state, _last_analysis
    today        = datetime.datetime.now(TIMEZONE).date()
    all_analysis = {}

    for cal in MY_CALENDARS:
        cn        = cal.get("name", "Inconnu")
        fresh, ok = fetch_events(cal)
        if ok:
            stored = state.get(cn, {})
            merged, _, _ = merge_events(stored, fresh, today)
            state[cn] = merged
            stored = merged
        else:
            stored = state.get(cn, {})
        by_year = analyze_events(stored, today)
        all_analysis[cn] = by_year

    save_state(state)
    save_analysis(all_analysis)
    _last_state    = {cn: state.get(cn, {}) for cn in (c.get("name") for c in MY_CALENDARS)}
    _last_analysis = all_analysis
    return state

# ---------------------------------------------------------------------
# Chargement et affichage d'une section
# ---------------------------------------------------------------------
def _load_and_show(state: Dict, section: int) -> Dict:
    state = _load_data(state)

    for cn, by_year in _last_analysis.items():
        logging.info("")
        logging.info(_green(SEP))
        logging.info(_green(f"  CALENDRIER : {cn}"))
        for sy in sorted(by_year.keys()):
            if _selected_sy and sy != _selected_sy:
                continue
            bk = by_year[sy]
            ch = bk["course_hours"]

            _disp_year_header(sy, bk)
            logging.info(_green(SEP))

            if section == 1:
                _disp_par_classe_et_cours(ch)

            elif section == 2:
                _disp_par_classe(ch)
                _disp_course_total(ch)

            elif section == 3:
                _disp_autres_evenements(bk)
                _disp_non_reconnus(bk)

            logging.info(SEP)

    return state

# ---------------------------------------------------------------------
# Option 5 : détail par CLASSE et par COURS
# ---------------------------------------------------------------------
_JOURS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]

# Format unique utilisé pour l'en-tête ET les lignes de données du tableau détail
# Colonnes : date(17) début(5) fin(5) durée(8) std(5) statut(12) dédoublé
_DET_FMT = "  {:<4}  {:<17}  {:<22}  {:<12}  {}"
_DET_SEP = "─" * 70


def _collect_class_courses() -> List[Tuple[str, str]]:
    seen = {}
    for by_year in _last_analysis.values():
        for sy, bk in by_year.items():
            if _selected_sy and sy != _selected_sy:
                continue
            for cl, courses in bk["course_hours"]["by_class_and_course"].items():
                for ck in courses:
                    seen[(cl, ck)] = True
    return sorted(seen.keys(), key=lambda x: (class_sort_key(x[0]), x[1]))


def _get_detail_events(classe: str, course_key: str, today: datetime.date) -> List[tuple]:
    fil, mod, nom = course_key.split("|", 2)

    slot_classes: Dict = {}
    for stored in _last_state.values():
        for ev in stored.values():
            parsed = parse_course_summary(ev.get("summary", ""))
            if not parsed:
                continue
            cl2, fil2, mod2, nom2 = parsed
            if fil2 != fil or mod2 != mod or nom2 != nom:
                continue
            s = _ev_start(ev)
            e = _ev_end(ev)
            slot_classes.setdefault((s, e), set()).add(cl2)
    regroupement_slots = {sl for sl, cls in slot_classes.items() if len(cls) > 1}

    results = []
    seen_slots: set = set()
    for stored in _last_state.values():
        for ev in stored.values():
            parsed = parse_course_summary(ev.get("summary", ""))
            if not parsed:
                continue
            cl, fil2, mod2, nom2 = parsed
            if cl != classe or f"{fil2}|{mod2}|{nom2}" != course_key:
                continue
            try:
                start    = datetime.datetime.fromisoformat(_ev_start(ev) or ev["start_dt"])
                end      = datetime.datetime.fromisoformat(_ev_end(ev)   or ev["end_dt"])
                slot     = (start.isoformat(), end.isoformat())
                if slot in seen_slots:
                    continue
                seen_slots.add(slot)
                dur      = (end - start).total_seconds() / 3600
                if _selected_sy and get_school_year_label(start.date()) != _selected_sy:
                    continue
                past     = end.date() < today
                dedouble = is_dedouble(ev.get("summary", ""), ev.get("description", ""))
                regroupe = slot in regroupement_slots
                results.append((start, end, dur, past, dedouble, regroupe))
            except Exception:
                continue
    return sorted(results, key=lambda x: x[0])


def _merge_consecutive_events(evts):
    """Fusionne uniquement la paire 15:25-16:25 + 16:25-17:30 (même jour, même statut)."""
    if not evts:
        return evts
    merged = []
    i = 0
    while i < len(evts):
        start, end, dur, past, dedouble, regroupe = evts[i]
        if (i + 1 < len(evts)
                and start.strftime('%H:%M') == '15:25'
                and end.strftime('%H:%M') == '16:25'
                and evts[i + 1][0].strftime('%H:%M') == '16:25'
                and evts[i + 1][1].strftime('%H:%M') == '17:30'
                and evts[i + 1][0].date() == start.date()
                and evts[i + 1][4] == dedouble
                and evts[i + 1][5] == regroupe):
            _, end2, dur2, _, _, _ = evts[i + 1]
            merged.append((start, end2, dur + dur2, past, dedouble, regroupe))
            i += 2
        else:
            merged.append(evts[i])
            i += 1
    return merged


def _show_detail(classe: str, course_key: str):
    today = datetime.datetime.now(TIMEZONE).date()
    fil, mod, nom = course_key.split("|", 2)
    lbl_court = course_label_short(mod, nom)
    evts = _merge_consecutive_events(_get_detail_events(classe, course_key, today))

    cn, sy = _current_cn_sy()
    _print_green_header(cn, sy)

    print(f"\n  {_DET_SEP}")
    print(_yellow(f"  CLASSE : {classe}"))
    print(_yellow(f"  COURS  : {lbl_court}"))
    print(f"  {_DET_SEP}")

    ep = ef = fp = ff = dp = df = rp = rf = 0.0

    nb_dedouble = sum(1 for _, _, _, _, ded, reg in evts if ded and not reg)

    seq_n = 0
    dedo_pending = False

    for start, end, dur, past, dedouble, regroupe in evts:
        day      = _JOURS[start.weekday()]
        date_str = f"{day}. {start.strftime('%d/%m/%Y')}"
        faux_positif  = dedouble and not regroupe and nb_dedouble <= 2
        trop_court    = round(dur * 60) < 30
        if regroupe:
            flag = "Regroupé"
        elif faux_positif:
            flag = "Faux positif (?), non compté dédoublé."
        elif dedouble:
            flag = "Dédoublé"
        elif trop_court:
            flag = "Non compté pour les ELEVES"
        else:
            flag = ""
        time_rng = f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')} ({format_hours_hm(dur)})"

        eh, fh, dc, rc = _compute_contributions(dur, dedouble, regroupe, faux_positif)

        # Numérotation des séances
        if dedouble and not faux_positif and not regroupe:
            if not dedo_pending:
                seq_n += 1
                num_label = f"{seq_n:>2}.a"
                dedo_pending = True
            else:
                num_label = f"{seq_n:>2}.b"
                dedo_pending = False
        else:
            seq_n += 1
            num_label = f"{seq_n:>2}"
            dedo_pending = False

        statut = "Passé" if past else "Planifié"
        _, warn = eleve_hours(dur)
        if warn:
            statut += " /!\\"
        print(_DET_FMT.format(num_label, date_str, time_rng, statut, flag))

        if past:
            ep += eh; fp += fh; dp += dc; rp += rc
        else:
            ef += eh; ff += fh; df += dc; rf += rc

    total_eleve = int(round(ep + ef))
    seq2h = total_eleve / 2
    if seq2h > 0:
        seq_fmt = int(seq2h) if seq2h == int(seq2h) else f"{seq2h:.1f}"
        seq_str = f", soit {seq_fmt} séquences de 2h"
    else:
        seq_str = ""

    # Progression vers l'objectif pour ce cours
    objectifs = load_objectifs()
    cn, sy = _current_cn_sy()
    obj = objectifs.get(cn, {}).get(sy, {}).get(classe, {}).get(course_key, {})
    ce = float(obj.get("eleve", 0))
    cf = float(obj.get("fmt",   0))

    prog_e = ""
    if ce > 0:
        pct_e_act = int(round(ep / ce * 100))
        pct_e_fut = int(round((ep + ef) / ce * 100))
        prog_e = (f" Progression actuelle : {int(round(ep))}/{int(round(ce))} ({pct_e_act}%),"
                  f" future : {int(round(ep + ef))}/{int(round(ce))} ({pct_e_fut}%)")

    prog_f = ""
    if cf > 0:
        pct_f_act = fp / cf * 100
        pct_f_fut = (fp + ff) / cf * 100
        prog_f = (f" Progression actuelle : {format_hours_hm(fp)}/{format_hours_hm(cf)} ({pct_f_act:.0f}%),"
                  f" future : {format_hours_hm(fp + ff)}/{format_hours_hm(cf)} ({pct_f_fut:.0f}%)")

    print(f"  {_DET_SEP}")
    print(_red(f"  ELEVES    : {_fmt_eleve(ep, ef)}{seq_str}.{prog_e}"))
    print(_yellow(f"  FORMATEUR : {_fmt_fmt(fp, ff, dp+df, rp+rf)}.{prog_f}"))
    print(f"  {_DET_SEP}")


def run_option_5():
    if not _last_analysis:
        print("  Aucune donnée — lancez d'abord une option Statistiques (1 à 4).")
        return

    class_courses = _collect_class_courses()
    if not class_courses:
        print("  Aucun COURS trouvé dans les données.")
        return

    while True:
        print(f"\n  {'─'*70}")
        print("  SOUS-MENU : Détail par CLASSE et par COURS")
        print(f"  {'─'*70}")
        for i, (cl, ck) in enumerate(class_courses, 1):
            fil, mod, nom = ck.split("|", 2)
            lbl = course_label_short(mod, nom)
            print(f"   ►{i:>4}.  {cl:<16} {lbl}")
        print()
        print("   ►   0.  Retour au menu principal")
        print(f"  {'─'*70}")

        choice = input("  Votre choix : ").strip()
        if choice == "0":
            break
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(class_courses):
                _show_detail(*class_courses[idx])
                input("\n  Appuyez sur Entrée pour continuer...")
            else:
                print("  Numéro invalide.")
        except ValueError:
            print("  Option invalide.")

# ---------------------------------------------------------------------
# Menu 5 : 4 Semaines suivantes
# ---------------------------------------------------------------------
_JOURS_LONG  = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
_MOIS_COURT  = ["jan.", "fév.", "mar.", "avr.", "mai", "juin",
                "juil.", "août", "sep.", "oct.", "nov.", "déc."]

def _fmt_date_court(d: datetime.date) -> str:
    return f"{d.day} {_MOIS_COURT[d.month - 1]}"

_ANSI_CYAN_LEN = len(_B) + len(_RED) + len(_R)  # compensation padding pour trng coloré
_W5_FMT = "    {:<17}  {:<22}  {:<35}  {}"
_W5_SEP = "-" * 84

def run_menu_5weeks():
    today = datetime.datetime.now(TIMEZONE).date()

    # Chargement des données
    if _last_state:
        sources = _last_state
    else:
        raw = load_state()
        sources = {c["name"]: raw.get(c["name"], {}) for c in MY_CALENDARS}
    if not any(sources.values()):
        print("  Aucune donnée — lancez d'abord une option Statistiques (1 à 3).")
        return

    monday = today - datetime.timedelta(days=today.weekday())
    end_date = monday + datetime.timedelta(weeks=4)

    # Détection des regroupements sur la période
    slot_classes: Dict = {}
    for evts in sources.values():
        for ev in evts.values():
            parsed = parse_course_summary(ev.get("summary", ""))
            if not parsed:
                continue
            cl, fil, mod, nom = parsed
            s = ev.get("start_iso", "")
            e = ev.get("end_iso", "")
            try:
                if monday <= datetime.datetime.fromisoformat(s).date() < end_date:
                    slot_classes.setdefault((s, e, fil, mod, nom), set()).add(cl)
            except Exception:
                pass
    reg_slots = {k for k, cls in slot_classes.items() if len(cls) > 1}

    # Collecte et tri des événements
    all_evts = []
    for evts in sources.values():
        for ev in evts.values():
            s_raw = ev.get("start_iso", "")
            e_raw = ev.get("end_iso", s_raw)
            try:
                start = datetime.datetime.fromisoformat(s_raw)
                end   = datetime.datetime.fromisoformat(e_raw)
                if monday <= start.date() < end_date:
                    all_evts.append((start, end, ev))
            except Exception:
                pass
    all_evts.sort(key=lambda x: x[0])

    # En-tête vert identique aux autres menus
    cn, sy = _current_cn_sy()
    _print_green_header(cn, sy)

    for week_idx in range(4):
        wk_mon = monday + datetime.timedelta(weeks=week_idx)
        wk_sun = wk_mon + datetime.timedelta(days=6)
        wk_fri = wk_mon + datetime.timedelta(days=4)

        week_evts = [(s, e, ev) for s, e, ev in all_evts
                     if wk_mon <= s.date() <= wk_sun]

        print(f"\n  {_W5_SEP}")
        print(_bold(f"  Détail de la semaine du {wk_mon.strftime('%d/%m/%Y')} au {wk_fri.strftime('%d/%m/%Y')}"))
        print(f"  {_W5_SEP}")

        ep = ef = fp = ff = dp = df = rp = rf = 0.0

        if not week_evts:
            print("    (aucun événement)")
        else:
            current_day = None
            seen_w: set = set()

            for start, end, ev in week_evts:
                slot_key = (ev.get("start_iso",""), ev.get("end_iso",""), ev.get("summary",""))
                if slot_key in seen_w:
                    continue
                seen_w.add(slot_key)
                # Séparateur de jour
                if start.date() != current_day:
                    current_day = start.date()
                    jour_long = _JOURS_LONG[current_day.weekday()]
                    print(_yellow(f"\n    -- {jour_long} {_fmt_date_court(current_day)}"))

                summ  = ev.get("summary", "")
                dur   = (end - start).total_seconds() / 3600
                trng  = f"{_B}{_RED}{start.strftime('%H:%M')}-{end.strftime('%H:%M')} ({format_hours_hm(dur)}){_R}"
                past  = end.date() < today

                parsed = parse_course_summary(summ)
                if parsed:
                    cl, fil, mod, nom = parsed
                    dedouble = is_dedouble(ev.get("summary", ""), ev.get("description", ""))
                    regroupe = (ev.get("start_iso",""), ev.get("end_iso",""),
                                fil, mod, nom) in reg_slots
                    flag = "Regroupé" if regroupe else ("Dédoublé" if dedouble else "")
                    lbl  = f"{cl} — {course_label_short(mod, nom)}"

                    eh, fh, dc, rc = _compute_contributions(dur, dedouble, regroupe)

                    if past:
                        ep += eh; fp += fh; dp += dc; rp += rc
                    else:
                        ef += eh; ff += fh; df += dc; rf += rc
                else:
                    label     = match_event_label(summ)
                    lbl       = normalize_display(label) if label else summ[:35]
                    flag      = ""
                    all_day   = dur >= 20.0   # événement toute la journée
                    if not all_day:
                        dur_label = _DURATION_OVERRIDES.get(label, dur) if label else dur
                        if past:
                            fp += dur_label
                        else:
                            ff += dur_label

                date_str = f"{_JOURS[start.weekday()]}. {_fmt_date_court(start.date())}"
                line = f"    {date_str}  {trng}  {lbl}"
                if flag:
                    line += f"  {flag}"
                print(_dim(line) if past else line)

        print(f"\n  {_W5_SEP}")
        print(_red(f"  Elèves    : {_fmt_eleve(ep, ef)}"))
        print(_yellow(f"  Formateur : {_fmt_fmt(fp, ff, dp+df, rp+rf)}"))
        print(f"  {_W5_SEP}")
        input("  Appuyez sur Entrée pour la semaine suivante...")


# ---------------------------------------------------------------------
# Menu 7 : Prochaines séquences  (v5.20)
# ---------------------------------------------------------------------

def run_menu_sequences():
    """Option 7 : tableau classe × cours × cette semaine × prochain cours."""
    today = datetime.datetime.now(TIMEZONE).date()

    # Semaine courante : lun–ven de la semaine calendaire (lun–dim) contenant today.
    # Si today est sam (5) ou dim (6), this_monday/friday pointent sur la semaine passée.
    days_since_monday = today.weekday()          # 0 = lun … 6 = dim
    this_monday = today - datetime.timedelta(days=days_since_monday)
    this_friday = this_monday + datetime.timedelta(days=4)
    next_monday = this_monday + datetime.timedelta(weeks=1)

    # Sources d'événements (même logique que option 6)
    if _last_state:
        sources = _last_state
    else:
        raw = load_state()
        sources = {c["name"]: raw.get(c["name"], {}) for c in MY_CALENDARS}
    if not any(sources.values()):
        print("  Aucune donnée — lancez d'abord une option Statistiques (1 à 3).")
        return

    # Collecte : (classe, course_key) → ensemble de dates de séances
    sessions: Dict = {}
    for evts in sources.values():
        for ev in evts.values():
            parsed = parse_course_summary(ev.get("summary", ""))
            if not parsed:
                continue
            cl, fil, mod, nom = parsed
            ck = f"{fil}|{mod}|{nom}"
            try:
                d = datetime.datetime.fromisoformat(ev["start_iso"]).date()
            except Exception:
                continue
            sessions.setdefault((cl, ck), set()).add(d)

    for key in sessions:
        sessions[key] = sorted(sessions[key])

    # Tri identique à l'option 4 : par classe (CLASS_ORDER) puis par cours
    pairs = sorted(sessions.keys(), key=lambda x: (class_sort_key(x[0]), x[1]))
    if not pairs:
        print("  Aucun cours trouvé.")
        return

    # En-tête vert
    cn, sy = _current_cn_sy()
    _print_green_header(cn, sy or _selected_sy)

    # Libellé de la semaine de référence
    if today.weekday() >= 5:
        week_label = (f"semaine passée  "
                      f"({this_monday.strftime('%d/%m')} – {this_friday.strftime('%d/%m/%Y')})")
    else:
        week_label = (f"semaine du {this_monday.strftime('%d/%m/%Y')}"
                      f" au {this_friday.strftime('%d/%m/%Y')}")

    SEP7  = "─" * 93
    CL_W  = 16
    CRS_W = 33
    TW_W  = 16
    NX_W  = 16

    def _fsd(d: datetime.date) -> str:
        """Formate une date en 'Lun. 14 avr.'"""
        return f"{_JOURS[d.weekday()]}. {_fmt_date_court(d)}"

    tw_range = (f"{this_monday.day} {_MOIS_COURT[this_monday.month-1].capitalize()}"
                f"-{this_friday.day} {_MOIS_COURT[this_friday.month-1].capitalize()}")

    print(f"\n  {SEP7}")
    print(_bold(f"  Prochaines séquences"))
    print(f"  {SEP7}")
    print(_bold(f"  {'CLASSE':<{CL_W}}  {'COURS':<{CRS_W}}  {'CETTE SEMAINE':<{TW_W}}  {'PROCHAIN COURS':<{NX_W}}"))
    print(f"  {'':<{CL_W}}  {'':<{CRS_W}}  {_yellow(tw_range)}")
    print(f"  {SEP7}")

    toggle = False   # alterne à chaque paire classe+cours
    for cl, ck in pairs:
        fil, mod, nom = ck.split("|", 2)
        lbl = course_label_short(mod, nom)
        dates = sessions[(cl, ck)]

        # Séances cette semaine (lun–ven de la semaine courante)
        tw_dates = [d for d in dates if this_monday <= d <= this_friday]

        # Séances à partir du prochain lundi
        fut_dates = [d for d in dates if d >= next_monday]

        # Toutes les séances de la semaine du premier cours futur
        if fut_dates:
            first = fut_dates[0]
            w_mon = first - datetime.timedelta(days=first.weekday())
            w_fri = w_mon + datetime.timedelta(days=4)
            nx_dates = [d for d in fut_dates if w_mon <= d <= w_fri]
        else:
            nx_dates = []

        tw_strs = [_fsd(d) for d in tw_dates] if tw_dates else ["-"]
        nx_strs = [_fsd(d) for d in nx_dates] if nx_dates else ["-"]

        n = max(len(tw_strs), len(nx_strs))

        toggle = not toggle
        colorize = _red if toggle else (lambda s: s)

        lbl_trunc = lbl if len(lbl) <= CRS_W else lbl[:CRS_W - 1] + "…"
        for i in range(n):
            cl_disp  = cl        if i == 0 else ""
            lbl_disp = lbl_trunc if i == 0 else ""
            tw_str   = tw_strs[i] if i < len(tw_strs) else ""
            nx_str   = nx_strs[i] if i < len(nx_strs) else ""
            print(colorize(f"  {cl_disp:<{CL_W}}  {lbl_disp:<{CRS_W}}  {tw_str:<{TW_W}}  {nx_str:<{NX_W}}"))

    print(f"  {SEP7}")
    input("\n  Appuyez sur Entrée pour revenir au menu principal...")


# ---------------------------------------------------------------------
# Menu principal
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Menu 6 : Progression vers les objectifs
# ---------------------------------------------------------------------

def _obj_raw_e(past_h: float, cible: float) -> str:
    """Chaîne ELEVE brute sans ANSI."""
    p = int(round(past_h))
    c = int(round(cible))
    if c > 0:
        return f"{p}h/{c}h ({past_h / cible * 100:.0f}%)"
    return f"{p}h"


def _obj_raw_f(past_h: float, cible: float) -> str:
    """Chaîne FORMATEUR brute sans ANSI."""
    if cible > 0:
        return f"{format_hours_hm(past_h)}/{format_hours_hm(cible)} ({past_h / cible * 100:.0f}%)"
    return format_hours_hm(past_h)


def _obj_col(raw: str, width: int, over: bool) -> str:
    """Padde à width chars (sur la chaîne brute), puis colore si over."""
    padded = f"{raw:<{width}}"
    return _red(padded) if over else padded


def _obj_row(ep, ef, ce, fp, ff, cf, **_) -> str:
    """Ligne de progression : [aujourd'hui]  ──→  [fin d'année]"""
    e_now_r = _obj_raw_e(ep,      ce);  e_now_o = ce > 0 and ep      / ce >= 1.0
    f_now_r = _obj_raw_f(fp,      cf);  f_now_o = cf > 0 and fp      / cf >= 1.0
    e_end_r = _obj_raw_e(ep + ef, ce);  e_end_o = ce > 0 and (ep+ef) / ce >= 1.0
    f_end_r = _obj_raw_f(fp + ff, cf);  f_end_o = cf > 0 and (fp+ff) / cf >= 1.0

    now = f"E: {_obj_col(e_now_r, _OBJ_E_W, e_now_o)}  F: {_obj_col(f_now_r, _OBJ_F_W, f_now_o)}"
    end = f"E: {_obj_col(e_end_r, _OBJ_E_W, e_end_o)}  F: {_obj_col(f_end_r, _OBJ_F_W, f_end_o)}"
    return f"  {now}  ──→  {end}"


def load_objectifs() -> dict:
    try:
        with open(OBJECTIFS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def generate_objectifs_template():
    """Génère (ou complète) objectifs.json à partir de _last_analysis."""
    existing = load_objectifs()
    for cn, by_year in _last_analysis.items():
        if cn not in existing:
            existing[cn] = {}
        for sy, bk in by_year.items():
            if sy not in existing[cn]:
                existing[cn][sy] = {}
            bcc = bk["course_hours"].get("by_class_and_course", {})
            for classe, courses in bcc.items():
                if classe not in existing[cn][sy]:
                    existing[cn][sy][classe] = {}
                for ck in courses:
                    if ck not in existing[cn][sy][classe]:
                        existing[cn][sy][classe][ck] = {"eleve": 0, "fmt": 0}
    with open(OBJECTIFS_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


def _pct_str(actual: float, cible: float) -> str:
    """Retourne '60%|85%' ou '--' si cible=0."""
    if cible <= 0:
        return "--"
    p_fait = actual / cible * 100
    return f"{p_fait:.0f}%"


def _pct2_str(past: float, fut: float, cible: float) -> str:
    """Retourne 'XX%|YY%' (fait | projeté fin d'année), ou '--' si cible=0."""
    if cible <= 0:
        return "--"
    p_fait   = past / cible * 100
    p_projet = (past + fut) / cible * 100
    s = f"{p_fait:.0f}%|{p_projet:.0f}%"
    if p_fait >= 100 or p_projet >= 100:
        return _red(s)   # cyan
    return s


def run_menu_objectifs():
    objectifs = load_objectifs()
    if not _last_analysis:
        print("  Aucune analyse disponible. Lancez d'abord une option 1-3.")
        return

    cn = next(iter(_last_analysis), "")
    sy = _selected_sy if _selected_sy else (sorted(_last_analysis.get(cn, {}).keys())[-1] if cn else "")
    if not cn or not sy:
        return

    bk  = _last_analysis[cn][sy]
    bcc = bk["course_hours"].get("by_class_and_course", {})
    obj_cn = objectifs.get(cn, {}).get(sy, {})

    has_any_target = any(
        (v.get("eleve", 0) > 0 or v.get("fmt", 0) > 0)
        for classe_d in obj_cn.values() for v in classe_d.values()
    )

    # En-tête vert
    _print_green_header(cn, sy)

    if not obj_cn or not has_any_target:
        generate_objectifs_template()
        print(f"\n  Aucun objectif défini.")
        print(f"  Un fichier modèle '{OBJECTIFS_FILE}' a été créé.")
        print(f"  Remplissez les valeurs 'eleve' et 'fmt' puis relancez.")
        return

    for cycle_label, classes in CYCLE_GROUPS:
        cycle_classes = [c for c in classes if c in bcc or c in obj_cn]
        if not cycle_classes:
            continue

        print(f"\n  {_bold(f'── {cycle_label} ──')}")

        for classe in cycle_classes:
            courses_actual = bcc.get(classe, {})
            courses_obj    = obj_cn.get(classe, {})

            all_keys = sorted(set(courses_actual) | set(courses_obj), key=lambda k: k)
            if not all_keys:
                continue

            tot_v = [0.0] * 8
            lines_data = []
            for ck in all_keys:
                v = courses_actual.get(ck, [0.0]*8)
                for i in range(min(len(v), 8)):
                    tot_v[i] += v[i]
                obj = courses_obj.get(ck, {})
                fil, mod, nom = ck.split("|", 2)
                lbl = _trunc_lbl(course_label_short(mod, nom))
                e_str, f_str = _compact_parts(v, obj)
                ep, ef, fp, ff = v[0], v[1], v[2], v[3]
                ce = float(obj.get("eleve", 0)) if obj else 0
                cf = float(obj.get("fmt",   0)) if obj else 0
                pcts = []
                if ce > 0: pcts += [ep / ce * 100, (ep + ef) / ce * 100]
                if cf > 0: pcts += [fp / cf * 100, (fp + ff) / cf * 100]
                alerte = bool(pcts) and max(pcts) > 105
                lines_data.append((f"{lbl:<{_PROG_LBL_W}}", e_str, f_str, False, alerte))

            if len(all_keys) > 1:
                e_str, f_str = _compact_parts(tot_v, {})
                lines_data.append((f"{'TOTAL':<{_PROG_LBL_W}}", e_str, f_str, True, False))

            print(_bold(f"    {classe}"))
            for lbl_f, e_str, f_str, is_total, alerte in lines_data:
                e_padded = f"{e_str:<{_PROG_ELEVE_W}}"
                alert_str = f"  {_B}{_RGE}ALERTE (>= 105%){_R}" if alerte else ""
                if is_total:
                    print(_row_yellow(lbl_f, e_padded, f_str) + alert_str)
                else:
                    print(_row_dim(lbl_f, e_padded, f_str) + alert_str)


def run_change_sy():
    """Permet à l'utilisateur de choisir l'année scolaire active."""
    global _selected_sy

    # Collecter toutes les années depuis _last_analysis (cours)
    available = set()
    for by_year in _last_analysis.values():
        available.update(by_year.keys())

    # Compléter avec les années des événements dans _last_state (RTT, CONGÉS, etc.)
    for stored in _last_state.values():
        for ev in stored.values():
            s = ev.get("start_iso") or ev.get("start_dt", "")
            if not s or len(s) < 10:
                continue
            try:
                d = datetime.date.fromisoformat(s[:10])
                available.add(get_school_year_label(d))
            except ValueError:
                pass

    if not available:
        print("  Aucune donnée disponible. Lancez d'abord une option 1-3.")
        return

    years = sorted(available)
    print(_green(f"\n  {SEP}"))
    print(_green("  CHANGER D'ANNÉE SCOLAIRE"))
    print(_green(f"  {SEP}"))
    print()
    for i, y in enumerate(years, 1):
        marker = "   ►" if y == _selected_sy else "    "
        print(f"{marker} {i} : {y}")
    print()
    print("   ► 0.  Retour au menu principal")
    print()

    try:
        choice = input("  Votre choix : ").strip()
        if not choice or choice == "0":
            return
        idx = int(choice) - 1
        if 0 <= idx < len(years):
            _selected_sy = years[idx]
            print(f"  Année scolaire sélectionnée : {_bold(_selected_sy)}")
        else:
            print("  Choix invalide.")
    except ValueError:
        print("  Choix invalide.")


# ---------------------------------------------------------------------
# Menu 8 : Analyse hebdomadaire de l'année scolaire  (v6.0)
# ---------------------------------------------------------------------

_REF_H = 20.0   # référence hebdomadaire en heures formateur

def run_menu_annual_analysis():
    """Option 8 : tableau hebdomadaire des heures formateur vs 20h de référence."""
    if not _last_state:
        print("  Aucune donnée disponible.")
        return
    if not _selected_sy:
        print("  Aucune année scolaire sélectionnée.")
        return

    sy_start, sy_end = school_year_bounds(_selected_sy)

    # --- Collecte des heures par jour (somme brute des durées de cours) ---
    day_hours: Dict[datetime.date, float] = {}
    seen_slots: set = set()
    for evts in _last_state.values():
        for ev in evts.values():
            if not parse_course_summary(ev.get("summary", "")):
                continue
            s_raw = ev.get("start_iso", "")
            e_raw = ev.get("end_iso", s_raw)
            slot  = (s_raw, e_raw, ev.get("summary", ""))
            if slot in seen_slots:
                continue
            seen_slots.add(slot)
            try:
                start   = datetime.datetime.fromisoformat(s_raw)
                end     = datetime.datetime.fromisoformat(e_raw)
                dur_raw = (end - start).total_seconds() / 3600
                dur, _  = eleve_hours(dur_raw)   # arrondi entier (≥50 min → heure sup.)
                d       = start.date()
                day_hours[d] = day_hours.get(d, 0.0) + dur
            except Exception:
                continue

    # --- En-tête ---
    cn, sy = _current_cn_sy()
    _print_green_header(cn, sy or _selected_sy)

    _MENTION_W = 11   # max len("très faible")
    _J8_W      = 18   # max len("x j à 8h de cours")
    SEP_A = "─" * 70
    print(f"\n  {SEP_A}")
    print(_bold(f"  Analyse de l'année {_selected_sy}  —  référence : {int(_REF_H)}h / semaine"))
    print(f"  {SEP_A}")
    # "Mention" supprimé ; "J >= 8H" → "Journées pleines"
    print(_bold(f"  {'SEMAINE':<20}  {'HEURES':>6}  {'%':>4}  {'':<{_MENTION_W}}  Journées pleines"))
    print(f"  {SEP_A}")

    # --- Itération semaine par semaine ---
    first_monday = sy_start - datetime.timedelta(days=sy_start.weekday())
    toggle      = False
    current     = first_monday
    prev_friday = None
    line_count  = 0

    while current <= sy_end:
        friday = current + datetime.timedelta(days=4)
        week_h = sum(day_hours.get(current + datetime.timedelta(days=i), 0.0)
                     for i in range(5))
        pct    = week_h / _REF_H * 100
        toggle = not toggle

        # Saut de ligne si le lundi courant est dans un mois différent du vendredi précédent
        if prev_friday is not None and current.month != prev_friday.month:
            print()
            line_count += 1
            if line_count >= 20:
                input("  — Appuyez sur Entrée pour continuer —")
                line_count = 0

        # Plage de dates (pas de point supplémentaire : _MOIS_COURT contient déjà le point)
        date_str = (f"{current.day} {_MOIS_COURT[current.month - 1].capitalize()}"
                    f"-{friday.day} {_MOIS_COURT[friday.month - 1].capitalize()}")

        # Heures
        h_str = format_hours_hm(week_h) if week_h > 0 else "    -"

        # Pourcentage : sans parenthèses, droite sur 3 chiffres
        pct_str = f"{pct:>3.0f}%" if week_h > 0 else "   -"

        # Alternance blanc/cyan
        colorize = _red if toggle else (lambda s: s)

        # Mention
        if pct >= 131:
            alert_lbl = "TRES ELEVE"
            alert_fmt = lambda s: f"{_B}{_RGE}{s}{_R}"
        elif pct >= 116:
            alert_lbl = "élevé"
            alert_fmt = lambda s: f"{_B}{_Y}{s}{_R}"
        elif week_h > 0 and pct <= 50:
            alert_lbl = "très faible"
            alert_fmt = lambda s: f"{_B}{_GRN}{s}{_R}"
        elif week_h > 0 and pct <= 80:
            alert_lbl = "faible"
            alert_fmt = lambda s: s
        else:
            alert_lbl = ""
            alert_fmt = lambda s: s
        alert_col = "  " + alert_fmt(f"{alert_lbl:<{_MENTION_W}}")

        # Journées pleines (≥ 8h)
        days_8h = sum(
            1 for i in range(5)
            if day_hours.get(current + datetime.timedelta(days=i), 0.0) >= 8
        )
        if days_8h >= 2:
            j8_lbl = f"{days_8h} j à 8h de cours"
            j8_fmt = lambda s: f"{_B}{_RGE}{s}{_R}"
        elif days_8h == 1:
            j8_lbl = f"{days_8h} j à 8h de cours"
            j8_fmt = lambda s: f"{_B}{_Y}{s}{_R}"
        else:
            j8_lbl = ""
            j8_fmt = lambda s: s
        j8_col = "  " + j8_fmt(f"{j8_lbl:<{_J8_W}}")

        base = f"  {date_str:<20}  {h_str:>6}  {pct_str}"
        print(colorize(base) + alert_col + j8_col)

        prev_friday = friday
        line_count += 1
        if line_count >= 20:
            input("  — Appuyez sur Entrée pour continuer —")
            line_count = 0

        current += datetime.timedelta(weeks=1)

    print(f"  {SEP_A}")
    input("\n  Appuyez sur Entrée pour revenir au menu principal...")


def print_main_menu(cal: str, sy: str):
    print(_green(f"\n{SEP}"))
    print(_green(f"  AGENT CALENDRIER MFR  —  {cal}"))
    print(_green(f"  Année scolaire : {sy}"))
    print(_green(SEP))
    print("   ► 1 : Statistiques Par CLASSE et par COURS")
    print("   ► 2 : Statistiques HEURES par CLASSE")
    print("   ► 3 : Statistiques Événements Hors COURS")
    print("   ► 4 : Détail par CLASSE et par COURS")
    print("   ► 5 : Progression vers les objectifs")
    print("   ► 6 : Détail de la semaine en cours et des 3 suivantes")
    print("   ► 7 : Prochaines séquences")
    print("   ► 8 : Analyse de l'année en cours")
    print("   ► 9 : Changer d'année scolaire")
    print()
    print("   ► 0 : Quitter")
    print("-" * 64)

def main():
    global _selected_sy
    create_lock()
    state = load_state()
    _selected_sy = get_school_year_label(datetime.date.today())

    print("  Chargement des données...", end="", flush=True)
    state = _load_data(state)
    print(" OK")

    while True:
        cal_names = ", ".join(c.get("name", "?") for c in MY_CALENDARS)
        print_main_menu(cal_names, _selected_sy)
        choice = input("  Votre choix : ").strip()

        if choice == "0":
            print("  Au revoir.")
            break
        elif choice in ("1", "2", "3"):
            state = _load_and_show(state, int(choice))
        elif choice == "4":
            run_option_5()
        elif choice == "5":
            run_menu_objectifs()
        elif choice == "6":
            run_menu_5weeks()
        elif choice == "7":
            run_menu_sequences()
        elif choice == "8":
            run_menu_annual_analysis()
        elif choice == "9":
            run_change_sy()
        else:
            print("  Option invalide, réessayez.")

# ---------------------------------------------------------------------
if __name__ == "__main__":
    main()
