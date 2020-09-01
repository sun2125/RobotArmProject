from lxml import etree
from enum import Enum
import asyncio
import queue
import numpy as np
from numpy import linalg as LA
import struct

PACKET_MAGIC_NUMBER = struct.pack('<i', 0x0001ba5e)
FLEX_GUI_NAMESPACE = {'ns': 'flex.gui'}
MIN_THRESHOLD = np.finfo(np.float32).eps
ACCESS_CODE_MAP = {
    'AcsToolTipPos': ("Generic", "SYSTEM!", 810),
    'AcsTcpSpeed': ("Generic", "SYSTEM!", 800),
    'AcsAxisEncode': ("Generic", "SYSTEM%", 200),
    'AcsAxisTheta': ("Generic", "SYSTEM!", 400),
    'AcsAxisSpeed': ("Generic", "SYSTEM!", 3041),
    'AcsAxisOrderSpped': ("Generic", "SYSTEM!", 3051),
    'AcsFixedIOPlayback': ("FixedIO", "FI", 8),
    'AcsServoMotorOnOff': ("Generic", "SYSTEM%", 171),
    'AcsFixedIOConfirmMotorsOn': ("FixedIO", "FI", 16),
    'AcsFixedIOStartDisplay1': ("FixedIO", "FO", 3),  # Yellow lamp "Running"
    'AcsFixedIOMotorsOnLAMP':
    ("FixedIO", "FO", 1),  # Fixed Output Motors-ON lamp
    'AcsStatusSavingEnergy': ("Generic", "SYSTEM%", 6),
    'AcsAxisAmpValue': ("Generic", "SYSTEM!", 3021),
    'AcsInterpolationKind': ("SPECIAL", "nInterpolation", 0)
}


class InterpolationType(Enum):
    joint = 0
    lin = 1
    cir1 = 2
    cir2 = 3


class XMLValueType(Enum):
    # value unimportant
    r = 0
    i = 1
    b = 2
    nil = 3
    unknown = -1


class MoveType(Enum):
    thru = 0
    positioning = 1
    end = 2


class XMLReplyType(Enum):
    # value unimportant
    data_update = 0
    data_update_ack = 1
    command_result = 2
    notification = 3
    unknown_reply = 4


class MonitorCycle(Enum):
    at5ms = 0
    at10ms = 1
    at50ms = 2
    at100ms = 3
    at200ms = 4
    at500ms = 5
    at1000ms = 6
    pull = 10


def get_numpy_type(value_type):
    if value_type == XMLValueType.r:
        return np.float32
    if value_type == XMLValueType.i:
        return np.int
    if value_type == XMLValueType.b:
        return np.bool
    raise ValueError


def create_flex_xml():
    return etree.Element('flexData', version='1', xmlns='flex.gui')


def set_request_properties(group, request_id, subid_base, mech_id):
    unit = 1
    mech_multiplier = -1
    count = -1
    unit_as_mech_id = False
    if (group == "SPECIAL"):
        if (request_id == "dTorque" and subid_base == 1
                or request_id == "dLifeSpan" and subid_base == 1):
            mech_multiplier = 1
            count = 6
        elif (request_id == "dAccuracy" and subid_base == 0
              or request_id == "nToolNr" and subid_base == 0
              or request_id == "nInterpolation" and subid_base == 0):
            mech_multiplier = 0
            unit_as_mech_id = True
            count = 1
    elif (group == "Generic"):
        if (request_id == "SYSTEM!"):
            if (subid_base == 3021 or  # AcsAxisAmpValue
                    subid_base == 3041 or  # AcsAxisSpeed
                    subid_base == 3051):  # AcsAxisOrderSpped
                mech_multiplier = 100
            if (subid_base == 900 or  # AcsAxisThetaOrder
                    subid_base == 810 or  # AcsToolTipPos
                    subid_base == 400 or  # AcsAxisTheta
                    subid_base == 310):  # AcsOrderToolTipPos
                mech_multiplier = 10
            if (subid_base == 800):  # AcsTcpSpeed
                mech_multiplier = 1
            count = 6
        elif (request_id == "SYSTEM%"):
            if (subid_base == 200):  # AcsAxisEncode
                mech_multiplier = 10
                count = 6
            if (subid_base == 171):  # AcsServoMotorOnOff
                mech_multiplier = 1
                count = 1
            if (subid_base == 6 or  # AcsStatusSavingEnergy
                    subid_base == 5):  # AcsStatusSlowPlayback
                mech_multiplier = 0
                count = 1
    elif (group == "FixedIO"):
        if (request_id == "FI" and subid_base == 8 or  # AcsFixedIOPlayback
                request_id == "FI" and subid_base == 16
                or  # AcsFixedIOConfirmMotorsOn
                request_id == "FO" and subid_base == 1
                or  # AcsFixedIOMotorsOnLAMP
                request_id == "FO"
                and subid_base == 3):  # AcsFixedIOStartDisplay1
            mech_multiplier = 0
            count = 1
    if (unit_as_mech_id):
        unit = mech_id
    return (unit, mech_multiplier, count)


def create_data_node(unit, group, request_id, subid, count, cycle, threshold):
    data_node = etree.Element("data")
    data_node.set("unit", str(unit))
    data_node.set("group", group)
    data_node.set("id", request_id)
    data_node.set("subid", str(subid))
    data_node.set("count", str(count))
    if (cycle == MonitorCycle.pull):
        data_node.set("push", "-1")
    else:
        data_node.set("push", "1")
    data_node.set("threshold", str(threshold))
    if (cycle == MonitorCycle.pull):
        data_node.set("priority", str(MonitorCycle.at500ms.value))
    else:
        data_node.set("priority", str(cycle.value))
    return data_node


def create_access_xml(group, request_id, subid_base, mech_id, cycle,
                      threshold):
    unit, mech_multiplier, count = set_request_properties(
        group, request_id, subid_base, mech_id)
    if (mech_multiplier < 0):
        print("invalid access")
        return ""

    subid = subid_base + (mech_id - 1) * mech_multiplier

    flex_node = create_flex_xml()

    exchange_node = etree.SubElement(flex_node, "dataExchange")
    request_node = etree.SubElement(exchange_node, "dataRequest")

    data_node = create_data_node(unit, group, request_id, subid, count, cycle,
                                 threshold)
    request_node.append(data_node)

    key = "unit:{};group:{};id:{};subid:{};count:{};".format(
        unit, group, request_id, subid, count)
    return (key, flex_node)


def create_update_xml(group, request_id, subid_base, mech_id, data, seqid):
    unit, mech_multiplier, count = set_request_properties(
        group, request_id, subid_base, mech_id)
    if (mech_multiplier < 0):
        print("invalid access")
        return ""
    subid = subid_base + (mech_id - 1) * mech_multiplier

    flex_node = create_flex_xml()
    exchange_node = etree.SubElement(flex_node, "dataExchange")
    update_node = etree.SubElement(exchange_node, "dataUpdate")
    update_node.set("seqid", str(seqid))
    data_node = etree.SubElement(update_node, "data")
    data_node.set("unit", str(unit))
    data_node.set("group", str(group))
    data_node.set("id", str(request_id))
    data_node.set("subid", str(subid))
    data_node.set("count", str(count))
    int_node = etree.SubElement(data_node, "i")
    int_node.text = str(data)
    key = "seqid:{};".format(seqid)
    return key, flex_node


def convert_xml_to_binary_string(element):
    return etree.tostring(element,
                          encoding='utf-8',
                          xml_declaration=True,
                          pretty_print=False).replace(b"\n", b"")


def create_payload(element):
    xml = convert_xml_to_binary_string(element)
    xml_length = struct.pack('<i', len(xml))
    return PACKET_MAGIC_NUMBER + xml_length + xml


def parse_xml_replies(raw_bytes):
    chunk_start = 0
    elements = []
    while (chunk_start < len(raw_bytes)):
        if (raw_bytes[chunk_start:chunk_start + 4] != PACKET_MAGIC_NUMBER):
            raise ValueError
        xml_length = int.from_bytes(raw_bytes[chunk_start + 4:chunk_start + 8],
                                    byteorder='little')
        elements += [
            etree.fromstring(raw_bytes[chunk_start + 8:chunk_start + 8 +
                                       xml_length])
        ]
        chunk_start += xml_length + 8
    return elements


def get_access_xml_key(element):
    data_node = element.xpath(
        "/ns:flexData/ns:dataExchange/ns:dataUpdate/ns:data",
        namespaces=FLEX_GUI_NAMESPACE)[0]
    unit = data_node.get("unit")
    group = data_node.get("group")
    request_id = data_node.get("id")
    subid = data_node.get("subid")
    count = int(data_node.get("count"))

    return "unit:{};group:{};id:{};subid:{};count:{};".format(
        unit, group, request_id, subid, count), data_node


def get_update_ack_xml_key(element):
    data_ack_node = element.xpath(
        "/ns:flexData/ns:dataExchange/ns:dataUpdateAck",
        namespaces=FLEX_GUI_NAMESPACE)[0]
    seqid = int(data_ack_node.get("seqid"))
    return "seqid:{};".format(seqid)


def get_command_result_xml_key(element):
    command_result_node = element.xpath(
        "/ns:flexData/ns:operations/ns:commandResult",
        namespaces=FLEX_GUI_NAMESPACE)[0]
    command_name = command_result_node.get("name")
    sequid = int(command_result_node.get("sequid"))
    return "command_name:{};sequid:{};".format(command_name, sequid)


def get_value_type(data_node):
    tagname = etree.QName(data_node[0]).localname
    if (tagname == XMLValueType.r.name):
        return XMLValueType.r
    if (tagname == XMLValueType.i.name):
        return XMLValueType.i
    if (tagname == XMLValueType.b.name):
        return XMLValueType.b
    return XMLValueType.unknown


def get_reply_type(element):
    if len(
            element.xpath("/ns:flexData/ns:dataExchange/ns:dataUpdate/ns:data",
                          namespaces=FLEX_GUI_NAMESPACE)) > 0:
        return XMLReplyType.data_update
    if len(
            element.xpath("/ns:flexData/ns:dataExchange/ns:dataUpdateAck",
                          namespaces=FLEX_GUI_NAMESPACE)) > 0:
        return XMLReplyType.data_update_ack
    if len(
            element.xpath("/ns:flexData/ns:operations/ns:commandResult",
                          namespaces=FLEX_GUI_NAMESPACE)) > 0:
        return XMLReplyType.command_result
    if len(
            element.xpath("/ns:flexData/ns:notifications/ns:note",
                          namespaces=FLEX_GUI_NAMESPACE)) > 0:
        return XMLReplyType.notification
    return XMLReplyType.unknown_reply


def parse_xml_value(data_node):
    value_type = get_value_type(data_node)
    strings = np.array(
        data_node.xpath("//ns:data/ns:{}/text()".format(value_type.name),
                        namespaces=FLEX_GUI_NAMESPACE))
    converted = strings.astype(get_numpy_type(value_type))
    return converted[0] if len(converted) == 1 else converted


def parse_xml_command_result(element):
    result_node = element.xpath(
        "/ns:flexData/ns:operations/ns:commandResult/ns:result",
        namespaces=FLEX_GUI_NAMESPACE)[0]
    result = int(result_node.text)
    result_text = element.xpath(
        "/ns:flexData/ns:operations/ns:commandResult/ns:resultText",
        namespaces=FLEX_GUI_NAMESPACE)[0].text
    return result, result_text


def parse_xml_notification(element):
    code_node = element.xpath("/ns:flexData/ns:notifications/ns:note/ns:code",
                              namespaces=FLEX_GUI_NAMESPACE)[0]
    code = int(code_node.text)

    mech_nodes = element.xpath("/ns:flexData/ns:notifications/ns:note/ns:mech",
                               namespaces=FLEX_GUI_NAMESPACE)
    if (len(mech_nodes) > 0):
        mech_id = int(mech_nodes[0].text)

    axis_nodes = element.xpath("/ns:flexData/ns:notifications/ns:note/ns:axis",
                               namespaces=FLEX_GUI_NAMESPACE)
    if (len(axis_nodes) > 0):
        axis = int(axis_nodes[0].text)

    line_nodes = element.xpath("/ns:flexData/ns:notifications/ns:note/ns:line",
                               namespaces=FLEX_GUI_NAMESPACE)
    if (len(line_nodes) > 0):
        line = int(line_nodes[0].text)

    program_nodes = element.xpath(
        "/ns:flexData/ns:notifications/ns:note/ns:program",
        namespaces=FLEX_GUI_NAMESPACE)
    if (len(program_nodes) > 0):
        program = program_nodes[0].text

    message = element.xpath("/ns:flexData/ns:notifications/ns:note/ns:message",
                            namespaces=FLEX_GUI_NAMESPACE)[0].text

    content = element.xpath("/ns:flexData/ns:notifications/ns:note/ns:content",
                            namespaces=FLEX_GUI_NAMESPACE)[0].text
    measures = element.xpath(
        "/ns:flexData/ns:notifications/ns:note/ns:measures",
        namespaces=FLEX_GUI_NAMESPACE)[0].text
    return {
        'unit': unit,
        'mech_id': mech_id,
        'axis': axis,
        'line': line,
        'program': program,
        'message': message,
        'content': content,
        'measures': measures
    }


class ClientProtocol(asyncio.Protocol):
    def __init__(self, pull_map):
        self.pull_map = pull_map

    def connection_made(self, transport):
        print('connection made')

    def data_received(self, data):
        print("data received")
        elements = parse_xml_replies(data)
        for element in elements:
            reply_type = get_reply_type(element)
            if reply_type == XMLReplyType.data_update:
                key, data_node = get_access_xml_key(element)
                fut = self.pull_map[key].get()
                fut.set_result(parse_xml_value(data_node))
            elif reply_type == XMLReplyType.data_update_ack:
                key = get_update_ack_xml_key(element)
                fut = self.pull_map[key].get()
                fut.set_result(None)
            elif reply_type == XMLReplyType.command_result:
                print('command result received')
                key = get_command_result_xml_key(element)
                print('key = ' + key)
                fut = self.pull_map[key].get()
                result, result_text = parse_xml_command_result(element)
                if result == 1:
                    fut.set_result((result, result_text))
                else:
                    fut.set_exception(RuntimeError)
            elif reply_type == XMLReplyType.notification:
                print(parse_xml_notification(element))

    def connection_lost(self, exc):
        print('Connection lost')


class Controller(object):
    @classmethod
    async def create(cls, ip, port=9876):
        self = cls()
        self.pull_map = {}
        loop = asyncio.get_running_loop()
        self.ip = ip
        self.port = port
        self.sequid = 0
        self.seqid = 0
        self.transport, self.protocol = await loop.create_connection(
            lambda: ClientProtocol(self.pull_map), ip, port)
        return self

    def close(self):
        if not self.transport.is_closing():
            print("close transport")
            self.transport.close()

    def add_future_to_pull_map(self, key):
        loop = asyncio.get_running_loop()
        if key not in self.pull_map:
            self.pull_map[key] = queue.Queue()
        fut = loop.create_future()
        self.pull_map[key].put(fut)
        return fut

    async def send_and_wait_reply(self, key, flex_node, timeout):
        fut = self.add_future_to_pull_map(key)
        self.transport.write(create_payload(flex_node))
        return await asyncio.wait_for(fut, timeout=timeout)

    async def access(self, group, request_id, subid, mech_id=1, timeout=5.0):
        key, flex_node = create_access_xml(group, request_id, subid, mech_id,
                                           MonitorCycle.pull, 0.01)
        return await self.send_and_wait_reply(key, flex_node, timeout)

    async def write(self,
                    group,
                    request_id,
                    subid,
                    data,
                    mech_id=1,
                    timeout=5.0):
        key, flex_node = create_update_xml(group, request_id, subid, mech_id,
                                           data, self.seqid)
        return await self.send_and_wait_reply(key, flex_node, timeout)

    async def get_position(self, mech_id=1, timeout=5.0):
        return await self.access(*ACCESS_CODE_MAP["AcsToolTipPos"],
                                 mech_id,
                                 timeout=timeout)

    async def get_velocity(self, mech_id=1, timeout=5.0):
        return await self.access(*ACCESS_CODE_MAP["AcsTcpSpeed"],
                                 mech_id,
                                 timeout=timeout)

    async def get_joint_angle_encoded(self, mech_id=1, timeout=5.0):
        return await self.access(*ACCESS_CODE_MAP["AcsAxisEncode"],
                                 mech_id,
                                 timeout=timeout)

    async def get_joint_angle(self, mech_id=1, timeout=5.0):
        return await self.access(*ACCESS_CODE_MAP["AcsAxisTheta"],
                                 mech_id,
                                 timeout=timeout)

    async def get_joint_velocity(self, mech_id=1, timeout=5.0):
        return await self.access(*ACCESS_CODE_MAP["AcsAxisSpeed"],
                                 mech_id,
                                 timeout=timeout)

    async def get_joint_target_velocity(self, mech_id=1, timeout=5.0):
        return await self.access(*ACCESS_CODE_MAP["AcsAxisOrderSpeed"],
                                 mech_id,
                                 timeout=timeout)

    async def get_playback_mode(self, mech_id=1, timeout=5.0):
        return await self.access(*ACCESS_CODE_MAP["AcsFixedIOPlayback"],
                                 mech_id,
                                 timeout=timeout)

    async def get_motor_power_on(self, mech_id=1, timeout=5.0):
        return await self.access(*ACCESS_CODE_MAP["AcsServoMotorOnOff"],
                                 mech_id,
                                 timeout=timeout)

    async def get_motor_ready(self, mech_id=1, timeout=5.0):
        return await self.access(*ACCESS_CODE_MAP["AcsFixedIOConfirmMotorsOn"],
                                 mech_id,
                                 timeout=timeout)

    async def get_motor_launched(self, mech_id=1, timeout=5.0):
        return await self.access(*ACCESS_CODE_MAP["AcsFixedIOStartDisplay1"],
                                 mech_id,
                                 timeout=timeout)

    async def get_motor_lamp(self, mech_id=1, timeout=5.0):
        return await self.access(*ACCESS_CODE_MAP["AcsFixedIOMotorsOnLAMP"],
                                 mech_id,
                                 timeout=timeout)

    async def get_energy_saving(self, mech_id=1, timeout=5.0):
        return await self.access(*ACCESS_CODE_MAP["AcsStatusSavingEnergy"],
                                 mech_id,
                                 timeout=timeout)

    async def get_joint_quadrature_current(self, mech_id=1, timeout=5.0):
        return await self.access(*ACCESS_CODE_MAP["AcsAxisAmpValue"],
                                 mech_id,
                                 timeout=timeout)

    async def get_interpolation_type(self, mech_id=1, timeout=5.0):
        return InterpolationType(
            await self.access(*ACCESS_CODE_MAP["AcsInterpolationKind"],
                              mech_id,
                              timeout=timeout))

    async def set_interpolation_type(self,
                                     interpolation_type,
                                     mech_id=1,
                                     timeout=5.0):
        return await self.write(*ACCESS_CODE_MAP["AcsInterpolationKind"],
                                interpolation_type.value,
                                mech_id,
                                timeout=timeout)

    async def monitor(self, group, request_id, subid, callback, mech_id, cycle,
                      threshold):
        print("in monitor, subid = {}".format(subid))
        key, flex_node = create_access_xml(group, request_id, subid, mech_id,
                                           cycle, threshold)
        return await MonitorController.create(self.ip, self.port, key,
                                              flex_node, callback)

    async def notify(self,
                     group,
                     request_id,
                     subid,
                     condition,
                     mech_id,
                     cycle,
                     threshold,
                     timeout=None):
        # value that does not change cannot be obtained by push
        data = await self.access(group,
                                 request_id,
                                 subid,
                                 mech_id,
                                 timeout=5.0 if timeout is None else timeout)
        if (condition(data)):
            return data

        loop = asyncio.get_running_loop()
        fut = loop.create_future()

        def close_upon_condition(data):
            nonlocal condition
            nonlocal fut
            if (condition(data)):
                fut.set_result(data)

        monitor = await self.monitor(group, request_id, subid,
                                     close_upon_condition, mech_id, cycle,
                                     threshold)
        data = await asyncio.wait_for(fut, timeout=timeout)
        monitor.close()
        return data

    async def notify_motor_ready(self,
                                 target,
                                 mech_id=1,
                                 cycle=MonitorCycle.at5ms,
                                 threshold=MIN_THRESHOLD,
                                 timeout=None):
        return await self.notify(*ACCESS_CODE_MAP["AcsFixedIOConfirmMotorsOn"],
                                 lambda v: v == target, mech_id, cycle,
                                 threshold, timeout)

    async def notify_motor_launched(self,
                                    target,
                                    mech_id=1,
                                    cycle=MonitorCycle.at5ms,
                                    threshold=MIN_THRESHOLD,
                                    timeout=None):
        return await self.notify(*ACCESS_CODE_MAP["AcsFixedIOStartDisplay1"],
                                 lambda v: v == target, mech_id, cycle,
                                 threshold, timeout)

    async def notify_motor_lamp(self,
                                target,
                                mech_id=1,
                                cycle=MonitorCycle.at5ms,
                                threshold=MIN_THRESHOLD,
                                timeout=None):
        return await self.notify(*ACCESS_CODE_MAP["AcsFixedIOMotorsOnLAMP"],
                                 lambda v: v == target, mech_id, cycle,
                                 threshold, timeout)

    async def notify_joint_angle(self,
                                 condition,
                                 mech_id=1,
                                 cycle=MonitorCycle.at5ms,
                                 threshold=MIN_THRESHOLD,
                                 timeout=None):
        return await self.notify(*ACCESS_CODE_MAP["AcsAxisTheta"], condition,
                                 mech_id, cycle, threshold, timeout)

    async def notify_joint_angle_velocity(self,
                                          condition,
                                          mech_id=1,
                                          cycle=MonitorCycle.at5ms,
                                          threshold=MIN_THRESHOLD,
                                          timeout=None):
        return await self.notify(*ACCESS_CODE_MAP["AcsAxisSpeed"], condition,
                                 mech_id, cycle, threshold, timeout)

    async def notify_joint_quadrature_current(self,
                                              condition,
                                              mech_id=1,
                                              cycle=MonitorCycle.at5ms,
                                              threshold=MIN_THRESHOLD,
                                              timeout=None):
        return await self.notify(*ACCESS_CODE_MAP["AcsAxisAmpValue"],
                                 condition, mech_id, cycle, threshold, timeout)

    def create_command_xml(self, command_name, params=None):
        flex_node = create_flex_xml()
        operations_node = etree.SubElement(flex_node, "operations")
        command_node = etree.SubElement(operations_node, "command")
        command_node.set("sequid", str(self.sequid))
        command_node.set("name", command_name)
        if params is not None:
            for (param_name, param_value) in params:
                param_node = etree.SubElement(command_node,
                                              "param",
                                              name=param_name)
                if (param_value is not None):
                    param_node.text = str(param_value)
        key = "command_name:{};sequid:{};".format(command_name, self.sequid)
        self.sequid += 1
        return (key, flex_node)

    async def move(self, v, command_name, move_type, timeout=5.0):
        params = []
        if (command_name == "MoveXR" or command_name == "MoveX"):
            params.append(('X', v[0]))
            params.append(('Y', v[1]))
            params.append(('Z', v[2]))
            params.append(('r', v[3]))
            params.append(('p', v[4]))
            params.append(('y', v[5]))
            params.append(('conf', 0))
        else:
            params.append(('angle1', v[0]))
            params.append(('angle2', v[1]))
            params.append(('angle3', v[2]))
            params.append(('angle4', v[3]))
            params.append(('angle5', v[4]))
            params.append(('angle6', v[5]))
        if (move_type != MoveType.thru):
            params.append(
                ("PAUSE" if move_type == MoveType.positioning else "END",
                 None))
        key, flex_node = self.create_command_xml(command_name, params)
        return await self.send_and_wait_reply(key, flex_node, timeout)

    async def move_by(self, shift, move_type, timeout=5.0):
        return await self.move(shift, "MoveXR", move_type, timeout)

    async def move_to(self, x, move_type, timeout=5.0):
        return await self.move(x, "MoveX", move_type, timeout)

    async def angulate_by(self, angles, move_type, timeout=5.0):
        return await self.move(angles, "MoveJA", move_type, timeout)

    async def angulate_to(self, angles, move_type, timeout=5.0):
        return await self.move(angles, "MoveJ", move_type, timeout)

    async def start_motor(self, timeout=5.0):
        key, flex_node = self.create_command_xml("selectMotorOn", [('on', 1)])
        await self.send_and_wait_reply(key, flex_node, timeout)
        await asyncio.sleep(0.05)  # sleep to send ACK
        key, flex_node = self.create_command_xml("selectMotorOn", [('on', 0)])
        return await self.send_and_wait_reply(key, flex_node, timeout)

    async def start_motor_until_current_ready(self,
                                              l1norm_threshold=0.7,
                                              cycle=MonitorCycle.at5ms,
                                              threshold=MIN_THRESHOLD,
                                              timeout=5.0):
        if (await self.get_motor_ready(timeout=timeout)):
            return
        await self.start_motor(timeout=timeout)
        return await self.notify_joint_quadrature_current(
            lambda current: LA.norm(current, 1) > l1norm_threshold,
            cycle=cycle,
            threshold=threshold,
            timeout=timeout)

    async def stop_motor(self, timeout=5.0):
        key, flex_node = self.create_command_xml("selectMotorOff")
        return await self.send_and_wait_reply(key, flex_node, timeout)

    async def stop_motor_until_current_drains(self,
                                              l1norm_threshold=0.1,
                                              cycle=MonitorCycle.at5ms,
                                              threshold=MIN_THRESHOLD,
                                              timeout=5.0):
        if (not await self.get_motor_ready(timeout=timeout)):
            return
        await self.stop_motor(timeout=timeout)
        return await self.notify_joint_quadrature_current(
            lambda current: LA.norm(current, 1) < l1norm_threshold,
            cycle=cycle,
            threshold=threshold,
            timeout=timeout)


class MonitorClientProtocol(asyncio.Protocol):
    def __init__(self, key, callback):
        self.key = key
        self.callback = callback

    def connection_made(self, transport):
        print('connection made for monitor')

    def data_received(self, data):
        print("data received")
        elements = parse_xml_replies(data)
        for element in elements:
            if (get_reply_type(element) != XMLReplyType.data_update):
                continue
            key, data_node = get_access_xml_key(element)
            if key != self.key:
                continue
            self.callback(parse_xml_value(data_node))

    def connection_lost(self, exc):
        print('Connection for monitor lost')


class MonitorController(object):
    @classmethod
    async def create(cls, ip, port, key, flex_node, callback):
        self = cls()
        loop = asyncio.get_running_loop()
        self.transport, self.protocol = await loop.create_connection(
            lambda: MonitorClientProtocol(key, callback), ip, port)
        self.transport.write(create_payload(flex_node))
        return self

    def close(self):
        self.transport.close()
