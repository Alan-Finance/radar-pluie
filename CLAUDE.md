# Radar Pluie — mémo pour Claude

Appli météo perso d'Alan (en français), publiée sur **https://alandoreau.github.io/radar-pluie/**.
Dépôt GitHub : **AlanDoreau/radar-pluie** (ancien nom Alan-Finance, renommé le 22/11/2026).
L'utilisateur n'est pas développeur : réponses courtes, en français, adaptées au téléphone ; il préfère que Claude fasse les manipulations.

## Architecture
- `index.html` : toute l'appli (HTML + CSS + JS, Leaflet via unpkg). Trois onglets : **Prévisions**, **Radar**, **Relevés**.
- `scripts/update.py` : robot (Python) lancé par `.github/workflows/radar.yml` ; fabrique `data/frames.json` + images PNG radar/prévision ; appelle `scripts/releves.py`.
- `scripts/releves.py` : relevés pluviomètres Météo-France (DPPaquetObs v2, horaire, 24 h d'historique côté API) + **station virtuelle radar** au-dessus du lieu (cumul des lames d'eau 5 min) → `data/releves.json`. Pluviomètres quotidiens data.gouv désactivés (`departements: []`).
- `config.json` : lieu des relevés (Marcilly-sur-Vienne 47.0435, 0.5393), rayon stations 50 km.
- L'état (historique radar, relevés) est relu à chaque passage depuis le site publié (`PAGES_URL` = sortie de `actions/configure-pages`). Rien n'est commité par le robot.
- Publication : GitHub Pages en mode « GitHub Actions » (upload-pages-artifact + deploy-pages, 2e essai si échec).

## Données
- Radar : Météo-France DPRadar (mosaïque LAME_D_EAU 500 m, HDF5) + DPPaquetRadar ; 1 h 30 de passé (PAST_HOURS), pas 10 min ; lissage gaussien ; palette 9 classes (violet ≥ 40 mm/h, choix validé).
- Prévision radar : AROME-PI (WCS GRIB2, TOTAL_PRECIPITATION_RATE), runs complets seulement, +3 h, pas 15 min.
- Prévisions 10 jours (côté navigateur) : Open-Meteo `meteofrance_seamless` (J1–J4) sinon `best_match` (ECMWF) ; fourchette = ensemble ECMWF (quartiles) affichée seulement dans le détail ; détail par tranches de 2 h ; vent arrondi à 5 km/h dans la liste (choix validé).
- Clé Météo-France : secret GitHub `METEOFRANCE_KEY` (en-tête `apikey`), abonnements : DPRadar, DPPaquetRadar, AROME, AROME-PI, DPPaquetObs v2. Ne jamais demander ni afficher la clé.

## Exécution
- Lancé toutes les 10 min par **cron-job.org** (tâche « Radar Pluie », POST sur l'API `workflow_dispatch`, clé GitHub fine-grained `radar-pluie-cron`, Actions lecture/écriture). Pas de `schedule` GitHub (retiré volontairement).
- Côté appli : maison 🏠, lieu, favoris, stations choisies, fond de carte et caches sont dans le `localStorage` du téléphone.

## Échéances
Voir README (clé Météo-France ~20/11/2027, clé GitHub 21/11/2027, abonnements 18/11/2028).

## À faire
Voir `AMELIORATIONS.md` (liste validée avec Alan, idées écartées notées).

## Méthode
- Tester l'appli en vue mobile (375 px) après chaque changement ; vérifier `node --check` sur le script extrait.
- Messages de commit en français.
