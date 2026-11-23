# Idées d'améliorations (à faire plus tard)

## Plus tard
1. **Alerte pluie sur le téléphone** (« pluie à la maison dans 30 min »), même appli fermée : demande un système de notifications.
2. **Pluviomètre connecté perso** (Ecowitt ou Netatmo, modèle Wi-Fi) : ajouter « Ma station » en tête des Relevés. Vérifier le modèle avant achat.
3. **Relevés pour la maison de chacun** si l'appli est partagée avec des personnes qui habitent loin de Verneuil-le-Château.
4. **Mettre à jour les outils GitHub du robot** quand GitHub retirera les versions actuelles (avertissement de version dans les journaux).

## Fait (23/11/2026)
- Bandeau Vigilance Météo-France (orange/rouge, Indre-et-Loire) en haut de Prévisions.
- Alerte e-mail si l'appel du robot échoue : cron-job.org prévient après 3 échecs de suite, et quand ça repart.
- Pluie arrondie au mm dans la liste à 10 jours (décimales gardées dans le détail du jour).
- Relevés et lieu par défaut : Verneuil-le-Château au lieu de Marcilly-sur-Vienne.
- « Maintenant » en tête des Relevés (comme Météus) : une carte par station (température, rosée, pluie de la dernière heure, humidité, vent moyen, rafale, direction).
- « La nuit dernière » plus clair, avec la rafale la plus forte, placée juste après « Maintenant ».

## Écarté
- Impacts de foudre : données Météo-France payantes, sources gratuites non autorisées pour cet usage.
- Vigilance jaune dans le bandeau : seulement orange et rouge.
- Violet du radar plus tôt : on garde l'échelle actuelle (violet dès 40 mm/h).
- Vent exact dans la liste à 10 jours : l'arrondi à 5 km/h convient (le détail par 2 h reste exact).
