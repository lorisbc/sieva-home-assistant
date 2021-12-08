# Sieva home assistant

This module show your Sieva water consumption inside home assistant.
It is a french water provider.

https://sieva.fr/

## Install

### HACS (recommended)

You can install this custom component using [HACS](https://hacs.xyz/) by adding a custom repository.

### Manual install

Copy this repository inside `config/custom_components/sieva`.

## Configuration

Add this to your `configuration.yaml`:

```yaml
sensor:
  - platform: sieva
    login: !secret sieva.login
    password: !secret sieva.password
    delivery_point: !secret sieva.delivery_point # 1234 
```

To find your `delivery_point`, go to your account and export to csv your consumption. With devTools, inspect the request url for the value of `pointDInstallationId`
Example: `https://ael.sieva.fr/Portail/fr-FR/Usager/Abonnement/ExportGraphReleveDataCSV?pointDInstallationId=XXXX&dateDebut=08/12/2020&dateFin=&granularite=Mois`

This will create a m3 index sensor for the total water consumption.
 

Thanks to https://github.com/cyprieng for template of custom component.
