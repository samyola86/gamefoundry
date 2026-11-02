import bpy, pathlib, json
root = pathlib.Path(__file__).resolve().parent
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=2, location=(0,0,1))
obj=bpy.context.object
obj.name='PipelineCube'
bpy.ops.export_scene.fbx(filepath=str(root/'cube.fbx'), use_selection=True, axis_forward='-Y', axis_up='Z', mesh_smooth_type='FACE')
assert (root/'cube.fbx').stat().st_size > 1000
(root/'blender_result.json').write_text(json.dumps({'version':bpy.app.version_string,'vertices':len(obj.data.vertices),'export_bytes':(root/'cube.fbx').stat().st_size}))
print('PIPELINE_BLENDER_OK')
