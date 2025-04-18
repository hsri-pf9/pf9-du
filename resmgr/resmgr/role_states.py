# Copyright 2016 Platform9 Systems Inc. All Rights Reserved

"""
Valid role state, strings and transitions.
See https://platform9.atlassian.net/wiki/display/~rdeuel/2016/08/30/Resource+Manager+Changes+v2.3
"""
# pylint: disable=too-few-public-methods

class _RoleState(object):
    """
    Class to hold role state names and legal transitions. Don't
    construct these directly. Use the constants below or fetch
    one with the from_name function.
    """
    roles = {}
    def __init__(self, name, valid_next):
        self.name = name
        self.valid_next = valid_next
        self.roles[name] = self

    def __repr__(self):
        return self.name

    def __eq__(self, other):
        """
        Compare a _RoleState object to another, or to its name,
        both of which will return true when there's a name match.
        Note that python will reverse the order when necessary,
        so this could be used both with 'applied' == APPLIED,
        and APPLIED == 'applied'. Obviously APPLIED == APPLIED as
        well.
        """
        if not (isinstance(other, str) or \
                isinstance(other, _RoleState)):
            return False
        else:
            # match names only, or strings
            return self.name == str(other)

def from_name(name):
    """
    Get a KeyError if the role isn't defined, otherwise get
    the _RoleState object.
    """
    return _RoleState.roles[name]

def legal_transition(old_state, new_state):
    """
    check to see if the next state is legal.
    """
    if isinstance(old_state, _RoleState):
        return str(new_state) in old_state.valid_next
    else:
        return str(new_state) in from_name(old_state).valid_next

def role_is_authed(state_name):
    """
    True when a role is in a state where it's considered
    assigned to the host.
    """
    role_state = from_name(state_name)
    return role_state in [APPLIED,
                          START_APPLY,
                          START_EDIT,
                          PRE_AUTH,
                          AUTH_CONVERGING,
                          AUTH_CONVERGED,
                          AUTH_ERROR]

def role_is_failed(state_name):
    """
    True when a role is in a state where it's failed.
    """
    role_state = from_name(state_name)
    return role_state in [DEAUTH_ERROR, AUTH_ERROR]

def role_is_converging(state_name):
    """
    True when a role is in a state where it's in the middle somewhere.
    """
    role_state = from_name(state_name)
    return role_state in [START_APPLY,
                          START_EDIT,
                          PRE_AUTH,
                          AUTH_CONVERGING,
                          AUTH_CONVERGED,
                          START_DEAUTH,
                          PRE_DEAUTH,
                          DEAUTH_CONVERGING,
                          DEAUTH_CONVERGED]

NOT_APPLIED = _RoleState('not-applied', ['start-apply'])
START_APPLY = _RoleState('start-apply', ['not-applied', 'pre-auth'])
PRE_AUTH = _RoleState('pre-auth', ['auth-converging'])
AUTH_CONVERGING = _RoleState('auth-converging', ['auth-converged', 'auth-error'])
AUTH_CONVERGED = _RoleState('auth-converged', ['applied', 'auth-error'])
AUTH_ERROR = _RoleState('auth-error', ['start-apply', 'start-deauth'])
APPLIED = _RoleState('applied', ['start-edit', 'start-deauth'])
START_EDIT = _RoleState('start-edit', ['pre-auth', 'applied'])
START_DEAUTH = _RoleState('start-deauth', ['pre-deauth', 'applied'])
PRE_DEAUTH = _RoleState('pre-deauth', ['deauth-converging'])
DEAUTH_CONVERGING = _RoleState('deauth-converging',
                               ['deauth-converged', 'deauth-error'])
DEAUTH_CONVERGED = _RoleState('deauth-converged',
                              ['deauth-error', 'not-applied'])
DEAUTH_ERROR = _RoleState('deauth-error', ['start-deauth'])

class InvalidState(Exception):
    def __init__(self, old_state, new_state):
        super(InvalidState, self).__init__('Bad state transition %s->%s' %
                                           (old_state, new_state))
