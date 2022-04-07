# API del BCCh SDK

[![forthebadge made-with-python](http://ForTheBadge.com/images/badges/made-with-python.svg)](https://www.python.org/) [![Python Version](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://shields.io/) ![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)

**Contents**

1. [Descripción general](#descripción-general-arrow_up)
2. [Requerimientos](#requerimientos-arrow_up)
3. [Instalación](#instalación-arrow_up)
4. [Demo](#instalación-arrow_up)
5. [Documentación](#documentación-arrow_up)
6. [Disclaimer](#disclaimer-arrow_up)

## Descripción general [:arrow_up:](#api-del-bcch-sdk)

Cliente no oficial de la API de la bases de datos estadísticos del Banco Central de Chile. Está diseñada para extraer datos macroeconómicos, los cuales deberán ser convertidos en hallazgos que gatillen patrones de comportamiento en Chile y en el mundo. Fue programado en Python :snake:

Escribí un articulo en mi blog comentando su funcionalidad, recomendaciones y un caso de uso práctico. Pueden encontrar el articulo en este link.

## Requerimientos [:arrow_up:](#api-del-bcch-sdk)

- Necesitaras acceso a los datos de la API. Los puedes solicitar en el siguiente [link](https://si3.bcentral.cl/estadisticas/Principal1/Web_Services/index.htm).
- ```Python``` >= 3.7

## Instalación [:arrow_up:](#api-del-bcch-sdk)
```python
pip install bcch
```
## Demo [:arrow_up:](#api-del-bcch-sdk)
```python
#Librerias base
import pandas as pd
import os

from bcch import BancoCentralDeChile

# Por seguridad, es mejor guardar las contraseñas y usuarios en las variables de entorno
bcch_user = os.environ['BCCH_USER']
bcch_pwd = os.environ['BCCH_PWD']

# Creación de la instancia
client = BancoCentralDeChile(bcch_user, bcch_pwd)

# Solicitar la Deuda pública en relación al PIB (porcentaje del PIB)
resp = pd.DataFrame(
    client.get_macro(serie='F051.D7.PPB.C.Z.Z.T')
    )
```
*Tutorial sobre como guardar y llamar variables de ambiente en Python -> [Hiding Passwords and Secret Keys in Environment Variables (Windows)](https://youtu.be/IolxqkL7cD8)*

## Documentación [:arrow_up:](#api-del-bcch-sdk)

Todos los métodos de la documentación van a ocupar la siguiente instancia de la clase del SDK

```python
import os
from bcch import BancoCentralDeChile

# Por seguridad, es mejor guardar las contraseñas y usuarios en las variables de entorno
bcch_user = os.environ['BCCH_USER']
bcch_pwd = os.environ['BCCH_PWD']

# Creación de la instancia
client = BancoCentralDeChile(bcch_user, bcch_pwd)
```

### Series macroeconomicas
- ```get_macro```: Método para solicitar datos macroeconómicos en base a una id correspondiente.
	- Argumentos:
		- ```serie```(**requerido**): ID de los datos a solicitar. El catalogo completo se puede revisar en el archivo [Excel del Banco](https://si3.bcentral.cl/estadisticas/Principal1/Web_Services/index.htm)
		- ```from_```(opcional): Ingresar fecha desde la cual se requiere recoger datos. Si el parámetro no está presente, se recoge por defecto desde el primer dato disponible. El formato a ocupar es el siguiente ```YYYY-MM-DD```
		- ```to_```(opcional): Ingresar fecha hasta la cual se requiere recoger datos. Si el parámetro no está presente, se recoge por defecto hasta el último dato disponible. El formato a ocupar es el siguiente ```YYYY-MM-DD```

## Disclaimer [:arrow_up:](#api-del-bcch-sdk)
La información contenida en este documento es solo para fines informativos y educativos. Nada de lo contenido en este documento se podrá interpretar como asesoramiento financiero, legal o impositivo. El contenido de este documento corresponde únicamente a la opinión del autor, el cual no es un asesor financiero autorizado ni un asesor de inversiones registrado. El autor no está afiliado como promotor de los servicios del Banco Central de Chile.

Este documento no es una oferta para vender ni comprar instrumentos financieros. Nunca invierta más de lo que puede permitirse perder. Usted debe consultar a un asesor profesional registrado antes de realizar cualquier inversión.