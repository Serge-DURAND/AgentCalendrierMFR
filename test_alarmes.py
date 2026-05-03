from icalendar import Calendar
import requests
import sys

def check_alarms_in_ics(url: str, max_events: int = 3) -> None:
    try:
        # Récupérer le fichier ICS
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # Parser le calendrier
        cal = Calendar.from_ical(response.text)
        events_with_alarms = 0

        # Parcourir les événements
        for i, component in enumerate(cal.walk("VEVENT")):
            if i >= max_events:
                break  # On ne vérifie que les 3 premiers

            alarms = list(component.walk("VALARM"))
            if alarms:
                events_with_alarms += 1
                print(f"Événement {i+1} : {component.get('SUMMARY')} → Rappel trouvé : {alarms[0].get('TRIGGER')}")

        # Résultat final
        if events_with_alarms > 0:
            print(f"\n✅ Oui, des rappels sont présents ({events_with_alarms}/{max_events} événements vérifiés).")
        else:
            print(f"\n❌ Non, aucun rappel trouvé dans les {max_events} premiers événements.")

    except Exception as e:
        print(f"⚠️ Erreur lors de la vérification : {e}")
        sys.exit(1)

# --- EXECUTION ---
if __name__ == "__main__":
    # Remplace cette URL par celle de ton calendrier ICS
    CALENDAR_URL = "https://uzes.imfr.fr/V2/iplanning/feed/ical/?u=qkuOqUQlTnLuUbCI5SKAe1F1IxUDz3ZN"  # Ex: "https://exemple.com/calendar.ics"

    print(f"Vérification des rappels dans le calendrier : {CALENDAR_URL}")
    check_alarms_in_ics(CALENDAR_URL)
