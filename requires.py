#!/usr/bin/python
from charmhelpers.core.hookenv import (
    unit_get,
    remote_unit,
    relation_set,
    relation_get,
    relation_ids,
    log,
    DEBUG,
    INFO,
)

from charms.reactive import RelationBase
from charms.reactive import hook
from charms.reactive import scopes

from master import Master


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
        # Once we have the password, export credentials to the slave so it can
        # download slave-agent.jnlp from the master.
        master = Master()
        relation_set(username=master.username())
        relation_set(password=master.password())

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
        master.add_node(slavehost, executors, labels=labels)
        log("Node slave %s added." % (slavehost), level=DEBUG)

        self.set_state('{relation_name}.available')

    @hook("{requires:jenkins-slave}-relation-{departed}")
    def departed(self):
        """Indicate the relation is no longer available and not connected."""
        # Slave hostname is derived from unit name so
        # this is pretty safe
        slavehost = remote_unit()
        log("Deleting slave with hostname %s." % slavehost, level=DEBUG)
        master = Master()
        master.delete_node(slavehost)
        self.remove_state("{relation_name}.available")
        self.remove_state("{relation_name}.connected")

    @hook("{requires:jenkins-slave}-relation-{broken}")
    def broken(self):
        """Indicate the relation is no longer available and not connected."""
        master = Master()
        for member in relation_ids():
            member = member.replace('/', '-')
            log("Removing node %s from Jenkins master." % member, level=DEBUG)
            master.delete_node(member)

        self.remove_state("{relation_name}.available")
        self.remove_state("{relation_name}.connected")
        self.remove_state("{relation_name}.tls.available")
