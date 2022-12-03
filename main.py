import json
from random import choice, randint

import simpy
from scipy import interpolate

from layer0.phy import PhysicalLayer, RadioEnvironment


class Path:
    def __init__(self, path):
        self.path = path

        if len(path) < 2:
            self.path.extend(path)

        time = [p['time'] for p in path]
        lat = [p['lat'] for p in path]
        lon = [p['lon'] for p in path]
        alt = [p['alt'] for p in path]

        self.lat = interpolate.interp1d(time, lat, fill_value=(lat[0], lat[-1]), bounds_error=False)
        self.lon = interpolate.interp1d(time, lon, fill_value=(lon[0], lon[-1]), bounds_error=False)
        self.alt = interpolate.interp1d(time, alt, fill_value=(alt[0], alt[-1]), bounds_error=False)

    def get_location(self, time):
        return self.lat(time), self.lon(time), self.alt(time)


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

        self.phy = PhysicalLayer(name, self.env, self.rf)
        self.transmissions = []
        self.path = None

        self.tx_power = 14

    def update_device(self):
        pass

    def test_loop(self):
        self.phy.geo = self.path.get_location(self.env.now)
        yield self.env.process(self.phy.rx(randint(0, 1000)))
        while True:
            self.phy.geo = self.path.get_location(self.env.now)
            target = choice([x for x in ["alfa", "d13", "blonia"] if x != self.phy.id])
            payload = {"from": self.phy.id, "dest": target,
                       "hops": [], "payload": "Test"}

            yield self.env.process(self.phy.tx(payload))
            received = yield self.env.process(self.phy.rx(randint(1000, 4000)))

            if received:
                for packet in received:
                    if packet['payload']["dest"] != self.phy.id and len(packet['payload']["hops"]) < 1:
                        packet['payload']["hops"].append(self.phy.id)
                        yield self.env.process(self.phy.tx(packet['payload']))



def parse_input(environment, filename):
    devices = []
    with open(filename) as f_input:
        sim_setup = json.loads(f_input.read())

    if sim_setup.get('settings', False):
        environment.rf.SF = sim_setup['settings'].get('spreading_factor', 7)
        environment.rf.BW = sim_setup['settings'].get('bandwidth', 0.125)
        environment.rf.HEADER = sim_setup['settings'].get('phy_header_length', 11)
    else:
        raise Exception('input json no settings section present')

    if sim_setup.get('devices', False):
        for device in sim_setup.get('devices'):

            if device.get('id', False):
                new_device = Device(device.get('id'))
            else:
                raise Exception('input json no device name present in device definition')

            new_device.tx_power = device.get('tx_power', 14)

            if device.get('path', False):
                path = device.get('path')
                if len(path) == 0:
                    raise Exception('input json device path empty')
                new_device.path = Path(path)
            else:
                raise Exception('input json device no path section')

            if device.get('transmissions', False):
                transmissions = device.get('transmissions')
                if len(transmissions) == 0:
                    raise Exception('input json device transmissions list empty')
                for transmission in transmissions:
                    new_device.transmissions.append(
                        Transmission(transmission.get('data', ''), transmission.get('interval', 1000),
                                     transmission.get('lenght', 0), transmission.get('destination', 'all'))
                    )

            else:
                raise Exception('input json device no transmissions section')

            devices.append(new_device)

    else:
        raise Exception('input json no devices section present')

    return devices


if __name__ == "__main__":
    Environment = Device  # for more clarity
    Environment.env = simpy.Environment()
    Environment.rf = RadioEnvironment(Environment.env)

    devices = parse_input(Environment, "input.json")
    for device in devices:
        Environment.env.process(device.test_loop())

    Environment.env.run(until=10 * 1000)
