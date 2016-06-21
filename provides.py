#!/usr/bin/python

from charms.reactive import RelationBase
from charms.reactive import hook
from charms.reactive import scopes


class JenkinsSlave(RelationBase):
    scope = scopes.GLOBAL

    @hook('{provides:jenkins-slave}-relation-{joined,changed}')
    def joined_or_changed(self):
        ''' Set the connected state from the provides side of the relation. '''
        self.set_state('{relation_name}.connected')

    @hook('{provides:etcd}-relation-{broken,departed}')
    def broken_or_departed(self):
        '''Remove connected state from the provides side of the relation. '''
        self.remove_state('{relation_name}.connected')

    def set_client_credentials(self, key, cert, ca):
        ''' Set the client credentials on the global conversation for this
        relation. '''
        self.set_remote('client_key', key)
        self.set_remote('client_ca', ca)
        self.set_remote('client_cert', cert)

    def set_connection_string(self, connection_string):
        ''' Set the connection string on the global conversation for this
        relation. '''
        self.set_remote('connection_string', connection_string)
