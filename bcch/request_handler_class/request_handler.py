# -*- coding: utf-8 -*-
"""
Created on Thu Apr  7 15:18:00 2022

@author: lauta
"""

import requests
from typing import Dict

class RequestHandler():
    def __init__(self, usuario:str, clave:str, timeout:int):
        self.usuario = usuario
        self.clave = clave
        self.timeout = timeout
        self.resp = None
        
    # -------------------------------------------
    # Metodos para preprocesar la data
    # -------------------------------------------
        
    def handle_request(self, endpoint_url, query_params: Dict[str, str], func:str):
        """
        Punto central para solcitar datos a la API del BCCh

        Parameters
        ----------
        query_params : Dict[str, str], optional
            query parameters of the request. The default is {}.

        Returns
        -------
        dict
            Respuesta desde la API.

        """
        # append el usuario y clave a los parametros de la query
        query_params_ = self.__append_fmt(query_params, func=func)
        
        self.resp = requests.get(url=endpoint_url,
                                 params=query_params_,
                                 timeout=self.timeout)
        
        if self.resp.status_code == 200:
            if func == 'GetSeries':
                return self.resp.json()['Series']['Obs']
            if func == 'SearchSeries':
                return self.resp.json()['SeriesInfos']
        else:
            print(f"Error en el llamado. Descripción {self.resp.json()['Descripcion']} Codigo: {self.resp.json()['Codigo']}")
    
    def __append_fmt(self, dict_to_append, func:str):
        """
        Append the type of format and api key to the query parameters

        Parameters
        ----------
        dict_to_append : dict
            paramters of the request.

        Returns
        -------
        dict_to_append : dict
            full dict of paramters of the request.

        """    
        # Parametros obligatorios
        dict_to_append['user'] = self.usuario
        dict_to_append['pass'] = self.clave
        
        if func == 'GetSeries':
            dict_to_append['function'] = 'GetSeries'
        
        if func == 'SearchSeries':
            dict_to_append['function'] = 'SearchSeries'
        
        # normalizando los parametros de las fechas
        # fecha de inicio
        if 'firstdate' in dict_to_append:
            dict_to_append['from_'] = dict_to_append.pop('firstdate')
        
        if 'from_' in dict_to_append:
            dict_to_append['firstdate'] = dict_to_append.pop('from_')
            
        # fecha de termino
        if 'lastdate' in dict_to_append:
            dict_to_append['to_'] = dict_to_append.pop('lastdate')
            
        if 'to_' in dict_to_append:
            dict_to_append['lastdate'] = dict_to_append.pop('to_')
            
        # serie macroeconomica
        if 'timeseries' in dict_to_append:
            dict_to_append['serie'] = dict_to_append.pop('timeseries')
            
        if 'serie' in dict_to_append:
            dict_to_append['timeseries'] = dict_to_append.pop('serie')
            
        # Frequencia o Periodicidad
        if 'frequency' in dict_to_append:
            dict_to_append['frecuencia'] = dict_to_append.pop('frequency ')
            
        if 'frecuencia' in dict_to_append:
            dict_to_append['frequency'] = dict_to_append.pop('frecuencia')
            
        return dict_to_append