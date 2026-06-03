import logging
from typing import Literal, Optional, TypedDict

import pyvisa
from pyvisa.resources import MessageBasedResource

logger = logging.getLogger(__name__)

MeasureType = Literal["DEFAULT", "J", "W"]
TriggerSource = Literal["DEFAULT", "INTERNAL", "EXTERNAL"]
TriggerSlope = Literal["DEFAULT", "POSITIVE", "NEGATIVE"]

# these are:
# energy,
# period,
# flags (P: peak clip error, B: baseline clip error, M: missed pulse, D: dirty batch, 0: OK),
# sequence ID (number of trigger)
ReadValue = Literal["PULS", "PER", "FLAG", "SEQ"]
Flags = Literal["P", "B", "M", "D"]


class ReadDict(TypedDict, total=False):
    PULS: Optional[float]
    PER: Optional[int]
    FLAG: Optional[str]
    SEQ: Optional[int]


class EnergyMaxUSB:
    def __init__(
        self, em_resource: MessageBasedResource, model: str, serial: str
    ) -> None:
        self.em_resource = em_resource

        self.model = self.query("SYSTEM:INFORMATION:MODEL?")
        assert self.model == model
        self.serial = self.query("SYSTEM:INFORMATION:SNUMBER?")
        assert self.serial == serial

        self._min_wl = int(self.query("CONFIGURE:WAVELENGTH? MINIMUM"))
        self._max_wl = int(self.query("CONFIGURE:WAVELENGTH? MAXIMUM"))
        self._current_wl = self.query("CONFIGURE:WAVELENGTH?")
        self.set_measure_type("J")

        # TODO: put this in a method
        self.set_read_values(["PULS", "PER", "FLAG", "SEQ"])
        self.set_trigger_slope("POSITIVE")
        self.set_trigger_source("EXTERNAL")
        self.set_trigger_delay(0)

    @classmethod
    def constructor_default(
        cls,
        rm: pyvisa.ResourceManager,
        position: Literal["before_sample", "after_sample"] = "before_sample",
    ):
        match position:
            case "before_sample":
                model = '"EM-USB J-10MB-HE"'
                serial = '"0344D22R"'
                resource_name = "ASRL6::INSTR"
                return cls.constructor(rm, model, serial, resource_name)
            case "after_sample":
                model = '"EM-USB J-25MB-HE"'
                serial = '"0071F22R"'
                resource_name = "ASRL5::INSTR"
                return cls.constructor(rm, model, serial, resource_name)
            case _:
                raise ValueError(
                    f"Invalid position {position}. Should be either before_sample or after_sample"
                )

    @classmethod
    def constructor(
        cls,
        rm: pyvisa.ResourceManager,
        model: str,
        serial: str,
        resource_name: str,
    ):
        em = rm.open_resource(
            resource_name,
            read_termination=MessageBasedResource.CR + MessageBasedResource.LF,
        )
        assert isinstance(em, MessageBasedResource)
        return cls(em, model, serial)

    def _check_ok(self, ok: str, command: str) -> bool:
        if ok.strip() != "OK":
            try:
                logger.error(
                    f"failed to communicate command {command} to energy meter {self.serial}"
                )
            except AttributeError:
                logger.info(
                    f"failed to communicate command {command} to unknown energy meter"
                )
            return False
        return True

    def query(self, command: str) -> str:
        try:
            logger.info(f"Sending query {command} to energy meter {self.serial}")
        except AttributeError:
            logger.info(f"Sending query {command} to unknown energy meter")

        resp = self.em_resource.query(command)
        ok = self.em_resource.read()

        if self._check_ok(ok, command):
            return resp
        return ""

    def write(self, command: str):
        try:
            logger.info(f"Sending write {command} to energy meter {self.serial}")
        except AttributeError:
            logger.info(f"Sending write {command} to unknown energy meter")

        ok = self.em_resource.query(command)

        self._check_ok(ok, command)

    def get_energy(self) -> float | None:
        read_dict = self.read()
        if "PULS" in read_dict.keys():
            return read_dict["PULS"]
        logger.error(
            f"Tried to get PULS from read dict with keys {list(read_dict.keys())}"
        )

    def get_period(self) -> int | None:
        read_dict = self.read()
        if "PULS" in read_dict.keys():
            return read_dict["PER"]
        logger.error(
            f"Tried to get PER from read dict with keys {list(read_dict.keys())}"
        )

    def get_sequence(self) -> int | None:
        read_dict = self.read()
        if "PULS" in read_dict.keys():
            return read_dict["SEQ"]
        logger.error(
            f"Tried to get SEQ from read dict with keys {list(read_dict.keys())}"
        )

    def get_flags(self) -> list[Flags]:
        try:
            return list(self.read()["FLAG"])
        except KeyError:
            logger.error("Reading flags failed because value wasn't in response.")
        return []

    def read(self) -> ReadDict:
        resp = self.query("READ?").split(",")
        read_values = self.get_read_values().split(",")
        read_dict: ReadDict = {}
        if "FLAG" in read_values:
            flags = resp[read_values.index("FLAG")]

            if "0" not in flags:
                if "P" in flags:
                    logger.error(f"peak clip error for energy meter {self.serial}")
                if "B" in flags:
                    logger.error(f"baseline clip error for energy meter {self.serial}")
                if "M" in flags:
                    logger.error(f"missed pulse error for energy meter {self.serial}")
                if "D" in flags:
                    logger.error(f"dirty batch error for energy meter {self.serial}")

            read_dict["FLAG"] = flags

        if "PULS" in read_values:
            read_dict["PULS"] = float(resp[read_values.index("PULS")])

        if "SEQ" in read_values:
            read_dict["SEQ"] = int(resp[read_values.index("SEQ")])

        if "PER" in read_values:
            read_dict["PER"] = int(resp[read_values.index("PER")])

        return read_dict

    def read_energy(self) -> float:
        reading = self.read()
        try:
            return reading["PULS"]
        except KeyError:
            logger.error(
                f"Couldn't find PULS value in read dict {reading} from energy meter {self.serial}. Returning 0."
            )
            return 0.0

    def set_read_values(self, values: list[ReadValue]):
        if len(values) == 0 or len(values) > 4:
            logger.error(f"Invalid amount of values {len(values)}. Min 1, max 4")
            return
        self.write(f"CONFIGURE:ITEMSELECT {','.join(values)}")

    def get_read_values(self):
        return self.query("CONFIGURE:ITEMSELECT?")

    def set_measure_type(self, typ: MeasureType):
        self.write(f"CONFIGURE:MEASURE:TYPE {typ}")

    def get_measure_type(self) -> str:
        resp = self.query("CONFIGURE:MEASURE:TYPE?")
        return resp

    def set_trigger_source(self, source: TriggerSource):
        self.write(f"TRIGGER:SOURCE {source}")

    def get_trigger_source(self):
        return self.query("TRIGGER:SOURCE?")

    def set_trigger_slope(self, slope: TriggerSlope):
        self.write(f"TRIGGER:SLOPE {slope}")

    def get_trigger_slope(self):
        return self.query("TRIGGER:SLOPE?")

    def set_wavelength(self, wl: float):
        assert self.min_wl <= wl <= self.max_wl
        self.write(f"CONFIGURE:WAVELENGTH {wl}")

    def get_wavelength(self):
        return self.query("CONFIGURE:WAVELENGTH?")

    def set_trigger_delay(self, delay: int):
        assert 0 <= delay <= 1000
        self.write(f"TRIGGER:DELAY {delay}")

    def get_trigger_delay(self):
        return self.query("TRIGGER:DELAY?")

    def get_scale(self) -> float:
        """
        returns the max value of the scale.
        the ranges for each model are the following:
        J-MB10-HE: 12 µJ to 20 mJ
        J-MB10-HE: 50 µJ to 50 mJ
        """
        try:
            float(self.query("CONFIGURE:RANGE:SELECT?"))
        except ValueError as e:
            logger.error(
                f"converting the return value of getting scale failed with error {e}. Returning the max value."
            )
        return 50

    def set_scale(self, range: Literal["MIN", "MAX"]):
        return self.query(f"CONFIGURE:RANGE:SELECT {range}")

    @property
    def min_wl(self):
        return self._min_wl

    @property
    def max_wl(self):
        return self._max_wl

    @property
    def current_wl(self):
        return self._current_wl
