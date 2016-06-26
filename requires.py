#!/usr/bin/python

from charmhelpers.core.hookenv import (
    unit_get,
    remote_unit,
    relation_set,
    relation_get,
    relation_ids,
    log,
)

from charms.reactive import RelationBase
from charms.reactive import hook
from charms.reactive import scopes

from charms.layer.jenkins.credentials import Credentials
from charms.layer.jenkins.api import Api


class JenkinsMaster(RelationBase):
    scope = scopes.UNIT

    @hook("{requires:jenkins-slave}-relation-{joined}")
    def joined(self):
        """Indicate the relation is connected and communicate our URL."""
        address = unit_get("private-address")
        log("Setting url relation to http://%s:8080" % address)
        relation_set(url="http://%s:8080" % address)

        # Export credentials to the slave so it can download
        # slave-agent.jnlp from the master.
        log("Setting relation credentials")
        credentials = Credentials()
        relation_set(username=credentials.username())
        relation_set(password=credentials.token())

        self.set_state("{relation_name}.connected")

    @hook("{requires:jenkins-slave}-relation-{changed}")
    def changed(self):
        """If the relation data is set, indicate the relation is available."""
        required_settings = ["executors", "labels", "slavehost"]
        settings = relation_get()
        missing = [s for s in required_settings if s not in settings]
        if missing:
            log("Not all required relation settings received yet "
                "(missing=%s) - skipping" % ", ".join(missing))
            return

        slavehost = settings["slavehost"]

        # Double check to see if this has happened yet
        if "x%s" % (slavehost) == "x":
            log("Slave host not yet defined - skipping")
            return

        log("Registration from slave with hostname %s." % slavehost)
        self.set_state("{relation_name}.available")

    @hook("{requires:jenkins-slave}-relation-{departed}")
    def departed(self):
        """Indicate the relation is no longer available and not connected."""
        # Slave hostname is derived from unit name so
        # this is pretty safe
        slavehost = remote_unit()
        log("Deleting slave with hostname %s." % slavehost)
        api = Api()
        api.delete_node(slavehost.replace("/", "-"))
        self.remove_state("{relation_name}.available")
        self.remove_state("{relation_name}.connected")

    @hook("{requires:jenkins-slave}-relation-{broken}")
    def broken(self):
        """Indicate the relation is no longer available and not connected."""
        api = Api()
        for member in relation_ids():
            member = member.replace("/", "-")
            log("Removing node %s from Jenkins master." % member)
            api.delete_node(member)

        self.remove_state("{relation_name}.available")
        self.remove_state("{relation_name}.connected")
        self.remove_state("{relation_name}.tls.available")

    def slaves(self):
        slaves = []
        for conversation in self.conversations():
            slaves.append({
                "slavehost": conversation.get_remote("slavehost"),
                "executors": conversation.get_remote("executors"),
                "labels": conversation.get_remote("labels"),
            })
        return [slave for slave in slaves if slave["slavehost"]]
