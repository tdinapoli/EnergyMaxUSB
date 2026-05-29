import logging
from typing import Literal

from pyvisa.resources import MessageBasedResource

logger = logging.getLogger(__name__)

MeasureType = Literal["DEFAULT", "J", "W"]
TriggerSource = Literal["DEFAULT", "INTERNAL", "EXTERNAL"]
TriggerSlope = Literal["DEFAULT", "POSITIVE", "NEGATIVE"]


class EnergyMaxUSB:
    # pm1 model: "EM-USB J-10MB-HE"
    # pm1 serial: "0344D22R"
    def __init__(self, em: MessageBasedResource, model: str, serial: str) -> None:
        self.em = em

        self.model = self.em.query("SYSTEM:INFORMATION:MODEL?")
        assert self.model == model
        self.serial = self.em.query("SYSTEM:INFORMATION:SNUMBER?")
        assert self.em.query("*IDN?") == serial

        self._min_wl = int(self.em.query("CONFIGURE:WAVELENGTH? MINIMUM"))
        self._max_wl = int(self.em.query("CONFIGURE:WAVELENGTH? MAXIMUM"))
        self._current_wl = self.em.query("CONFIGURE:WAVELENGTH?")
        self.set_measure_type("J")

    def parse_read(self, response: str) -> float:
        # TODO: implement this
        return response

    def read(self) -> float | None:
        resp = self.em.query("READ?")
        if self.query_succeded(resp, "read measurement"):
            logger.info("Reading measurment with value {resp}")
            return self.parse_read(resp)

    def set_measure_type(self, typ: MeasureType):
        resp = self.em.query(f"CONFIGURE:MEASURE:TYPE {typ}")
        if self.query_succeded(resp, "set measure type"):
            logger.info("Setting measure type to {typ}")
            return resp
        return resp

    def get_measure_type(self) -> str:
        resp = self.em.query("CONFIGURE:MEASURE:TYPE?")
        if self.query_succeded(resp, "get measure type"):
            logger.info("Getting measure type")
            return resp
        return resp

    def set_trigger_source(self, source: TriggerSource):
        resp = self.em.query(f"TRIGGER:SOURCE {source}")
        if self.query_succeded(resp, "set trigger source"):
            logger.info(f"Setting trigger source to {source}")
            return
        return resp

    def get_trigger_source(self):
        resp = self.em.query("TRIGGER:SOURCE?")
        if self.query_succeded(resp, "set trigger source"):
            logger.info("Getting trigger source")
            return resp
        return resp

    def set_trigger_slope(self, slope: TriggerSlope):
        resp = self.em.query(f"TRIGGER:SLOPE {slope}")
        if self.query_succeded(resp, "set trigger slope"):
            logger.info(f"Setting trigger slope to {slope}")
            return
        return resp

    def get_trigger_slope(self):
        resp = self.em.query("TRIGGER:SLOPE?")
        if self.query_succeded(resp, "set trigger slope"):
            logger.info("Getting trigger slope")
            return resp
        return resp

    def set_wavelength(self, wl: float):
        assert self.min_wl <= wl <= self.max_wl
        resp = self.em.query(f"CONFIGURE:WAVELENGTH {wl}")
        if self.query_succeded(resp, "set wavelength"):
            logger.info(f"Setting wavelength to {wl}")
            return
        return resp

    def get_wavelength(self):
        resp = self.em.query("CONFIGURE:WAVELENGTH?")
        if self.query_succeded(resp, "get wavelength"):
            logger.info("Getting wavelength")
            return
        return resp

    def set_trigger_delay(self, delay: int):
        assert 0 <= delay <= 1000
        resp = self.em.query(f"TRIGGER:DELAY {delay}")
        if self.query_succeded(resp, "set trigger delay"):
            logger.info(f"Setting trigger delay to {delay}")
            return
        return resp

    def get_trigger_delay(self):
        resp = self.em.query("TRIGGER:DELAY?")
        if self.query_succeded(resp, "set trigger delay"):
            logger.info("Getting trigger delay")
            return resp
        return resp

    @property
    def min_wl(self):
        return self._min_wl

    @property
    def max_wl(self):
        return self._max_wl

    @property
    def current_wl(self):
        return self._current_wl

    def query_succeded(self, response: str, method_string: str) -> bool:
        if response != "OK":
            logger.error(f"Failed to {method_string} with response {response}")
            return False
        return True
