#!/usr/bin/env python

from __future__ import print_function

from functools import partial

import os

import socket
import math
import rospy

import pycfs
from pycfs.serialization import Formatter,CommandFactory,TelemetryFactory,CStruct
from pycfs.listener import UDPListener
from pycfs.commander import UDPCommander

from std_msgs.msg import Empty

import importlib

def get_cmd_topic(mid, cc):
    return '{}/{}'


class CFSBridge(object):
    def __init__(self, host, cmd_port, tlm_port, cmd_types, tlm_types):
        """
        cmd_types is a list of thruples (mid, cc, cfs typename)
        tlm_types is a list of tuples (mid, cfs typename)
        are lists of pairs (cFS message id, ros cfs qualified message name)
        """
        self.host = host
        self.cmd_port = cmd_port
        self.tlm_port = tlm_port


        self.bundle_path = rospy.get_param('~bundle_path')
        self.mission = rospy.get_param('~mission')
        self.target = rospy.get_param('~target')
        self.apps = rospy.get_param('~apps')
        self.msg_package = rospy.get_param('~msg_package')

        MID,CID,MSG,cfs_parser = pycfs.load_bundle(
                self.bundle_path,
                mission=self.mission, target=self.target,
                apps=self.apps,
                use_cache=True)

        rospy.loginfo('Loaded cfs message types.')

        self.message_ids = MID
        self.command_codes = CID
        self.type_specs = MSG

        # store command / tlm types
        self.cmd_types = [
                (ct if (len(ct) == 3) else ct+[None]*(3-len(ct)))
                for ct in cmd_types]

        self.tlm_types = [
                (tt if (len(tt) == 2) else tt+[None])
                for tt in tlm_types]

        self.command_factory = CommandFactory(self.type_specs, 'little')
        self.formatter = Formatter(self.type_specs, 'little')

        self.commander = UDPCommander(self.host,self.cmd_port)
        rospy.loginfo('Sending commands to {}:{}'.format(self.host, self.cmd_port))
        self.listener = UDPListener('',self.tlm_port,self.type_specs)
        rospy.loginfo('Listening to telemetry on {}'.format(self.tlm_port))

        # create subscribers for command messages
        # topics are in the format '/MESSAGE_ID/COMMAND_CODE'

        self.cmd_subscribers = []
        for mid, cc, spec_name in self.cmd_types:
            mid_num = getattr(self.message_ids,mid)
            cc_num = getattr(self.command_codes,cc) if cc else 0

            if spec_name:
                msg_type = self.get_msg_type(spec_name)
                if msg_type is None:
                    rospy.logerr("Subscriber for message type {} failed to construct.".format(spec_name))
                    continue
                type_spec = getattr(self.type_specs,spec_name)
            else:
                msg_type = Empty
                type_spec = None

            topic_name = 'CMD/{}/{}'.format(mid,cc)

            rospy.loginfo('Creating subscriber for command MID: 0x{:04x} Topic: {}'.format(mid_num,topic_name))

            self.cmd_subscribers.append(
                    rospy.Subscriber(
                        topic_name,
                        msg_type,
                        partial(self.send_cmd,
                            mid_num,
                            cc_num,
                            type_spec)))

        self.tlm_publishers = []
        for mid, spec_name in self.tlm_types:
            if spec_name:
                msg_type = self.get_msg_type(spec_name)
                if msg_type is None:
                    rospy.logerr("Publisher for message type {} failed to construct.".format(spec_name))
                    continue
            else:
                msg_type = Empty

            topic_name = 'TLM/{}'.format(mid)

            rospy.loginfo('Creating publisher for telemetry topic: {}'.format(topic_name))

            pub = rospy.Publisher(
                        topic_name,
                        msg_type,
                        queue_size=10)

            self.tlm_publishers.append(pub)

            self.listener.listen(
                    getattr(self.message_ids,mid),
                    getattr(self.type_specs,spec_name),
                    partial(self.send_tlm,
                        getattr(self.message_ids,mid),
                        getattr(self.type_specs,spec_name),
                        pub))

        self.listener.start()

    def get_msg_type(self, spec_name):
        msg_module = importlib.import_module('{}.msg'.format(self.msg_package))
        try:
            msg_type = getattr(msg_module,spec_name)
        except AttributeError:
            rospy.logerr("Struct {} not found. Is it in your cfs_msgs/CMakeLists.txt?".format(spec_name))
            return None

        return msg_type

    def msg_to_cstruct(self, msg):
        """recursively create the CStruct from a message"""

        msg_name = type(msg).__name__.split('.')[-1]
        spec = getattr(self.type_specs,msg_name)

        cstruct = CStruct(spec)

        #print('msg_to_cstruct: {}'.format(type(msg).__name__.split('.')[-1]))

        for m_name, m_type, _ in spec.members:


            n_values = (
                    m_type.declarators[0][0]
                    if (len(m_type.declarators) > 0)
                    else 1)

            msg_member = getattr(msg,m_name)

            #print('  {} [{}] {}: {}'.format(m_type, n_values, m_name, msg_member))

            if m_type.type_spec in self.formatter.primitives:
                if n_values == 1 and m_type.type_spec != 'char':
                    val = msg_member
                else:
                    val = msg_member[0:min(len(msg_member),n_values)]
            else:
                if n_values == 1:
                    val = self.msg_to_cstruct(msg_member)
                else:
                    val = []
                    for i in range(min(len(msg_member),n_values)):
                        sub_val = self.msg_to_cstruct(msg_member[i])
                        val.append(sub_val)

            #print('  ----> {}'.format(val))

            cstruct.members[m_name] = val

        return cstruct

    def cstruct_to_msg(self, cstruct, msg_type):

        spec = cstruct.spec

        msg = msg_type()

        #print('cstruct_to_msg: {}'.format(type(msg).__name__.split('.')[-1]))

        for m_name, m_type, _ in spec.members:

            n_values = (
                    m_type.declarators[0][0]
                    if (len(m_type.declarators) > 0)
                    else 1)

            cstruct_member = getattr(cstruct,m_name,None)

            # print('  {} [{}] {}: {}'.format(m_type, n_values, m_name, cstruct_member))

            if m_type.type_spec in self.formatter.primitives:
                if n_values == 1:
                    val = cstruct_member
                else:
                    if m_type.type_spec == "char":
                        val = ''.join(cstruct_member[0:min(len(cstruct_member),n_values,cstruct_member.index("\0"))])
                    else:
                        val = cstruct_member[0:min(len(cstruct_member),n_values)]
            else:
                m_msg_type = self.get_msg_type(m_type.type_spec)
                if m_msg_type is None:
                    raise Exception("cstruct_to_msg failed to extract message type {}.".format(m_type.type_spec))

                if n_values == 1:
                    val = self.cstruct_to_msg(cstruct_member, m_msg_type)
                else:
                    val = []
                    for i in range(n_values):
                        sub_val = self.cstruct_to_msg(cstruct_member[i], m_msg_type)
                        val.append(sub_val)

            setattr(msg, m_name, val)

        return msg

    def send_cmd(self, mid_num, cc, spec, msg):
        rospy.logdebug('Received CMD: 0x{:04x}'.format(mid_num))
        if type(msg) != Empty:
            cstruct = self.msg_to_cstruct(msg)
            packed = self.command_factory.pack(mid_num, cc, cstruct)
        else:
            packed = self.command_factory.pack(mid_num, cc)

        #rospy.loginfo('  packed: {} bytes:\n{}'.format(len(packed),['%02x'%ord(x) for x in packed]))
        self.commander.send(packed)

    def send_tlm(self, mid, spec, pub, cstruct):
        rospy.logdebug('Received TLM: 0x{:04x}'.format(mid))
        if pub.data_class != Empty:
            msg = self.cstruct_to_msg(cstruct, pub.data_class)
        else:
            msg = Empty()

        pub.publish(msg)

    def shutdown(self):
        self.listener.shutdown()

def main():

    rospy.init_node('cfs_bridge')

    host_ip = rospy.get_param('~host_ip')
    cmd_types = rospy.get_param('~cmd_types')
    tlm_types = rospy.get_param('~tlm_types')

    bridge = CFSBridge(host_ip,1234,1235,cmd_types,tlm_types)

    rospy.on_shutdown(bridge.shutdown)

    rospy.spin()

if __name__ == '__main__':
    main()
