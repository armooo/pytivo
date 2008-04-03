import ez_setup
ez_setup.use_setuptools()

from setuptools import setup
setup(
    name = "pyTivo",
    description="Tivo media server",
    url="http://pytivo.armooo.net/",

    packages = ['pyTivo',],
    install_requires = [
        'lrucache',
        #'eyed3', # eyed3 uses a configure script to create setup.py
        'Cheetah',
    ],
    dependency_links  = [
        'http://evan.prodromou.name/lrucache/',
        #'http://eyed3.nicfit.net/releases/',
    ],
    entry_points = {
        'console_scripts' : ['pytivo = pyTivo.pyTivo:main',],
        'gui_scripts' : ['pytivoconfigurator = pyTivo.pyTivoConfigurator:main',],
    },
    include_package_data = True
)
