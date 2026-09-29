# Sieva – Home Assistant

🇫🇷 [Français](#-français) · 🇬🇧 [English](#-english)

---

## 🇫🇷 Français

Intégration Home Assistant qui récupère la consommation d'eau depuis l'espace client
[SIEVA](https://sieva.fr/) : https://ael.sieva.fr.

> ⚠️ **Uniquement pour les abonnés du SIEVA – Syndicat Intercommunal des Eaux du Val
> d'Azergues** (Rhône), disposant d'un compte sur l'espace client
> [ael.sieva.fr](https://ael.sieva.fr). Elle ne fonctionne pas avec d'autres
> fournisseurs d'eau.

### Fonctionnalités

- Configuration 100 % via l'interface : **identifiant + mot de passe**, rien d'autre
- **Détection automatique des compteurs** du compte (pas besoin de chercher le
  `pointDInstallationId`)
- **Plusieurs comptes** (ex. le vôtre et celui de vos parents) et **plusieurs compteurs
  par compte**
- Un appareil par compteur (ex. `Sieva 1234`), avec l'adresse, le numéro de point
  d'installation et le numéro de compteur
- Compatible avec le **tableau de bord Énergie** (consommation d'eau)
- Ressaisie du mot de passe proposée automatiquement s'il change
- Diagnostics téléchargeables (identifiants, adresses et numéros masqués)
- Aucune dépendance Python externe
- Compatible **Home Assistant 2025.2+**, testée sur **2026.9**

### Installation

#### HACS (recommandé)

1. HACS → menu ⋮ → **Dépôts personnalisés**
2. Dépôt : `https://github.com/lorisbc/sieva-home-assistant`, type : **Intégration**
3. Rechercher **Sieva** dans HACS → **Télécharger**
4. Redémarrer Home Assistant

#### Manuelle

Copier le dossier `custom_components/sieva` dans `<config>/custom_components/sieva`,
puis redémarrer Home Assistant.

### Configuration

**Paramètres → Appareils et services → Ajouter une intégration → Sieva**, puis saisir
l'identifiant (e-mail) et le mot de passe de l'espace client. Tous les compteurs du
compte sont ajoutés automatiquement.

#### Plusieurs comptes

Ajoutez l'intégration **une fois par compte**, chacun avec ses propres identifiants.
Chaque compte a sa propre session : si le mot de passe de l'un change, seul celui-ci
demande à être ressaisi.

```
Sieva
├── moi@example.com
│   ├── Sieva 1234   (1, RUE DE LA PAIX 69380 CHASSELAY)   → Total, Current year
│   └── Sieva 5120   (2, RUE DU LAC 69380 CHASSELAY)       → Total, Current year
└── parents@example.com
    └── Sieva 7342   (3, PLACE DU MARCHÉ 69480 ANSE)       → Total, Current year
```

Un compteur ajouté plus tard sur un compte apparaît après un rechargement de
l'intégration. Un compteur qui disparaît du portail passe en « indisponible ».

### Capteurs

Pour chaque compteur (`1234` = son identifiant interne, voir plus bas) :

| Capteur | Description |
| --- | --- |
| **Total** (`sensor.sieva_1234_total`) | Consommation cumulée en m³ (`total_increasing`). **À utiliser dans le tableau de bord Énergie.** |
| **Current year** (`sensor.sieva_1234_current_year`) | Consommation de l'année civile en cours, en m³. L'attribut `yearly` donne le détail par année. |

Attributs communs aux deux capteurs :

| Attribut | Exemple | Description |
| --- | --- | --- |
| `address` | `1, RUE DE LA PAIX 69380 CHASSELAY` | Adresse desservie |
| `installation_point` | `6900000123` | Numéro du point d'installation |
| `meter` | `C15FA012345` | Numéro du compteur physique |

Vous pouvez renommer l'appareil dans Home Assistant (ex. « Maison », « Parents »).

#### Les trois numéros

Le portail utilise trois numéros différents pour un même compteur :

| Numéro | Exemple | Où le voir | Utilisation dans l'intégration |
| --- | --- | --- | --- |
| Identifiant interne (`pointDInstallationId`) | `1234` | Invisible sur le portail (utilisé par ses requêtes) | Nom de l'appareil (`Sieva 1234`), identifiants des entités, récupération des données |
| Numéro de point d'installation | `6900000123` | Portail → *Point d'installation* | Attribut `installation_point` |
| Numéro de compteur | `C15FA012345` | Portail → *Compteur*, et sur le compteur lui-même | Attribut `meter` et numéro de série de l'appareil |

Si le compteur est remplacé, le numéro de compteur change mais pas les deux
autres : l'appareil et son historique sont conservés.

### Fonctionnement

Toutes les **6 heures**, pour chaque compte :

1. connexion au portail (une seule connexion par compte, quel que soit le nombre de
   compteurs) ;
2. détection des abonnements, puis des points d'installation
   (`AjaxPointDInstallationSynchros`) ;
3. pour chaque compteur, lecture des consommations annuelles (`GetGraphRelevesData`,
   granularité `Annee`).

Le **Total** est la somme de ces consommations annuelles : il augmente à chaque
nouvelle donnée publiée par Sieva. Le portail ne publie qu'une valeur par jour, il
est donc inutile d'interroger plus souvent. Pour forcer une mise à jour : action
`homeassistant.update_entity` sur le capteur Total.

> ℹ️ Le Total part du début de l'historique disponible sur le portail : ce n'est pas
> l'index affiché sur le compteur physique. Cela n'a aucun impact sur le tableau
> de bord Énergie, qui n'utilise que les augmentations.

Si le portail renvoie un total inférieur au précédent (correction de relevé),
le Total garde l'ancienne valeur, pour ne pas être compté comme une remise à zéro du
compteur dans les statistiques.

### Tableau de bord Énergie

**Paramètres → Tableaux de bord → Énergie → Consommation d'eau → Ajouter une source**
et choisir le capteur **Total**.

Si vous suivez aussi le compte de quelqu'un d'autre, ne l'ajoutez pas au tableau de
bord Énergie (il serait additionné à votre consommation) : utilisez plutôt une carte
Statistiques ou Historique.

### Sécurité

Le portail Sieva ne propose pas d'API à jeton : l'identifiant et le mot de passe sont
nécessaires. Ils sont stockés par Home Assistant dans la configuration de
l'intégration, comme pour les autres intégrations cloud, et ne sont envoyés qu'à
`ael.sieva.fr`.

### Migration depuis la version 0.x (YAML)

1. Supprimer le bloc `sensor: - platform: sieva` de `configuration.yaml`
2. Mettre à jour l'intégration puis redémarrer
3. Ajouter l'intégration via l'interface
4. Dans le tableau de bord Énergie, remplacer l'ancien capteur (`sensor.sieva_m3`)
   par le nouveau capteur **Total**

### Dépannage

- **Diagnostics** : page de l'intégration → menu ⋮ → *Télécharger les diagnostics*.
  Le fichier contient les réponses brutes du portail (identifiants, adresses et numéros masqués).
- **Logs détaillés** :

  ```yaml
  logger:
    logs:
      custom_components.sieva: debug
  ```

- **Tester hors Home Assistant** (affiche les compteurs trouvés, les réponses brutes
  et le total) :

  ```bash
  python3 -m venv .venv && .venv/bin/pip install aiohttp
  SIEVA_LOGIN=... SIEVA_PASSWORD=... .venv/bin/python scripts/sieva_cli.py
  ```

### Développement

```bash
pip install pytest-homeassistant-custom-component
pytest
```

La CI GitHub exécute hassfest, la validation HACS et les tests.

---

## 🇬🇧 English

Home Assistant integration that retrieves water consumption from the
[SIEVA](https://sieva.fr/) customer portal: https://ael.sieva.fr.

> ⚠️ **Only for customers of SIEVA – Syndicat Intercommunal des Eaux du Val
> d'Azergues** (Rhône, France), with an account on the
> [ael.sieva.fr](https://ael.sieva.fr) customer portal. It does not work with other
> water providers.

### Features

- UI-only configuration: **login + password**, nothing else
- **Automatic meter discovery** (no need to look up the `pointDInstallationId`)
- **Several accounts** (e.g. yours and your parents') and **several meters per
  account**
- One device per meter (e.g. `Sieva 1234`), with the address, the installation point
  number and the meter serial number
- Works with the **Energy dashboard** (water consumption)
- Automatic re-authentication prompt when the password changes
- Downloadable diagnostics (credentials, addresses and numbers redacted)
- No external Python dependency
- Compatible with **Home Assistant 2025.2+**, tested on **2026.9**

### Installation

#### HACS (recommended)

1. HACS → ⋮ menu → **Custom repositories**
2. Repository: `https://github.com/lorisbc/sieva-home-assistant`, type: **Integration**
3. Search for **Sieva** in HACS → **Download**
4. Restart Home Assistant

#### Manual

Copy `custom_components/sieva` to `<config>/custom_components/sieva`, then restart
Home Assistant.

### Configuration

**Settings → Devices & services → Add integration → Sieva**, then enter the portal
login (e-mail) and password. Every meter of the account is added automatically.

#### Several accounts

Add the integration **once per account**, each with its own credentials. Every
account has its own session: if one password changes, only that account asks for it
again.

```
Sieva
├── me@example.com
│   ├── Sieva 1234   (1, RUE DE LA PAIX 69380 CHASSELAY)   → Total, Current year
│   └── Sieva 5120   (2, RUE DU LAC 69380 CHASSELAY)       → Total, Current year
└── parents@example.com
    └── Sieva 7342   (3, PLACE DU MARCHÉ 69480 ANSE)       → Total, Current year
```

A meter added later to an account shows up after reloading the integration. A meter
no longer returned by the portal becomes unavailable.

### Sensors

For each meter (`1234` = its internal id, see below):

| Sensor | Description |
| --- | --- |
| **Total** (`sensor.sieva_1234_total`) | Cumulated consumption in m³ (`total_increasing`). **Use this one in the Energy dashboard.** |
| **Current year** (`sensor.sieva_1234_current_year`) | Consumption of the current calendar year, in m³. The `yearly` attribute gives the per-year breakdown. |

Attributes shared by both sensors:

| Attribute | Example | Description |
| --- | --- | --- |
| `address` | `1, RUE DE LA PAIX 69380 CHASSELAY` | Served address |
| `installation_point` | `6900000123` | Installation point number |
| `meter` | `C15FA012345` | Physical meter serial number |

You can rename the device in Home Assistant (e.g. "Home", "Parents").

#### The three numbers

The portal uses three different numbers for the same meter:

| Number | Example | Where to see it | Use in the integration |
| --- | --- | --- | --- |
| Internal id (`pointDInstallationId`) | `1234` | Hidden on the portal (used by its requests) | Device name (`Sieva 1234`), entity ids, data retrieval |
| Installation point number | `6900000123` | Portal → *Point d'installation* | `installation_point` attribute |
| Meter serial number | `C15FA012345` | Portal → *Compteur*, and on the meter itself | `meter` attribute and device serial number |

If the meter is replaced, its serial number changes but not the other two: the device
and its history are kept.

### How it works

Every **6 hours**, for each account:

1. log in to the portal (a single login per account, whatever the number of meters);
2. discover the subscriptions, then the installation points
   (`AjaxPointDInstallationSynchros`);
3. for each meter, read the yearly consumption (`GetGraphRelevesData`, `Annee`
   granularity).

The **Total** is the sum of these yearly values: it grows with every new value
published by Sieva. The portal publishes one value per day, so polling more often is
pointless. To force a refresh: `homeassistant.update_entity` action on the Total
sensor.

> ℹ️ The Total starts at the beginning of the history available on the portal: it is
> not the index shown on the physical meter. This has no impact on the Energy
> dashboard, which only uses increases.

If the portal returns a lower total than before (reading correction), the Total keeps
its previous value, so that statistics do not see it as a meter reset.

### Energy dashboard

**Settings → Dashboards → Energy → Water consumption → Add water source** and pick
the **Total** sensor.

If you also track someone else's account, do not add it to the Energy dashboard (it
would be added to your own consumption): use a Statistics or History card instead.

### Security

The Sieva portal has no token-based API: login and password are required. Home
Assistant stores them in the integration configuration, like other cloud
integrations, and they are only sent to `ael.sieva.fr`.

### Migrating from 0.x (YAML)

1. Remove the `sensor: - platform: sieva` block from `configuration.yaml`
2. Update the integration and restart
3. Add the integration from the UI
4. In the Energy dashboard, replace the old sensor (`sensor.sieva_m3`) with the new
   **Total** sensor

### Troubleshooting

- **Diagnostics**: integration page → ⋮ menu → *Download diagnostics*. The file
  contains the raw portal answers (credentials, addresses and numbers redacted).
- **Debug logs**:

  ```yaml
  logger:
    logs:
      custom_components.sieva: debug
  ```

- **Test outside Home Assistant** (prints discovered meters, raw answers and total):

  ```bash
  python3 -m venv .venv && .venv/bin/pip install aiohttp
  SIEVA_LOGIN=... SIEVA_PASSWORD=... .venv/bin/python scripts/sieva_cli.py
  ```

### Development

```bash
pip install pytest-homeassistant-custom-component
pytest
```

GitHub CI runs hassfest, HACS validation and the tests.
