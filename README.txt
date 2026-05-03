=== Agent Calendrier - Guide complet ===

1️⃣ Configurer le mot de passe d’application Outlook :
   - Se connecter à https://account.microsoft.com
   - Sécurité → Plus d’options de sécurité → Mots de passe d'application
   - Créer un mot de passe spécifique
   - Définir la variable d'environnement Windows :
       setx AGENT_EMAIL_PASSWORD "TON_MOT_DE_PASSE_APP"

2️⃣ Remplir config.json :
   - ICS_URL : lien de ton calendrier .ics
   - EMAIL_RECIPIENT : destinataire des mails
   - EMAIL_SENDER : ton compte Hotmail / Outlook
   - CHECK_INTERVAL : 60 secondes pour test

3️⃣ Lancer le script :
   - CMD → cd C:\Users\acher\AgentCalendrierMFR
   - python.exe calendar_agent_console.py
   - Vérifier que les notifications Windows et mails arrivent

4️⃣ Notes :
   - Webhook Teams/Slack optionnel
   - En test, interval 60 secondes, à remettre à 300s pour production
   - pythonw.exe peut être utilisé pour lancement silencieux
