# Radar Pluie

**Adresse de l'appli : https://alandoreau.github.io/radar-pluie/**

Appli web de radar de pluie en temps réel, avec les données de Météo-France :

- **Radar** : mosaïque « lame d'eau » 500 m de Météo-France, une image toutes les 10 minutes sur les 2 dernières heures.
- **Prévision** : modèle AROME-PI (prévision immédiate), une image par quart d'heure jusqu'à +3 h.
- Ta position GPS, tes points nommés, et une barre « pluie ici » pour savoir quand la pluie arrive.

## Comment ça marche

Un robot GitHub Actions (`.github/workflows/radar.yml`) tourne toutes les 10 minutes :
il télécharge les données Météo-France, les transforme en images lissées (`scripts/update.py`)
et publie le tout sur GitHub Pages avec l'appli (`index.html`).

La clé Météo-France est rangée dans le secret `METEOFRANCE_KEY` du dépôt : elle n'apparaît jamais dans le code.

## Réglages

- Vue de départ et points fixes : bloc « RÉGLAGES PERSO » en haut du script de `index.html`.
- Couleurs, seuils, lissage, durée du passé et de la prévision : haut de `scripts/update.py`.

Données : Météo-France, Licence Ouverte 2.0.

## Entretien (à noter dans un agenda)

| Quand | Quoi | Où |
|---|---|---|
| **Vers le 20 novembre 2027** | La clé Météo-France expire : en générer une nouvelle (Clé API, durée 31536000) et la coller dans le secret `METEOFRANCE_KEY` | portail-api.meteofrance.fr → Mes API, puis GitHub → Settings → Secrets and variables → Actions |
| **Avant le 21 novembre 2027** | La clé GitHub `radar-pluie-cron` expire : en recréer une (Actions : lecture et écriture, dépôt radar-pluie) et la recoller après `Bearer ` dans l'en-tête Authorization de la tâche | github.com/settings/personal-access-tokens, puis console.cron-job.org |
| **Avant le 18 novembre 2028** | Les abonnements aux API Météo-France arrivent à échéance : cliquer sur « Renouveler » | portail-api.meteofrance.fr → Mes API |

Si l'appli affiche « ⚠️ Données pas mises à jour », regarder d'abord l'historique de la tâche sur cron-job.org,
puis l'onglet Actions du dépôt GitHub.
