"""Create a starter asset file only when the destination does not exist."""
import bpy
import pathlib
import sys
path = pathlib.Path(sys.argv[sys.argv.index('--') + 1])
if path.exists():
    raise FileExistsError('Refusing to overwrite an existing Blender project')
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.save_as_mainfile(filepath=str(path), check_existing=False)
assert path.is_file()
print('STARTER_BLEND_OK')
