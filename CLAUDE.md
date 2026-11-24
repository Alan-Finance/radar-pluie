# Radar Pluie — mémo pour Claude

Appli météo perso d'Alan (en français), publiée sur **https://alandoreau.github.io/radar-pluie/**.
Dépôt GitHub : **AlanDoreau/radar-pluie** (ancien nom Alan-Finance, renommé le 22/11/2026).
L'utilisateur n'est pas développeur : réponses courtes, en français, adaptées au téléphone ; il préfère que Claude fasse les manipulations.

## Architecture
- `index.html` : toute l'appli (HTML + CSS + JS, carte **MapLibre GL 4.7.1** via unpkg depuis le 24/11/2026 ; avant : Leaflet, dernier commit Leaflet = bdf4c04). Trois onglets, dans cet ordre (choix validé) : **Relevés** (icône emoji 🌡️ + 2 petites gouttes 💧 en haut à droite, choix validé ; onglet d’ouverture), **Prévisions** 🌦️, **Radar** (icône SVG : mini-carte avec une perturbation).
- `scripts/update.py` : robot (Python) lancé par `.github/workflows/radar.yml` ; fabrique `data/frames.json` + images PNG radar/prévision ; appelle `scripts/releves.py`.
- `scripts/releves.py` : relevés pluviomètres Météo-France (DPPaquetObs v2, horaire, 24 h d'historique côté API) + **station virtuelle radar** au-dessus du lieu (cumul des lames d'eau 5 min) → `data/releves.json`. Pluviomètres quotidiens data.gouv désactivés (`departements: []`). Par heure et par station : rr, t, et si mesurés ff/fx (km/h), u, td, dd (`VERSION` dans releves.py : l'augmenter relit les 24 h une fois).
- Station virtuelle du lieu (Verneuil-le-Château) : pluie = radar ; température, humidité, rosée, vent, rafales = modèle AROME via Open-Meteo (`meteofrance_seamless`, current + 24 h passées), côté navigateur, affiché comme « estimé ». Les stations les plus proches (L'Île-Bouchard, Saint-Épain) ne mesurent ni vent ni humidité.
- Onglet Relevés (ordre validé, comme Météus) : « Maintenant » (cartes par station, défilement horizontal), « La nuit dernière » (22h–6h : pluie, rafale max, mini/maxi), cumuls, graphiques.
- `config.json` : lieu des relevés (Verneuil-le-Château 47.0394, 0.4583, depuis le 23/11/2026 ; avant Marcilly-sur-Vienne), rayon stations 50 km. Changer de lieu garde l’historique des stations ; la station virtuelle radar repart de zéro.
- L'état (historique radar, relevés) est relu à chaque passage depuis le site publié (`PAGES_URL` = sortie de `actions/configure-pages`). Rien n'est commité par le robot.
- Publication : GitHub Pages en mode « GitHub Actions » (upload-pages-artifact + deploy-pages, 2e essai si échec).

## Données
- Radar : Météo-France DPRadar (mosaïque LAME_D_EAU 500 m, HDF5) + DPPaquetRadar ; 2 h de passé (PAST_HOURS, 1 h 30 avant le 24/11/2026), pas 10 min ; lissage gaussien ; palette 9 classes (violet ≥ 40 mm/h, choix validé).
- Prévision radar : AROME-PI (WCS GRIB2, TOTAL_PRECIPITATION_RATE), runs complets seulement, +3 h, pas 15 min.
- Prévisions 10 jours (côté navigateur) : Open-Meteo `meteofrance_seamless` (J1–J4) sinon `best_match` (ECMWF) ; fourchette = ensemble ECMWF (quartiles) affichée seulement dans le détail ; détail par tranches de 2 h ; vent arrondi à 5 km/h et pluie arrondie au mm (« <1mm » sous 0,5 mm) dans la liste, décimales gardées dans le détail du jour (choix validés).
- Vigilance : `scripts/vigilance.py` (API Données Publiques Vigilance, `cartevigilance/encours`) → `data/vigilance.json` pour le département `departement_vigilance` de config.json (37) ; bandeau en haut de Prévisions seulement en orange/rouge (jaune volontairement non affiché, choix validé), lien vers vigilance.meteofrance.fr.
- Clé Météo-France : secret GitHub `METEOFRANCE_KEY` (en-tête `apikey`), abonnements : DPRadar, DPPaquetRadar, AROME, AROME-PI, DPPaquetObs v2, Données Publiques Vigilance. La clé (JWT) ne couvre que les API abonnées au moment où elle est générée : après un nouvel abonnement, régénérer la clé et mettre à jour le secret. Ne jamais demander ni afficher la clé.

## Exécution
- Lancé toutes les 10 min par **cron-job.org** (tâche « Radar Pluie », POST sur l'API `workflow_dispatch`, clé GitHub fine-grained `radar-pluie-cron`, Actions lecture/écriture). Pas de `schedule` GitHub (retiré volontairement). Notification e-mail cron-job.org après 3 échecs d'appel de suite + au retour (ne voit pas les échecs internes du robot).
- Onglet Radar (24/11/2026, façon Pleinchamp) : carte vectorielle pour la fluidité (demande d'Alan) ; fond par défaut « Détaillé » = OpenFreeMap style liberty (vectoriel, gratuit sans clé ; bascule forcée une fois via `radar-pluie-fond-v2`), les autres fonds sont des tuiles raster ; zoom MapLibre = zoom Leaflet − 1 (helpers `Z`, `zoomL`, `setView`), max 15 (= 16 Leaflet) ; radar = source `image` unique (`updateImage`, une image à la fois) placée sous les noms de lieux ; appui long maison (touchstart 600 ms) ; secours : si OpenFreeMap ne répond pas (pas de tuile en 10 s ou 3 erreurs), bascule sur « Relief » sans l'enregistrer (réessai à la prochaine ouverture, choix d'Alan) ; vue « chez moi » (`vueMaison`, RECUL_KM = 50 km de chaque côté de la maison) remise à chaque arrivée sur l'onglet Radar, sauf quand la vue vient d'être choisie (`garderVue`), demande d'Alan ; fond « Plan IGN » en plus ; panneau du temps : lecture/pause + ↻ (retour à maintenant + recharge), date + heure, barre verte épaisse, carrés de pluie au point gardés au-dessus (demande d'Alan), sans phrase en dessous (les couleurs suffisent, choix d'Alan), trait rouge = maintenant, partie prévision hachurée ; animation 600 ms/image.
- Côté appli : maison 🏠, lieu, favoris, stations choisies, fond de carte et caches sont dans le `localStorage` du téléphone.

## Échéances
Voir README (clé Météo-France ~23/11/2027, clé GitHub 21/11/2027, abonnements 18/11/2028).

## À faire
Voir `AMELIORATIONS.md` (liste validée avec Alan, idées écartées notées).

## Méthode
- Tester l'appli en vue mobile (375 px) après chaque changement ; vérifier `node --check` sur le script extrait.
- Messages de commit en français.
