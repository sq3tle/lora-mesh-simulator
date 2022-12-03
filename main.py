from random import choice, randint
import simpy
from layer0.phy import PhysicalLayer, RadioEnvironment

class Device:
    env = None
    rf = None

    def __init__(self, name, geo=None):

        if not self.env or not self.rf:
            raise Exception("Please specify simulation and rf environments")

        self.phy = PhysicalLayer(name, (0, 0, 0) if not geo else geo[0], self.env, self.rf)
        self.messages2tx = []
        self.path = []
        self.tx_power = 14

    def set_geo(self, geo):
        self.phy.geo = geo

    def update_device(self):
        pass

    def test_loop(self):
        yield self.env.process(self.phy._rx(randint(0, 1000)))
        while True:
            target = choice([x for x in ["alfa", "d13", "blonia"] if x != self.phy.name])
            payload = {"dest": target, "hops": [], "payload": "Test"}

            yield self.env.process(self.phy._tx(payload))
            received = yield self.env.process(self.phy._rx(randint(100, 3000)))

            if received:
                for packet in received:
                    if packet['payload']["dest"] != self.phy.name and len(packet['payload']["hops"]) < 1:
                        packet['payload']["hops"].append(self.phy.name)
                        yield self.env.process(self.phy._tx(packet['payload']))


if __name__ == "__main__":
    Environment = Device  # for more clarity
    Environment.env = simpy.Environment()

    Environment.rf = RadioEnvironment(Environment.env)
    Environment.rf.SF = 8
    Environment.rf.TXPWR = 14

    devices = [
        Device("alfa", [(50.065607816004636, 19.9155651840895, 3)]),
        Device("d13", [(50.070749606821, 19.90674912815427, 1.5)]),
        Device("blonia", [(50.060667559992204, 19.909718523873615, 1.5)]),
    ]

    for device in devices:
        Environment.env.process(device.test_loop())

    Environment.env.run(until=30 * 1000)
