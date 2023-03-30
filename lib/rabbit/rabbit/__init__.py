import json
import requests
from six.moves.urllib.parse import quote

class RabbitMgmtClient(object):
    """
    Queries the RabbitMQ Management HTTP API
    """

    def __init__(self,
                 user,
                 password,
                 amqp_host,
                 amqp_mgmt_port=15672,
                 vhost='/'):
        self.endpoint = 'http://%s:%s/api/' % (amqp_host, amqp_mgmt_port)
        self.vhost = quote(vhost, safe='')
        self.request_kwargs = {'auth' : (user, password)}

    def create_user(self, user, password, tags=''):
        """
        :param tags: csv of the tags to give to the user
        :type tags: str
        """
        body = {'password' : password,
                'tags' : tags}
        headers = {'Content-type': 'application/json'}
        url = self.endpoint + 'users/' +  user
        resp = requests.put(url,
                            headers=headers,
                            data=json.dumps(body),
                            **self.request_kwargs)
        resp.raise_for_status()

    def delete_user(self, user):
        url = self.endpoint + 'users/' +  user
        resp = requests.delete(url, **self.request_kwargs)
        resp.raise_for_status()

    def set_permissions(self, user, config, write, read):
        body = {'configure' : config,
                'write' : write,
                'read' : read}
        headers = {'Content-type': 'application/json'}
        url = self.endpoint + 'permissions/' + self.vhost + '/' + user
        resp = requests.put(url,
                            headers=headers,
                            data=json.dumps(body),
                            **self.request_kwargs)
        resp.raise_for_status()

