# Idées d'améliorations (à faire plus tard)

## Importantes
(aucune pour l'instant)

## Confort
3. **Le temps qu'il fait maintenant** en haut de Prévisions (comme l'en-tête Météus) : température, humidité, vent moyen et rafale mesurés à la station Météo-France la plus proche.

## Plus tard
4. **Alerte pluie sur le téléphone** (« pluie à la maison dans 30 min »), même appli fermée : demande un système de notifications.
5. **Pluviomètre connecté perso** (Ecowitt ou Netatmo, modèle Wi-Fi) : ajouter « Ma station » en tête des Relevés. Vérifier le modèle avant achat.
6. **Relevés pour la maison de chacun** si l'appli est partagée avec des personnes qui habitent loin de Verneuil-le-Château.
7. **Mettre à jour les outils GitHub du robot** quand GitHub retirera les versions actuelles (avertissement de version dans les journaux).

## Fait
- Bandeau Vigilance Météo-France (orange/rouge, Indre-et-Loire) en haut de Prévisions (23/11/2026).
- Alerte e-mail si l'appel du robot échoue : cron-job.org prévient après 3 échecs de suite, et quand ça repart (23/11/2026).

## Écarté
- Impacts de foudre : données Météo-France payantes, sources gratuites non autorisées pour cet usage.
- Violet du radar plus tôt : on garde l'échelle actuelle (violet dès 40 mm/h).
- Vent exact dans la liste à 10 jours : l'arrondi à 5 km/h convient (le détail par 2 h reste exact).
