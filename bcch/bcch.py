# -*- coding: utf-8 -*-
"""
Created on Thu Apr  7 15:12:25 2022

@author: lauta
"""

from bcch.macro_series import BcchAPI

class BancoCentralDeChile(BcchAPI):
    def __init__(self, usuario:str, clave:str, timeout:int=300):
        #Subclases de la clase "maestra"
        BcchAPI.__init__(self, usuario, clave, timeout)