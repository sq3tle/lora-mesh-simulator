import json
from random import choice, randint

import simpy

from layer0.phy import PhysicalLayer, RadioEnvironment

class Path:
    def __init__(self, path):
        self.path = path

    def get_location(self,time):
        pass

class Transmission:
    def __init__(self, data, interval, lenght, destination):
        self.data = data
        self.interval = interval
        self.lenght = lenght
        self.destination = destination
        self.last_tx = None

class Device:
    env = None
    rf = None

    def __init__(self, name):

        if not self.env or not self.rf:
            raise Exception("Please specify simulation and rf environments")

        self.phy = PhysicalLayer(name, self.rf)
        self.transmissions = []
        self.path = None

        self.tx_power = 14

    def set_geo(self, geo):
        self.phy.geo = geo

    def update_device(self):
        pass

    def test_loop(self):
        yield self.env.process(self.phy.rx(randint(0, 1000)))
        while True:
            target = choice([x for x in ["alfa", "d13", "blonia"] if x != self.phy.id])
            payload = {"dest": target, "hops": [], "payload": "Test"}

            yield self.env.process(self.phy.tx(payload))
            received = yield self.env.process(self.phy.rx(randint(100, 3000)))

            if received:
                for packet in received:
                    if packet['payload']["dest"] != self.phy.id and len(packet['payload']["hops"]) < 1:
                        packet['payload']["hops"].append(self.phy.id)
                        yield self.env.process(self.phy.tx(packet['payload']))


# if __name__ == "__main__":
#
#
#     devices = [
#         Device("alfa", [(50.065607816004636, 19.9155651840895, 3)]),
#         Device("d13", [(50.070749606821, 19.90674912815427, 1.5)]),
#         Device("blonia", [(50.060667559992204, 19.909718523873615, 1.5)]),
#     ]
#
#     for device in devices:
#         Environment.env.process(device.test_loop())
#
#     Environment.env.run(until=30 * 1000)


Environment = Device  # for more clarity
Environment.env = simpy.Environment()
Environment.rf = RadioEnvironment(Environment.env)
devices = []

with open("input.json") as f_input:
    sim_setup = json.loads(f_input.read())

if sim_setup.get('settings', False):
    Environment.rf.SF = sim_setup['settings'].get('spreading_factor', 7)
    Environment.rf.BW = sim_setup['settings'].get('bandwidth', 0.125)
    Environment.rf.HEADER = sim_setup['settings'].get('phy_header_length', 11)
else:
    raise Exception('input json no settings section present')

if sim_setup.get('devices', False):
    for device in sim_setup.get('devices'):

        if device.get('id',False):
            new_device = Device(device.get('id'))
        else:
            raise Exception('input json no device name present in device definition')

        new_device.tx_power = device.get('tx_power')

        if device.get('path', False):
            path = device.get('path')
            if len(path) == 0:
                raise Exception('input json device path empty')
            device.path = Path(path)

        else:
            raise Exception('input json device no path section')

else:
    raise Exception('input json no devices section present')