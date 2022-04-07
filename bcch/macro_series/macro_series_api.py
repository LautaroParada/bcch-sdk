# -*- coding: utf-8 -*-
"""
Created on Thu Apr  7 14:43:47 2022

@author: lauta
"""

from bcch.request_handler_class import RequestHandler

class BcchAPI(RequestHandler):
    def __init__(self, usuario:str, clave:str, timeout:int=300):
        
        self.HOST = 'https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx'
        super().__init__(usuario, clave, timeout)
        
    def get_macro(self, **query_params):
        """
        Obtener los valores historicos para la serie solicitada

        Parameters
        ----------
        **query_params : dict
            parametros de la query a ingresar a la API.

        Returns
        -------
        list
            valores historicos para la serie de datos macroeconomicos.

        """
        return super().handle_request(self.HOST, query_params, 'GetSeries')

    def get_busqueda(self, **query_params):
        """
        Permite ver la lista de series disponibles por frecuencia y su metadata.

        Parameters
        ----------
        **query_params : dict
            parametros de la query a ingresar a la API.

        Returns
        -------
        list
            series con su metadata.

        """
        return super().handle_request(self.HOST, query_params, 'SearchSeries')

