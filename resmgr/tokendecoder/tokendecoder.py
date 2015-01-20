# Copyright (c) 2015 Platform9 Systems Inc.
# All Rights reserved

import base64
import logging
import zlib

"""
Middleware to decode compressed Auth token that is passed in the request.
It decompresses the token and adds it back to the header.
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


class TokenDecoder(object):
    """
    Middleware class which decodes the token
    """
    def __init__(self, app, conf):
        log.info("Setting up token decoder middleware")
        self.app = app
        self.conf = conf

    def __call__(self, environ, start_response):
        """
        Process the request. Extracts the actual token out of the
        compressed token and sets the HTTP_X_AUTH_TOKEN attribute
        in the request.
        """
        try:
            token = self.extract_token(environ)
            environ['HTTP_X_AUTH_TOKEN'] = token
        except Exception, e:
            # We could not decode the token, mark it as authentication failure
            log.exception('Decoding token failed: %s', e)
            resp = MiniResp('Authentication required', environ)
            start_response('401 Unauthorized', resp.headers)
            log.error('Returning error response from token '
                      'decoder middleware: %s', resp.body)
            return resp.body

        # Things look ok in the decode process, pass it down the pipeline
        return self.app(environ, start_response)

    def extract_token(self, environ):
        """
        Extracts the token
        """
        encoded_token = environ['HTTP_X_AUTH_TOKEN']
        # Decode the base64 encoded token string.
        compressed_token = base64.b64decode(encoded_token)
        # Decompress the string to get the actual token
        token = zlib.decompress(compressed_token)

        return token


def filter_factory(global_conf, **local_conf):
    """
    Paste setup method
    """
    conf = global_conf.copy()
    conf.update(local_conf)

    def token_decoder(app):
        return TokenDecoder(app, conf)

    return token_decoder
