# Sieva – Home Assistant

🇫🇷 [Français](#-français) · 🇬🇧 [English](#-english)

---

## 🇫🇷 Français

Intégration Home Assistant qui récupère la consommation d'eau depuis l'espace client
[Sieva](https://sieva.fr/) (Val d'Azergues) : https://ael.sieva.fr.

### Fonctionnalités

- Configuration 100 % via l'interface : **identifiant + mot de passe**, rien d'autre
- **Détection automatique des compteurs** du compte (pas besoin de chercher le
  `pointDInstallationId`)
- **Plusieurs comptes** (ex. le vôtre et celui de vos parents) et **plusieurs compteurs
  par compte**
- Un appareil par compteur, **nommé d'après son adresse**
- Compatible avec le **tableau de bord Énergie** (consommation d'eau)
- Ressaisie du mot de passe proposée automatiquement s'il change
- Diagnostics téléchargeables (identifiants et adresses masqués)
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
│   ├── 1, RUE DE LA PAIX 69380 CHASSELAY   → Index, Consommation de l'année
│   └── 2, RUE DU LAC 69380 CHASSELAY       → Index, Consommation de l'année
└── parents@example.com
    └── 3, PLACE DU MARCHÉ 69480 ANSE       → Index, Consommation de l'année
```

Un compteur ajouté plus tard sur un compte apparaît après un rechargement de
l'intégration. Un compteur qui disparaît du portail passe en « indisponible ».

### Capteurs

Pour chaque compteur :

| Capteur | Description |
| --- | --- |
| **Index** (`sensor.<adresse>_index`) | Consommation cumulée en m³ (`total_increasing`). **À utiliser dans le tableau de bord Énergie.** |
| **Consommation de l'année** | Consommation de l'année civile en cours, en m³. L'attribut `par_annee` donne le détail par année. |

### Fonctionnement

Toutes les **6 heures**, pour chaque compte :

1. connexion au portail (une seule connexion par compte, quel que soit le nombre de
   compteurs) ;
2. détection des abonnements, puis des points d'installation
   (`AjaxPointDInstallationSynchros`) ;
3. pour chaque compteur, lecture des consommations annuelles (`GetGraphRelevesData`,
   granularité `Annee`).

L'**Index** est la somme de ces consommations annuelles : il augmente à chaque
nouvelle donnée publiée par Sieva. Le portail ne publie qu'une valeur par jour, il
est donc inutile d'interroger plus souvent. Pour forcer une mise à jour : action
`homeassistant.update_entity` sur le capteur Index.

> ℹ️ L'Index part du début de l'historique disponible sur le portail : ce n'est pas
> le chiffre affiché sur le compteur physique. Cela n'a aucun impact sur le tableau
> de bord Énergie, qui n'utilise que les augmentations.

Si le portail renvoie un total inférieur au précédent (correction de relevé),
l'Index garde l'ancienne valeur, pour ne pas être compté comme une remise à zéro du
compteur dans les statistiques.

### Tableau de bord Énergie

**Paramètres → Tableaux de bord → Énergie → Consommation d'eau → Ajouter une source**
et choisir le capteur **Index**.

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
   par le nouveau capteur **Index**

### Dépannage

- **Diagnostics** : page de l'intégration → menu ⋮ → *Télécharger les diagnostics*.
  Le fichier contient les réponses brutes du portail (identifiants et adresses masqués).
- **Logs détaillés** :

  ```yaml
  logger:
    logs:
      custom_components.sieva: debug
  ```

- **Tester hors Home Assistant** (affiche les compteurs trouvés, les réponses brutes
  et l'index) :

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
[Sieva](https://sieva.fr/) (Val d'Azergues, France) customer portal:
https://ael.sieva.fr.

### Features

- UI-only configuration: **login + password**, nothing else
- **Automatic meter discovery** (no need to look up the `pointDInstallationId`)
- **Several accounts** (e.g. yours and your parents') and **several meters per
  account**
- One device per meter, **named after its address**
- Works with the **Energy dashboard** (water consumption)
- Automatic re-authentication prompt when the password changes
- Downloadable diagnostics (credentials and addresses redacted)
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
│   ├── 1, RUE DE LA PAIX 69380 CHASSELAY   → Index, Current year consumption
│   └── 2, RUE DU LAC 69380 CHASSELAY       → Index, Current year consumption
└── parents@example.com
    └── 3, PLACE DU MARCHÉ 69480 ANSE       → Index, Current year consumption
```

A meter added later to an account shows up after reloading the integration. A meter
no longer returned by the portal becomes unavailable.

### Sensors

For each meter:

| Sensor | Description |
| --- | --- |
| **Index** (`sensor.<address>_index`) | Cumulated consumption in m³ (`total_increasing`). **Use this one in the Energy dashboard.** |
| **Current year consumption** | Consumption of the current calendar year, in m³. The `par_annee` attribute gives the per-year breakdown. |

### How it works

Every **6 hours**, for each account:

1. log in to the portal (a single login per account, whatever the number of meters);
2. discover the subscriptions, then the installation points
   (`AjaxPointDInstallationSynchros`);
3. for each meter, read the yearly consumption (`GetGraphRelevesData`, `Annee`
   granularity).

The **Index** is the sum of these yearly values: it grows with every new value
published by Sieva. The portal publishes one value per day, so polling more often is
pointless. To force a refresh: `homeassistant.update_entity` action on the Index
sensor.

> ℹ️ The Index starts at the beginning of the history available on the portal: it is
> not the number shown on the physical meter. This has no impact on the Energy
> dashboard, which only uses increases.

If the portal returns a lower total than before (reading correction), the Index keeps
its previous value, so that statistics do not see it as a meter reset.

### Energy dashboard

**Settings → Dashboards → Energy → Water consumption → Add water source** and pick
the **Index** sensor.

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
   **Index** sensor

### Troubleshooting

- **Diagnostics**: integration page → ⋮ menu → *Download diagnostics*. The file
  contains the raw portal answers (credentials and addresses redacted).
- **Debug logs**:

  ```yaml
  logger:
    logs:
      custom_components.sieva: debug
  ```

- **Test outside Home Assistant** (prints discovered meters, raw answers and index):

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
