# Sieva pour Home Assistant

Intégration Home Assistant qui récupère la consommation d'eau depuis l'espace client
[Sieva](https://sieva.fr/) (Val d'Azergues), https://ael.sieva.fr.

- Configuration 100 % via l'interface (pas de YAML)
- Aucune dépendance Python externe (aiohttp fourni par Home Assistant)
- Compatible **Home Assistant 2025.2+**, testée sur **2026.9**
- Compatible avec le **tableau de bord Énergie** (consommation d'eau)

## Appareils et capteurs

Chaque compte Sieva est une entrée de l'intégration. Chaque compteur (point
d'installation) du compte est détecté automatiquement et devient un appareil nommé
d'après **son adresse**, avec deux capteurs :

| Capteur | Description |
| --- | --- |
| **Index** (`sensor.<adresse>_index`) | Somme des consommations annuelles en m³ (`total_increasing`), à utiliser dans le tableau de bord Énergie |
| **Consommation de l'année** | Consommation de l'année en cours. L'attribut `par_annee` donne le détail par année |

Les données sont récupérées toutes les 6 heures (une connexion par compte) via
`GetGraphRelevesData` (granularité `Annee`). Si le portail renvoie un total inférieur
au précédent (correction de relevé), l'index garde l'ancienne valeur pour ne pas
fausser les statistiques.

## Installation

### HACS (recommandé)

1. HACS → menu ⋮ → **Dépôts personnalisés**
2. Dépôt : `https://github.com/lorisbc/sieva-home-assistant`, type : **Intégration**
3. Rechercher **Sieva** dans HACS → **Télécharger**
4. Redémarrer Home Assistant

### Manuelle

Copier le dossier `custom_components/sieva` dans `<config>/custom_components/sieva`,
puis redémarrer Home Assistant.

## Configuration

**Paramètres → Appareils et services → Ajouter une intégration → Sieva**, puis saisir
l'identifiant et le mot de passe de l'espace client. Tous les compteurs du compte sont
ajoutés automatiquement.

**Plusieurs comptes** : ajoutez l'intégration une fois par compte. Un compteur ajouté
plus tard au compte apparaît après un rechargement de l'intégration.

Les identifiants sont stockés par Home Assistant dans la configuration de l'intégration
(le portail Sieva ne propose pas d'API à jeton). Si le mot de passe change, Home
Assistant demande de le ressaisir.

### Tableau de bord Énergie

**Paramètres → Tableaux de bord → Énergie → Consommation d'eau → Ajouter une source**
et choisir le capteur **Index**.

## Migration depuis la version 0.x (YAML)

1. Supprimer le bloc `sensor: - platform: sieva` de `configuration.yaml`
2. Mettre à jour l'intégration puis redémarrer
3. Ajouter l'intégration via l'interface

Si vous utilisiez l'ancien capteur `sensor.sieva_m3` (ou `sensor.sieva_m3_external`)
dans le tableau de bord Énergie, remplacez-le par le nouveau capteur **Index**.

## Dépannage

- **Diagnostics** : sur la page de l'intégration, menu ⋮ → *Télécharger les
  diagnostics*. Le fichier contient la réponse brute du portail (identifiants masqués).
- **Logs détaillés** :

  ```yaml
  logger:
    logs:
      custom_components.sieva: debug
  ```

- **Tester hors Home Assistant** :

  ```bash
  python3 -m venv .venv && .venv/bin/pip install aiohttp
  SIEVA_LOGIN=... SIEVA_PASSWORD=... .venv/bin/python scripts/sieva_cli.py
  ```

## Développement

```bash
pip install pytest-homeassistant-custom-component
pytest
```
