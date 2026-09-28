# Sieva pour Home Assistant

Intégration Home Assistant qui récupère la consommation d'eau depuis l'espace client
[Sieva](https://sieva.fr/) (Val d'Azergues), https://ael.sieva.fr.

- Configuration 100 % via l'interface (pas de YAML)
- Aucune dépendance Python externe (aiohttp fourni par Home Assistant)
- Compatible **Home Assistant 2025.2+**, testée sur **2026.9**
- Compatible avec le **tableau de bord Énergie** (consommation d'eau)

## Capteurs

| Entité | Description |
| --- | --- |
| `sensor.compteur_d_eau_sieva_<pi>_index` | Index en m³ = somme des consommations annuelles depuis le début du contrat (`total_increasing`, à utiliser dans le tableau de bord Énergie) |
| `sensor.compteur_d_eau_sieva_<pi>_consommation_de_l_annee` | Consommation de l'année en cours. L'attribut `par_annee` donne le détail par année |

Les données sont interrogées toutes les 6 heures via l'appel
`GetGraphRelevesData` (granularité `Annee`). Si le portail renvoie un total inférieur
au précédent (correction de relevé), l'index conserve l'ancienne valeur pour ne pas
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

**Paramètres → Appareils et services → Ajouter une intégration → Sieva**, puis saisir :

- votre identifiant et votre mot de passe de l'espace client ;
- le **point d'installation** (`pointDInstallationId`).

### Trouver le point d'installation

1. Se connecter sur https://ael.sieva.fr et ouvrir la page **Consommations**
2. Ouvrir les outils de développement du navigateur (F12) → onglet **Réseau**
3. Repérer la requête `GetGraphRelevesData` : son corps contient
   `"pointDInstallationId":"XXXX"` → `XXXX` est la valeur à saisir.

> Ce n'est pas le numéro présent dans l'URL `/Consommations/NNNNN`.

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
  pip install aiohttp
  SIEVA_LOGIN=... SIEVA_PASSWORD=... SIEVA_PI=4064 python scripts/sieva_cli.py
  ```

## Développement

```bash
pip install pytest-homeassistant-custom-component
pytest
```
