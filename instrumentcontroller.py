import random
import time

from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal
from forgot_again.file import load_ast_if_exists, pprint_to_file

from instr.instrumentfactory import mock_enabled, SourceFactory, AnalyzerFactory
from measureresult import MeasureResult
from secondaryparams import SecondaryParams

GIGA = 1_000_000_000
MEGA = 1_000_000
KILO = 1_000
MILLI = 1 / 1_000


class InstrumentController(QObject):
    pointReady = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        addrs = load_ast_if_exists('instr.ini', default={
            'АЦ': 'GPIB1::9::INSTR',
            'Источник': 'GPIB1::4::INSTR',
        })

        self.requiredInstruments = {
            'АЦ': AnalyzerFactory(addrs['АЦ']),
            'Источник': SourceFactory(addrs['Источник']),
        }

        self.deviceParams = {
            'Приёмник': {
                'F': 1,
            },
        }

        self.secondaryParams = SecondaryParams(required={
            'sweep_points': [
                'Кол-во точек=',
                {'start': 101.0, 'end': 1001.0, 'step': 10.0, 'value': 401.0, 'suffix': ''}
            ],
            'f_min': [
                'Fмин=',
                {'start': 1.0, 'end': 4.0, 'step': 0.5, 'value': 1.0, 'suffix': ' ГГц'}
            ],
            'f_max': [
                'Fмакс=',
                {'start': 1.0, 'end': 4.0, 'step': 0.5, 'value': 2.0, 'suffix': ' ГГц'}
            ],
            'p_in': [
                'Pвх=',
                {'start': -60.0, 'end': 0.0, 'step': 1.0, 'value': -20.0, 'suffix': ' дБм'}
            ],
            'src_u': [
                'Uпит=',
                {'start': 3.0, 'end': 3.5, 'step': 0.1, 'value': 3.3, 'suffix': ' В'}
            ],
            'src_i_max': [
                'Iпот.макс=',
                {'start': 10.0, 'end': 80.0, 'step': 1.0, 'value': 60.0, 'suffix': ' В'}
            ],
        })
        self.secondaryParams.load_from_config('params.ini')

        self._instruments = dict()
        self.found = False
        self.present = False
        self.hasResult = False

        self.result = MeasureResult()

    def __str__(self):
        return f'{self._instruments}'

    # region connections
    def connect(self, addrs):
        print(f'searching for {addrs}')
        for k, v in addrs.items():
            self.requiredInstruments[k].addr = v
        self.found = self._find()

    def _find(self):
        self._instruments = {
            k: v.find() for k, v in self.requiredInstruments.items()
        }
        return all(self._instruments.values())

    def check(self, token, params):
        print(f'call check with {token} {params}')
        device, secondary = params
        self.present = self._check(token, device, secondary)
        print('sample pass')

    def _check(self, token, device, secondary):
        print(f'launch check with {self.deviceParams[device]} {self.secondaryParams}')
        self._init()
        return True
    # endregion

    # region calibrations
    def calibrate(self, token, params):
        print(f'call calibrate with {token} {params}')
        return self._calibrate(token, self.secondaryParams)

    def _calibrateLO(self, token, secondary):
        print('run calibrate LO with', secondary)
        result = {}
        self._calibrated_pows_lo = result
        return True

    def _calibrateRF(self, token, secondary):
        print('run calibrate RF')
        result = {}
        self._calibrated_pows_rf = result
        return True

    def _calibrateMod(self, token, secondary):
        print('calibrate mod gen')
        result = {}
        self._calibrated_pows_mod = result
        return True
    # endregion

    # region initialization
    def _clear(self):
        self.result.clear()

    def _init(self):
        self._instruments['Источник'].send('*RST')
        self._instruments['АЦ'].send('*RST')
    # endregion

    def measure(self, token, params):
        print(f'call measure with {token} {params}')
        device, _ = params
        try:
            self.result.set_secondary_params(self.secondaryParams)
            self.result.set_primary_params(self.deviceParams[device])
            self._measure(token, device)
            # self.hasResult = bool(self.result)
            self.hasResult = True  # TODO HACK
        except RuntimeError as ex:
            print('runtime error:', ex)

    def _measure(self, token, device):
        param = self.deviceParams[device]
        secondary = self.secondaryParams.params
        print(f'launch measure with {token} {param} {secondary}')

        self._clear()
        _ = self._measure_tune(token, param, secondary)
        self.result.set_secondary_params(self.secondaryParams)
        return True

    def _measure_tune(self, token, param, secondary):
        pna = self._instruments['АЦ']
        src = self._instruments['Источник']

        sweep_points = secondary['sweep_points']
        pna_f_min = secondary['f_min'] * GIGA
        pna_f_max = secondary['f_max'] * GIGA
        p_in = secondary['p_in']
        src_u = secondary['src_u']
        src_i_max = secondary['src_i_max'] * MILLI

        pna.send('SYST:PRES')
        pna.query('*OPC?')
        # pna.send('SENS1:CORR ON')

        pna.send(f'SYSTem:FPRESet')

        pna.send('CALC1:PAR:DEF:EXT "CH1_S11",S11')
        # pna.send('CALC1:PAR:DEF:EXT "CH1_S21",S21')

        pna.send(f'DISPlay:WINDow1:STATe ON')
        pna.send(f"DISPlay:WINDow1:TRACe1:FEED 'CH1_S11'")
        # pna.send(f"DISPlay:WINDow1:TRACe2:FEED 'CH1_S21'")

        # pna.send(f'SENSe{chan}:SWEep:TRIGger:POINt OFF')
        pna.send(f'SOUR1:POW1 {p_in}dbm')

        pna.send(f'SENS1:SWE:POIN {sweep_points}')

        pna.send(f'SENS1:FREQ:STAR {pna_f_min}Hz')
        pna.send(f'SENS1:FREQ:STOP {pna_f_max}Hz')
        # pna.send(f'SENS1:POW:ATT AREC, {primary["Pin"]}')

        pna.send('SENS1:SWE:MODE CONT')
        pna.send(f'FORM:DATA ASCII')

        src.send('INST:SEL OUTP1')
        src.send(f'APPLY {src_u}V,{src_i_max}A')
        src.send('OUTP ON')

        # measurement
        res = []
        for p in [-15, -16, -15, -16, -15, -16, -15, -16, -15, -16, -15, -16, -15, -16, -15, -16]:
            pna.send(f'CALC1:PAR:SEL "CH1_S11"')
            pna.query('*OPC?')
            # res = pna.query(f'CALC1:DATA:SNP? 1')

            if not mock_enabled:
                time.sleep(0.5)

            pna.send(f'SOUR1:POW1 {p}dbm')

            # pna.send(f'CALC1:PAR:SEL "CH1_S21"')
            # pna.query('*OPC?')

            if not mock_enabled:
                time.sleep(0.5)

            offs = random.randint(-4, 4)
            pna.send(f'CALC:OFFS:MAGN {offs}')
            slop = random.random()
            pna.send(f'CALC:OFFS:MAGN:SLOP {slop}')

            if not mock_enabled:
                time.sleep(0.1)

            pna.send(f'DISP:WIND:TRAC:Y:AUTO')

            res.append(p)

        src.send('OUTP OFF')
        pna.send('SYST:PRES')

        return res

    def _add_measure_point(self, data):
        print('measured point:', data)
        self.result.add_point(data)
        self.pointReady.emit()

    def saveConfigs(self):
        pprint_to_file('params.ini', self.secondaryParams.params)

    @pyqtSlot(dict)
    def on_secondary_changed(self, params):
        self.secondaryParams.params = params

    @property
    def status(self):
        return [i.status for i in self._instruments.values()]
