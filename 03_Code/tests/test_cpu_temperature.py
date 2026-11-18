import sys
from pathlib import Path
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch, Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cpu_temperature import *

class TemperatureTests(unittest.TestCase):
    def test_valid_and_boundaries(self):
        for v in (None,0,-1,151,float('nan'),float('inf'),'bad'):
            self.assertIsNone(package_value(v))
        self.assertEqual(package_value(120),120)
        for device, limits in [('cpu',(75,85,94)),('RTX 5060 Ti',(60,75,82)),('RTX 3060',(65,78,84))]:
            for i,t in enumerate(limits):
                self.assertEqual(temperature_color(device,t),COLORS[i])
                self.assertEqual(temperature_color(device,t+.1),COLORS[i+1])
        self.assertEqual(temperature_color('cpu',None),'#8C9BAE')

    def tree(self,value='52 °C'):
        return {'Text':'Sensor','Children':[{'HardwareId':'/intelcpu/0','ImageURL':'images_icon/cpu.png','Children':[{'Text':'CPU Package','Type':'Temperature','SensorId':'/intelcpu/0/temperature/16','Value':value}]}]}

    def test_http_identity_units_ambiguity(self):
        tree=self.tree()
        self.assertEqual(parse_lhm_cpu_package(tree),52)
        tree['Children']*=2
        self.assertIsNone(parse_lhm_cpu_package(tree))
        for value in ('52 W','NaN °C','151 °C','0 °C'):
            self.assertIsNone(parse_lhm_cpu_package(self.tree(value)))
        tree=self.tree();tree['Children'][0]['Children'][0]['SensorId']='/gpu/temperature/0'
        self.assertIsNone(parse_lhm_cpu_package(tree))

    def test_dll_unique_and_cpu_only(self):
        reader=DllCpuPackage();sensor=NS(SensorType='Temperature',Name='CPU Package',Value=53)
        reader.computer=NS(Hardware=[NS(HardwareType='Cpu',Update=Mock(),Sensors=[sensor])])
        self.assertEqual(reader.read(),53)
        reader.computer.Hardware[0].Sensors.append(sensor)
        self.assertIsNone(reader.read())

    def test_fallback_no_stale_close(self):
        with patch('cpu_temperature.platform.system',return_value='Windows'):
            provider=CpuTemperature()
        provider.dll=Mock(status='DLL: unavailable')
        provider.dll.read.side_effect=[52,None,None]
        with patch('cpu_temperature.read_lhm_cpu_package_http',side_effect=[54,OSError()]):
            self.assertEqual(provider.read(),52)
            self.assertEqual(provider.read(),54)
            self.assertIsNone(provider.read())
        provider.close();provider.dll.close.assert_called_once()

    def test_dll_failure_cooldown(self):
        sensor=CpuPackageSensor();sensor.reader=Mock();sensor.reader.open.side_effect=OSError('missing')
        with patch('cpu_temperature.ctypes.windll',create=True) as windll,patch('cpu_temperature.time.monotonic',return_value=100):
            windll.shell32.IsUserAnAdmin.return_value=True
            self.assertIsNone(sensor.read());self.assertIsNone(sensor.read())
        sensor.reader.open.assert_called_once();sensor.reader.close.assert_called_once()

    def test_http_no_redirect(self):
        self.assertIsNone(LocalSensorNoRedirect().redirect_request(None,None,302,'',{},'http://example.com'))

if __name__=='__main__':unittest.main()
