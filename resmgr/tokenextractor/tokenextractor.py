# Copyright (c) 2019 Platform9 Systems Inc.
# All Rights reserved

import logging
from six.moves.http_cookies import SimpleCookie

"""
Middleware to extract Auth token that is passed in the request as part of the
Cookie
"""

log = logging.getLogger('resmgr')


class MiniResp(object):
    """
    Class to deal with error responses
    """
    def __init__(self, error_message, env, headers=[]):
        # The HEAD method is unique: it must never return a body, even if
        # it reports an error (RFC-2616 clause 9.4). We relieve callers
        # from varying the error responses depending on the method.
        if env['REQUEST_METHOD'] == 'HEAD':
            self.body = ['']
        else:
            self.body = [error_message]
        self.headers = list(headers)
        self.headers.append(('Content-type', 'text/plain'))


class TokenExtractor(object):
    """
    Middleware class which extracts the token
    """
    def __init__(self, app, conf):
        log.info("Setting up token extractor middleware")
        self.app = app
        self.conf = conf

    def __call__(self, environ, start_response):
        """
        Process the request. Extracts the actual token out of the
        cookie and sets the HTTP_X_AUTH_TOKEN attribute
        in the request.
        """
        try:
            token = self.extract_token(environ)
            environ['HTTP_X_AUTH_TOKEN'] = token
        except Exception as e:
            # We could not extract the token, mark it as authentication failure
            log.exception('Extracting token failed: %s, environ: %s', e, environ)
            resp = MiniResp('Authentication required', environ)
            start_response('401 Unauthorized', resp.headers)
            log.error('Returning error response from token '
                      'extractor middleware: %s', resp.body)
            return resp.body

        # Things look ok in the extract process, pass it down the pipeline
        return self.app(environ, start_response)

    def extract_token(self, environ):
        """
        Extracts the token
        """

        # Try the cookie first, and fall back to the header
        token = None
        if 'HTTP_COOKIE' in environ:
            cookie = SimpleCookie(environ['HTTP_COOKIE'])
            if 'X-Auth-Token' in cookie:
                token = cookie['X-Auth-Token'].value
                log.debug('Extracted token from cookie')
        if not token:
            token = environ['HTTP_X_AUTH_TOKEN']

        return token

def filter_factory(global_conf, **local_conf):
    """
    Paste setup method
    """
    conf = global_conf.copy()
    conf.update(local_conf)

    def token_extractor(app):
        return TokenExtractor(app, conf)

    return token_extractor
