# -*- coding: utf-8 -*-
"""
Created on Thu Apr  7 14:26:18 2022

@author: lauta
"""

import requests
import pandas as pd
import os

bcch_user = os.environ['BCCH_USER']
bcch_pwd = os.environ['BCCH_PWD']
serie = 'F013.IBC.IND.N.7.LAC.CL.CLP.BLO.D'

url = "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx?user={}&pass={}&timeseries={}&function=GetSeries".format(bcch_user, bcch_pwd, serie)

resp = requests.get(url).json()

if resp['Descripcion'] == 'Success':
    print(pd.DataFrame(resp['Series']['Obs']))
else:
    print('Error')

# Catalogo de series de datos    
test = pd.read_excel('https://si3.bcentral.cl/estadisticas/Principal1/Web_Services/Webservices/series.xlsx')


#%% test al SDK

from bcch import BancoCentralDeChile
import os
import pandas as pd

bcch_user = os.environ['BCCH_USER']
bcch_pwd = os.environ['BCCH_PWD']
serie = 'F073.IVP.PRE.Z.D'

client = BancoCentralDeChile(bcch_user, bcch_pwd)

resp = client.get_macro(serie=serie)
