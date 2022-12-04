import json
from random import randint

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
    out = None

    def __init__(self, name):

        if not self.env or not self.rf:
            raise Exception("Please specify simulation and rf environments")

        self.phy = PhysicalLayer(name, self.env, self.rf, self.out)
        self.transmissions = []
        self.path = None
        self.neighbors = None
        self.tx_power = 14

    def update_device(self):
        while 1:
            if self.neighbors:
                self.neighbors = list(filter(lambda x: x['last_heard'] > self.env.now + 5000, self.neighbors))
            self.phy.geo = self.path.get_location(self.env.now)

            self.out.add_device(self.env.now, {
                "name": self.phy.id,
                "lat": float(self.phy.geo[0]),
                "lon": float(self.phy.geo[1]),
                "alt": float(self.phy.geo[2]),
            })

            yield self.env.timeout(1)

    def test_loop(self):
        self.env.process(self.update_device())
        while True:
            if self.transmissions:
                payload = {"from": self.phy.id, "dest": "d13",
                           "hops": [], "payload": "Ping"}

                yield self.env.process(self.phy.tx(payload))
                yield self.env.timeout(1000)
            received = yield self.env.process(self.phy.rx_one(randint(1000, 4000)))

            if received:
                for packet in received:
                    if packet['payload']["dest"] == self.phy.id:
                        payload = {"from": self.phy.id, "dest": packet['payload']["from"],
                                   "hops": [], "payload": "Pong"}
                        yield self.env.process(self.phy.tx(payload))

                    elif packet['payload']["dest"] != self.phy.id and len(packet['payload']["hops"]) < 1:
                        packet['payload']["hops"].append(self.phy.id)
                        yield self.env.process(self.phy.tx(packet['payload']))


class DataInterface:
    def __init__(self, filename):
        self.filename = filename
        self.data = []
        self.last_chunk_end = 0
        self.last_chunk = 0

    def add_packet(self, time, data, lenght):
        chunk_time = time - self.last_chunk_end
        self._extend(chunk_time)

        if not self.data[chunk_time - lenght].get('packets', False):
            self.data[chunk_time - lenght]['packets'] = []

        self.data[chunk_time - lenght]['packets'].append(data)

    def add_link(self, time, data):
        chunk_time = time - self.last_chunk_end
        self._extend(chunk_time)

        if not self.data[chunk_time].get('links', False):
            self.data[chunk_time]['links'] = []

        self.data[chunk_time]['links'].append(data)

    def add_device(self, time, data):
        chunk_time = time - self.last_chunk_end
        self._extend(chunk_time)

        if not self.data[chunk_time].get('devices', False):
            self.data[chunk_time]['devices'] = []

        self.data[chunk_time]['devices'].append(data)

    def commit(self):

        last = None
        self.last_chunk_end += len(self.data)
        self.last_chunk += 1

        for step in self.data.copy():
            now = self._datastr(step)
            if last == now:
                self.data.remove(step)
                continue
            last = now

        with open("{}_{}.json".format(self.filename, self.last_chunk), "w") as f:
            f.write(json.dumps(self.data, indent=2))
        self.data = []

    def _extend(self, time):
        for i in range(len(self.data), time + 1):
            self.data.append({"time": i + self.last_chunk_end})

    def _datastr(self, json):
        return "{} {} {}".format(json.get('packets', ''), json.get('devices', ''), json.get('links', ''))

    @staticmethod
    def parse_input(environment, filename):
        devices = []
        with open(filename, "r") as f_input:
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
                    if len(transmissions) != 0:
                        for transmission in transmissions:
                            new_device.transmissions.append(
                                Transmission(transmission.get('data', ''), transmission.get('interval', 1000),
                                             transmission.get('lenght', 0), transmission.get('destination', 'all'))
                            )

                devices.append(new_device)

        else:
            raise Exception('input json no devices section present')

        return devices


def basic_use(input, output):
    Environment = Device  # for more clarity
    Environment.env = simpy.Environment()
    Environment.rf = RadioEnvironment(Environment.env)
    Environment.out = DataInterface(output)

    devices = DataInterface.parse_input(Environment, input)
    for device in devices:
        Environment.env.process(device.test_loop())

    for i in range(1, 2 + 1):
        Environment.env.run(until=30000 * i)
        Environment.out.commit()


if __name__ == "__main__":
    basic_use("example_static_3devices_ping.json", "example")
