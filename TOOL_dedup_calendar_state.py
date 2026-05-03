"""Nettoie calendar_state.json en supprimant les événements en double (même start_iso + end_iso)."""
import json, os

STATE_FILE = "calendar_state.json"
BACKUP_FILE = "calendar_state.json.bak"

with open(STATE_FILE, "r", encoding="utf-8") as f:
    state = json.load(f)

# Sauvegarde
with open(BACKUP_FILE, "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)
print(f"Sauvegarde : {BACKUP_FILE}")

total_before = 0
total_after  = 0

for cal_name, events in state.items():
    seen_slots = {}  # (start_iso, end_iso) -> clé conservée
    to_delete  = []

    for key, ev in events.items():
        slot = (ev.get("start_iso") or ev.get("start_dt", ""),
                ev.get("end_iso")   or ev.get("end_dt",   ""))
        if slot in seen_slots:
            # Préférer la clé imfr_ (données plus riches) sinon garder la première
            existing_key = seen_slots[slot]
            if key.startswith("imfr_"):
                # Remplacer l'ancienne clé par celle-ci
                to_delete.append(existing_key)
                seen_slots[slot] = key
            else:
                to_delete.append(key)
        else:
            seen_slots[slot] = key

    before = len(events)
    for k in to_delete:
        del events[k]
    after = len(events)

    print(f"  {cal_name} : {before} -> {after} evenements ({before - after} doublons supprimes)")
    total_before += before
    total_after  += after

print(f"\nTotal : {total_before} -> {total_after} evenements ({total_before - total_after} doublons supprimes)")

with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)

size = os.path.getsize(STATE_FILE)
print(f"Fichier sauvegardé : {STATE_FILE} ({size // 1024} KB)")
