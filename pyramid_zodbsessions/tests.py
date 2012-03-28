import unittest
from pyramid import testing

from zope.interface.verify import verifyObject

from pyramid.interfaces import ISession
from pyramid.session import signed_deserialize, signed_serialize

class TestSessionFactoryConfig(unittest.TestCase):
    def _makeOne(self, *arg, **kw):
        from . import SessionFactoryConfig
        return SessionFactoryConfig(*arg, **kw)
    
    def test_no_sessions_manager(self):
        factory = self._makeOne('secret')
        request = testing.DummyRequest()
        connection = DummyConnection()
        def get_connection(request, dbname):
            self.assertEqual(dbname, None)
            return connection
        session = factory(request, get_connection=get_connection)
        self.assertEqual(session.__class__.__name__, 'ZODBSession')
        self.assertEqual(connection._root['sessions'].__class__.__name__,
                         'PyramidSessionDataManager')
        verifyObject(ISession, session)

    def test_with_sessions_manager(self):
        from . import PyramidSessionDataManager
        factory = self._makeOne('secret')
        request = testing.DummyRequest()
        manager = PyramidSessionDataManager(10, 5)
        root = {'sessions':manager}
        connection = DummyConnection(root)
        def get_connection(request, dbname):
            self.assertEqual(dbname, None)
            return connection
        factory(request, get_connection=get_connection)
        self.assertEqual(connection._root['sessions'], manager)

    def test_cookieval_callback_no_cookie_set(self):
        factory = self._makeOne('secret')
        request = testing.DummyRequest()
        connection = DummyConnection()
        def get_connection(request, dbname):
            self.assertEqual(dbname, None)
            return connection
        def new_session_id():
            return '1'
        factory(request, get_connection=get_connection, 
                new_session_id=new_session_id)
        self.assertEqual(len(request.response_callbacks), 1)
        response = DummyResponse()
        request.response_callbacks[0](request, response)
        self.assertEqual(response.name, 'session_id')
        self.assertEqual(
            signed_deserialize(response.kw['value'], 'secret'), '1')

    def test_cookie_already_set_new_session(self):
        factory = self._makeOne('secret')
        request = testing.DummyRequest()
        request.cookies['session_id'] = signed_serialize('1', 'secret')
        connection = DummyConnection()
        def get_connection(request, dbname):
            self.assertEqual(dbname, None)
            return connection
        session = factory(request, get_connection=get_connection)
        self.assertEqual(len(request.response_callbacks), 0)
        self.assertEqual(session.id, '1')
        self.assertTrue(session._v_new)

    def test_cookie_already_set_existing_session(self):
        from . import PyramidSessionDataManager
        factory = self._makeOne('secret')
        request = testing.DummyRequest()
        request.cookies['session_id'] = signed_serialize('1', 'secret')
        manager = PyramidSessionDataManager(10, 5)
        expected = manager.get('1')
        root = {'sessions':manager}
        connection = DummyConnection(root)
        def get_connection(request, dbname):
            self.assertEqual(dbname, None)
            return connection
        session = factory(request, get_connection=get_connection)
        self.assertEqual(session, expected)

    def test_cookieval_bad(self):
        factory = self._makeOne('secret')
        request = testing.DummyRequest()
        request.cookies['session_id'] = 'wtf'
        connection = DummyConnection()
        def get_connection(request, dbname):
            self.assertEqual(dbname, None)
            return connection
        def new_session_id():
            return '1'
        factory(request, get_connection=get_connection, 
                new_session_id=new_session_id)
        self.assertEqual(len(request.response_callbacks), 1)
        response = DummyResponse()
        request.response_callbacks[0](request, response)
        self.assertEqual(response.name, 'session_id')
        self.assertEqual(
            signed_deserialize(response.kw['value'], 'secret'), '1')

class TestZODBSession(unittest.TestCase):
    def _makeOne(self):
        from . import ZODBSession
        return ZODBSession()

    def test_changed(self):
        inst = self._makeOne()
        class DummyJar(object):
            def register(self, *arg, **kw):
                pass
        inst._p_jar = DummyJar()
        inst.changed()
        self.assertEqual(inst._p_changed, True)

    def test_new_false(self):
        inst = self._makeOne()
        self.assertFalse(inst.new)

    def test_new_true(self):
        inst = self._makeOne()
        inst._v_new = True
        self.assertTrue(inst.new)

    def test_flash_default(self):
        session = self._makeOne()
        session.flash('msg1')
        session.flash('msg2')
        self.assertEqual(session['_f_'], ['msg1', 'msg2'])

    def test_flash_allow_duplicate_false(self):
        session = self._makeOne()
        session.flash('msg1')
        session.flash('msg1', allow_duplicate=False)
        self.assertEqual(session['_f_'], ['msg1'])

    def test_flash_allow_duplicate_true_and_msg_not_in_storage(self):
        session = self._makeOne()
        session.flash('msg1', allow_duplicate=True)
        self.assertEqual(session['_f_'], ['msg1'])

    def test_flash_allow_duplicate_false_and_msg_not_in_storage(self):
        session = self._makeOne()
        session.flash('msg1', allow_duplicate=False)
        self.assertEqual(session['_f_'], ['msg1'])

    def test_flash_mixed(self):
        session = self._makeOne()
        session.flash('warn1', 'warn')
        session.flash('warn2', 'warn')
        session.flash('err1', 'error')
        session.flash('err2', 'error')
        self.assertEqual(session['_f_warn'], ['warn1', 'warn2'])

    def test_pop_flash_default_queue(self):
        session = self._makeOne()
        queue = ['one', 'two']
        session['_f_'] = queue
        result = session.pop_flash()
        self.assertEqual(result, queue)
        self.assertEqual(session.get('_f_'), None)

    def test_pop_flash_nodefault_queue(self):
        session = self._makeOne()
        queue = ['one', 'two']
        session['_f_error'] = queue
        result = session.pop_flash('error')
        self.assertEqual(result, queue)
        self.assertEqual(session.get('_f_error'), None)

    def test_peek_flash_default_queue(self):
        session = self._makeOne()
        queue = ['one', 'two']
        session['_f_'] = queue
        result = session.peek_flash()
        self.assertEqual(result, queue)
        self.assertEqual(session.get('_f_'), queue)

    def test_peek_flash_nodefault_queue(self):
        session = self._makeOne()
        queue = ['one', 'two']
        session['_f_error'] = queue
        result = session.peek_flash('error')
        self.assertEqual(result, queue)
        self.assertEqual(session.get('_f_error'), queue)

    def test_new_csrf_token(self):
        session = self._makeOne()
        token = session.new_csrf_token()
        self.assertEqual(token, session['_csrft_'])

    def test_get_csrf_token(self):
        session = self._makeOne()
        session['_csrft_'] = 'token'
        token = session.get_csrf_token()
        self.assertEqual(token, 'token')
        self.assertTrue('_csrft_' in session)

    def test_get_csrf_token_new(self):
        session = self._makeOne()
        token = session.get_csrf_token()
        self.assertTrue(token)
        self.assertTrue('_csrft_' in session)
        
class DummyConnection(object):
    def __init__(self, root=None):
        if root is None:
            root = {}
        self._root = root

    def root(self):
        return self._root

class DummyResponse(object):
    def set_cookie(self, name, **kw):
        self.name = name
        self.kw = kw
