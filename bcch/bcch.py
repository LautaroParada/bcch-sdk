# -*- coding: utf-8 -*-
"""
Created on Thu Apr  7 15:12:25 2022

@author: lauta
"""

from bcch.macro_series import BcchAPI

class BancoCentralDeChile(BcchAPI):
    """
    Clase que congrega a toda la funcionalidad del SDK. Hereda la funcionalidad
    desde BcchAPI, y este a su vez desde Requesthandler. De esta manera
    se centraliza la funcionalidad del SDK en solo un punto y no en muchos.
    """
    def __init__(self, usuario:str, clave:str, timeout:int=300):
        #Subclases de la clase "maestra"
        BcchAPI.__init__(self, usuario, clave, timeout)