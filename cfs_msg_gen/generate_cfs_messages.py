#!/usr/bin/env python

from __future__ import print_function

import os
import sys
import glob
import argparse
import fnmatch
import re

from IPython import embed

import pycfs

from pycfs.serialization import CStruct,CommandFactory,TelemetryFactory
from pycfs.commander import UDPCommander
from pycfs.listener import UDPListener

def main():

    parser = argparse.ArgumentParser(description="cFS Shell")
    parser.add_argument('-p','--path',metavar='BUNDLE_PATH',type=str,
            default=None,
            help="The path to the cFS bundle. (default: cwd)")
    parser.add_argument('-m','--mission',metavar='MISSION',type=str,
            default=None,
            help="The mission name (default: $MISSIONCONFIG)")
    parser.add_argument('-t','--target',metavar='TARGET',type=str,
            default=None,
            help="The path to the desired target. (default: none)")
    parser.add_argument('-n','--no-cache',action='store_true',
            help="Disable use of the cache.")
    parser.add_argument('-a','--apps',metavar='APP',type=str,nargs='+',
            help="The name of an app to get messages from.")

    parser.add_argument('-o','--output',metavar='OUTPUT_PATH',type=str,
            default=os.getcwd(),
            help="The path to the ROS msg output directory. (default: cwd)")

    parser.add_argument('-s','--structs',metavar='STRUCT',type=str,nargs='+',
            help="The name of the C structs from which messages should be generated.")

    parser.add_argument('-c','--constants',metavar='CONST',type=str,nargs='*',
            help="The name of the C constants (#define) which should be added to the message package.")

    parser.add_argument('-g','--globs',metavar='PATTERN',type=str,nargs='+',
            help="A list of glob patterns to use for structs and constants.")

    args = parser.parse_args()

    MID,CC,MSG,cparser = pycfs.load_bundle(args.path, args.mission,
            args.target, args.apps, use_cache=(not args.no_cache))

    # map ROS primitives to C primitives
    primitive_inverse_map = {
            'bool':    ['bool',    '_Bool'],
            'int8':    ['int8',    'int8_t'],
            'uint8':   ['uint8',   'uint8_t'],
            'int16':   ['int16',   'int16_t'],
            'uint16':  ['uint16',  'uint16_t'],
            'int32':   ['int32',   'int32_t'],
            'uint32':  ['uint32',  'uint32_t'],
            'int64':   ['int64',   'int64_t'],
            'uint64':  ['uint64',  'uint64_t'],
            'float32': ['float'],
            'float64': ['double'],
            'string':  ['char'] }


    # map c primitives to ros primitives
    primitive_map = dict()
    for ros_type, c_types in primitive_inverse_map.items():
        for c_type in c_types:
            primitive_map[c_type] = ros_type

    for k,v in primitive_map.items():
        print('{}: {}'.format(k,v))

    # process messages
    msg_queue = list(args.structs)
    processed_msgs = set()
    while len(msg_queue) > 0:

        msg_typename = msg_queue.pop(0)
        processed_msgs.add(msg_typename)

        print('Generating message for {}'.format(msg_typename))

        # initialize message file text
        msg_str = '# ROS Message definition for C type "{}"\n# DO NOT EDIT: Auto-generated from cfs headers.\n'.format(msg_typename)

        # skip if this message is an alias for a primitive type
        msg_def = getattr(MSG,msg_typename)
        if type(msg_def) is unicode and msg_def in primitive_map:
            continue

        # process one member at a time
        for member_name, member_spec, _ in msg_def.members:
            member_typename = member_spec.type_spec

            # resolve aliased types
            while type(getattr(MSG,member_typename,None)) is unicode:
                member_typename = getattr(MSG,member_typename)

            # get the primitive type if this is a primitive type
            member_ros_typename = primitive_map.get(member_typename,member_typename)

            # determine if this is an array type
            # TODO: support multi-dimensional arrays
            if member_ros_typename == 'string':
                member_multiplicity = 1
            else:
                member_multiplicity = member_spec.declarators[0][0] if (len(member_spec.declarators) > 0) else 1

            # add the line for this member
            msg_str += '{}{} {}\n'.format(
                    member_ros_typename,
                    '[]' if member_multiplicity > 1 else '',
                    member_name)

            # add this member type if it needs to be processed
            if (member_typename not in primitive_map
                    and member_typename not in msg_queue
                    and member_typename not in processed_msgs):
                print(' - Enqueuing type {}'.format(member_typename))
                msg_queue.append(member_typename)

        # write the message file out
        with open('{}.msg'.format(os.path.join(args.output,msg_typename)),'w') as msg_file:
            msg_file.write(msg_str)

    # create a message to contain constants

    filters = [re.compile(fnmatch.translate(glob)) for glob in args.globs]

    constants = [const_name
            for const_name in cparser.defs['values'].keys()
            if any([f.match(const_name) for f in filters])]

    constants += args.constants
    constants_msg_str = '# ROS Message constants\n# DO NOT EDIT: Auto-generated from cfs headers.\n'

    for const_name in sorted(constants):
        const_val = cparser.defs['values'][const_name]

        if const_val == None:
            continue

        if const_val == int(const_val):
            constants_msg_str += 'int64 {}={}\n'.format(const_name, const_val)
        elif const_val == float(const_val):
            constants_msg_str += 'double {}={}\n'.format(const_name, const_val)
        elif const_val == str(const_val):
            constants_msg_str += 'string {}={}\n'.format(const_name, const_val)

    with open('{}.msg'.format(os.path.join(args.output,'Constants')),'w') as msg_file:
        msg_file.write(constants_msg_str)


if __name__ == '__main__':
    main()
