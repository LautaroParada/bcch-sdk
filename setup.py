import pathlib
from setuptools import setup, find_packages

HERE = pathlib.Path(__file__).parent

VERSION = '0.0.1'
PACKAGE_NAME = 'bcch'
AUTHOR = 'Lautaro Parada Opazo'
AUTHOR_EMAIL = 'lautaro.parada.opazo@gmail.com'
URL = 'https://github.com/LautaroParada/bcch-sdk'

LICENSE = 'Apache License 2.0'
DESCRIPTION = 'Cliente en Python para la API del Banco Central de Chile'
LONG_DESCRIPTION = (HERE / "README.md").read_text()
LONG_DESC_TYPE = "text/markdown"

INSTALL_REQUIRES = [
      'requests'
]

setup(name=PACKAGE_NAME,
      version=VERSION,
      description=DESCRIPTION,
      long_description=LONG_DESCRIPTION,
      long_description_content_type=LONG_DESC_TYPE,
      author=AUTHOR,
      license=LICENSE,
      author_email=AUTHOR_EMAIL,
      url=URL,
      install_requires=INSTALL_REQUIRES,
      packages=find_packages()
      )