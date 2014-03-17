# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights reserved

import pecan
import functools

def enforce(required = []) :
    """
    Generates a decorator that checks permissions before calling the
    contained pecan handler function.
    :param list[str] required: Roles require to run function.
    """
    def _enforce(fun) :

        @functools.wraps(fun)
        def newfun(self, *args, **kwargs) :
            # if either the attribute or key isn't there, enforcement is 'on'
            if hasattr(pecan.conf, 'resmgr') :
                do_enforce = pecan.conf.resmgr.get('enforce_policy', True)
            else :
                do_enforce = True

            if not (do_enforce and required) :
                return fun(self, *args, **kwargs)
            else :
                roles_hdr = pecan.core.request.headers.get('X-Roles')
                if roles_hdr :
                    roles = roles_hdr.split(',')
                else :
                    roles = []

                if set(roles) & set(required):
                    return fun(self, *args, **kwargs)
                else :
                    return pecan.abort(403)
        return newfun
    return _enforce


