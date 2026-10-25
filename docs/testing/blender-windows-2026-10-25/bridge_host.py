import sys, time, pathlib, json
import bpy
sys.path.insert(0, r'D:\pyprj\2026\MyTargetProject\backend\modules\blender')
import zhenxun_bridge as bridge
bridge.PORT = 19877
bridge.register()
print('TEST_BRIDGE_READY ' + bpy.app.version_string, flush=True)
deadline = time.monotonic() + 600
try:
    while time.monotonic() < deadline:
        bridge._tick()
        time.sleep(.05)
finally:
    bridge.unregister()
