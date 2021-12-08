# Sieva home assistant

This module show your Sieva water consumption inside home assistant.


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

This will create a m3 index sensor for the total water consumption.
 
