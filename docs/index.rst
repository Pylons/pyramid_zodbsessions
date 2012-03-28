pyramid_zodbsessions
====================

``pyramid_zodbsessions`` is an extension for the ``pyramid`` web framework
which allows you to store Pyramid sessions in a ZODB database.

Installation
------------

Install using setuptools, e.g. (within a virtualenv)::

  $ easy_install pyramid_zodbsessions

Dependencies
------------

This package depends on the :term:`pyramid_zodbconn` library for resolving
URIs to ZODB databases and loading those databases from Pyramid
configuration.

Usage
-----

In your Pyramid.ini file, set up a ZODB database to hold sessions

::

  [app:main]
  zodbconn.uri.sessions = file:///home/project/var/Data.fs

In your application's ``main``, create a session factory and use it.  Also,
include ``pyramid_zodbconn`` so the sessions database can be resolved.

::

  from pyramid_zodbsessions import SessionFactoryConfig
  from pyramid.config import Configurator
  session_factory = SessionFactoryConfig('seekri1', dbname='sessions')
  config = Configurator()
  config.include('pyramid_zodbconn')
  config.set_session_factory(session_factory)

More Information
----------------

.. toctree::
   :maxdepth: 1

   api.rst
   glossary.rst

Reporting Bugs / Development Versions
-------------------------------------

Visit https://github.com/Pylons/pyramid_zodbsessions/issues to report bugs.
Visit https://github.com/Pylons/pyramid_zodbsessions to download development
or tagged versions.

Indices and tables
------------------

* :ref:`glossary`
* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
