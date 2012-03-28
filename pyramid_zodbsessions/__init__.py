import binascii
import random
import os
import time
import threading
from hashlib import sha1

from zope.interface import implementer

from repoze.session.manager import SessionDataManager
from repoze.session.data import SessionData

from pyramid_zodbconn import get_connection

from pyramid.compat import text_

from pyramid.interfaces import ISession
from pyramid.session import (
    signed_serialize,
    signed_deserialize,
    )

def SessionFactoryConfig(
    secret,
    timeout=1200,
    period=300,
    cookie_name='session_id',
    cookie_max_age=None,
    cookie_path='/',
    cookie_domain=None,
    cookie_secure=False, 
    cookie_httponly=False,
    cookie_on_exception=True,
    dbname=None,
    rootname='sessions',
    ):
    """
    Configure a :term:`session factory` which will provide session data based
    on the ``repoze.session`` and ``pyramid_zodbconn`` libraries.

    The return value of this function is a :term:`session factory`, which may
    be provided as the ``session_factory`` argument of a
    :class:`pyramid.config.Configurator` constructor, or used as the
    ``session_factory`` argument of the
    :meth:`pyramid.config.Configurator.set_session_factory` method.

    Parameters:

    ``secret``
      A string which is used to sign the cookie.

    ``timeout``
      A number of seconds of inactivity before a session times out.

    ``period``
      Granularity of inactivity checking in seconds (should be lower
      than timeout).

    ``cookie_name``
      The name of the cookie used for sessioning.  Default: ``session``.

    ``cookie_max_age``
      The maximum age of the cookie used for sessioning (in seconds).
      Default: ``None`` (browser scope).

    ``cookie_path``
      The path used for the session cookie.  Default: ``/``.

    ``cookie_domain``
      The domain used for the session cookie.  Default: ``None`` (no domain).

    ``cookie_secure``
      The 'secure' flag of the session cookie.  Default: ``False``.

    ``cookie_httponly``
      The 'httpOnly' flag of the session cookie.  Default: ``False``.

    ``cookie_on_exception``
      If ``True``, set a session cookie even if an exception occurs
      while rendering a view.  Default: ``True``.

    ``dbname``
      The database name passed to ``pyramid_zodbconn.get_connection``.  If
      this is not provided, the unnamed connection will be used.

    ``rootname``
      The key under which the ZODB session manager should be stored in the 
      ZODB root.

    """
    def factory(request):
        try:
            conn = get_connection(request, dbname)
        except TypeError: # no multidb support
            conn = get_connection(request)
        root = conn.root()
        sessions = root.get(rootname)
        if sessions is None:
            sessions = PyramidSessionDataManager(timeout, period)
            root[rootname] = sessions

        cookieval = request.cookies.get(cookie_name)
        
        session_id = None

        if cookieval is not None:
            try:
                session_id = signed_deserialize(cookieval, secret)
            except ValueError:
                pass
            
        if session_id is None:
            session_id = new_session_id()
            def set_cookie_callback(request, response):
                cookieval = signed_serialize(session_id, secret)
                response.set_cookie(
                    cookie_name,
                    value = cookieval,
                    max_age = cookie_max_age,
                    path = cookie_path,
                    domain = cookie_domain,
                    secure = cookie_secure,
                    httponly = cookie_httponly,
                    )
            request.add_response_callback(set_cookie_callback)
                
        session = sessions.query(session_id)
        if session is None:
            session = sessions.get(session_id)
            session._v_new = True

        return session

    return factory

@implementer(ISession)
class ZODBSession(SessionData):
    def changed(self):
        self._p_changed = True

    @property
    def new(self):
        return getattr(self, '_v_new', False)

    # flash API methods
    def flash(self, msg, queue='', allow_duplicate=True):
        storage = self.setdefault('_f_' + queue, [])
        if allow_duplicate or (msg not in storage):
            storage.append(msg)

    def pop_flash(self, queue=''):
        storage = self.pop('_f_' + queue, [])
        return storage

    def peek_flash(self, queue=''):
        storage = self.get('_f_' + queue, [])
        return storage

    # CSRF API methods
    def new_csrf_token(self):
        token = text_(binascii.hexlify(os.urandom(20)))
        self['_csrft_'] = token
        return token

    def get_csrf_token(self):
        token = self.get('_csrft_', None)
        if token is None:
            token = self.new_csrf_token()
        return token

class PyramidSessionDataManager(SessionDataManager):
    _DATA_TYPE = ZODBSession

pid = os.getpid()

def new_session_id():
    """ Returns opaque 40-character session id
        
    An example is: e193a01ecf8d30ad0affefd332ce934e32ffce72
    """
    when = time.time()
    rand = _get_rand_for(when)
    source = '%s%s%s' % (rand, when, pid)
    session_id = sha1(source).hexdigest()
    return session_id

_RANDS = []
_CURRENT_PERIOD = None
_LOCK = threading.Lock()

def _get_rand_for(when):
    """
    There is a good chance that two simultaneous callers will
    obtain the same random number when the system first starts, as
    all Python threads/interpreters will start with the same
    random seed (the time) when they come up on platforms that
    dont have an entropy generator.

    We'd really like to be sure that two callers never get the
    same browser id, so this is a problem.  But since our browser
    id has a time component and a random component, the random
    component only needs to be unique within the resolution of the
    time component to ensure browser id uniqueness.

    We keep around a set of recently-generated random numbers at a
    global scope for the past second, only returning numbers that
    aren't in this set.  The lowest-known-resolution time.time
    timer is on Windows, which changes 18.2 times per second, so
    using a period of one second should be conservative enough.
    """
    period = 1
    this_period = int(when - (when % period))
    _LOCK.acquire()
    try:
        while 1:
            rand = random.randint(0, 99999999)
            global _CURRENT_PERIOD
            if this_period != _CURRENT_PERIOD:
                _CURRENT_PERIOD = this_period
                _RANDS[:] = []
            if rand not in _RANDS:
                _RANDS.append(rand)
                return rand
    finally:
        _LOCK.release()
