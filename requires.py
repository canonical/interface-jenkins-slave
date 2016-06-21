#!/usr/bin/python

import os

from charmhelpers.core.hookenv import (
    config,
    unit_get,
    remote_unit,
    relation_set,
    relation_get,
    relation_ids,
    log,
    DEBUG,
    INFO,
    WARNING,
)
from charmhelpers.core.decorators import (
    retry_on_exception,
)

from charms.reactive import RelationBase
from charms.reactive import hook
from charms.reactive import scopes

HOME = '/var/lib/jenkins'
URL = "http://localhost:8080/"


class JenkinsMaster(RelationBase):
    scope = scopes.GLOBAL

    @hook("{requires:jenkins-slave}-relation-{joined}")
    def joined(self):
        """Indicate the relation is connected and communicate our URL."""
        address = unit_get("private-address")
        log("Setting url relation to http://%s:8080" % address, level=DEBUG)
        relation_set(url="http://%s:8080" % address)

        self.set_state('{relation_name}.connected')

    @hook("{requires:jenkins-slave}-relation-{changed}")
    def changed(self):
        """If the relation data is set, indicate the relation is available."""
        password = self.get_password()
        # Once we have the password, export credentials to the slave so it can
        # download slave-agent.jnlp from the master.
        username = config("username")
        relation_set(username=username)
        relation_set(password=password)

        required_settings = ["executors", "labels", "slavehost"]
        settings = relation_get()
        missing = [s for s in required_settings if s not in settings]
        if missing:
            log("Not all required relation settings received yet "
                "(missing=%s) - skipping" % ", ".join(missing), level=INFO)
            return

        slavehost = settings["slavehost"]
        executors = settings["executors"]
        labels = settings["labels"]

        # Double check to see if this has happened yet
        if "x%s" % (slavehost) == "x":
            log("Slave host not yet defined - skipping", level=INFO)
            return

        log("Adding slave with hostname %s." % slavehost, level=DEBUG)
        self.add_node(slavehost, executors, labels, username, password)
        log("Node slave %s added." % (slavehost), level=DEBUG)

        self.set_state('{relation_name}.available')

    @hook("{requires:jenkins-slave}-relation-{departed}")
    def departed(self):
        """Indicate the relation is no longer available and not connected."""
        # Slave hostname is derived from unit name so
        # this is pretty safe
        slavehost = remote_unit()
        log("Deleting slave with hostname %s." % (slavehost), level=DEBUG)
        self.del_node(slavehost, config("username"), config("password"))
        self.remove_state("{relation_name}.available")
        self.remove_state("{relation_name}.connected")

    @hook("{requires:jenkins-slave}-relation-{broken}")
    def broken(self):
        """Indicate the relation is no longer available and not connected."""
        password = self.get_password()
        for member in relation_ids():
            member = member.replace('/', '-')
            log("Removing node %s from Jenkins master." % member, level=DEBUG)
            del_node(member, config('username'), password)

        self.remove_state("{relation_name}.available")
        self.remove_state("{relation_name}.connected")
        self.remove_state("{relation_name}.tls.available")

    def get_password(self):
        """Return password from the config or the one saved on file."""
        password = config("password")
        if not password:
            passwd_file = os.path.join(HOME, '.admin_password')
            with open(passwd_file, "r") as fd:
                password = fd.read()
        return password

    def add_node(self, host, executors, labels, username, password):
        import jenkins

        @retry_on_exception(2, 2, exc_type=jenkins.JenkinsException)
        def _add_node(*args, **kwargs):
            client = jenkins.Jenkins(URL, username, password)

            if client.node_exists(host):
                log("Node exists - not adding", level=DEBUG)
                return

            log("Adding node '%s' to Jenkins master" % host, level=INFO)
            client.create_node(
                host, int(executors) * 2, host, labels=labels)

            if not client.node_exists(host):
                log("Failed to create node '%s'" % host, level=WARNING)

        return _add_node()

    def del_node(self.host, username, password):
        import jenkins

        client = jenkins.Jenkins(URL, username, password)
        if client.node_exists(host):
            log("Node '%s' exists" % host, level=DEBUG)
            client.delete_node(host)
        else:
            log("Node '%s' does not exist - not deleting" % host, level=INFO)
