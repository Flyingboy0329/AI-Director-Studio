# CPU sensor dependencies

Unmodified LibreHardwareMonitorLib 0.9.6.0 and the local managed dependency closure are bundled here. No LibreHardwareMonitor GUI, driver installer, credentials, machine settings or model weights are included. Each DLL is byte-identical to the source deployment; verify SHA256.json.

| Component | License | Corresponding source |
| --- | --- | --- |
| LibreHardwareMonitorLib | MPL-2.0; embedded PawnIO modules carry the upstream notices | https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/tree/v0.9.6 |
| BlackSharp.Core 1.0.7 | MPL-2.0 | https://github.com/Blacktempel/BlackSharp and https://www.nuget.org/packages/BlackSharp.Core/1.0.7 |
| DiskInfoToolkit 1.1.2 | MPL-2.0 | https://github.com/Blacktempel/DiskInfoToolkit and https://www.nuget.org/packages/DiskInfoToolkit/1.1.2 |
| RAMSPDToolkit-NDD 1.4.2 | MPL-2.0 | https://github.com/Blacktempel/RAMSPDToolkit and https://www.nuget.org/packages/RAMSPDToolkit-NDD/1.4.2 |
| HidSharp 2.6.4 | Apache-2.0 | https://github.com/SeekHisKingdom/HIDSharp and https://software.seekye.com/hidsharp |
| System.Buffers, System.Memory, System.Numerics.Vectors, System.Runtime.CompilerServices.Unsafe | MIT | https://github.com/dotnet/runtime |

License texts and notices are preserved in licenses/. Source code is available from the linked upstream repositories/packages; these components have not been modified. No component's license is replaced by an application license. The upstream PawnIO notice is preserved with LibreHardwareMonitor's notices; the kernel driver itself is not redistributed or installed by this package.

Windows prerequisites: .NET Framework 4.7.2 or compatible later version, Python.NET from requirements-cpu-sensor.txt, an existing compatible PawnIO installation and administrator consent where required. Missing permissions/driver/CPU Package support yields N/A, not a simulated temperature. Bundling DLLs does not ensure every CPU exposes a CPU Package sensor.
