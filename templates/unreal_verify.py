import unreal, pathlib, json
root=pathlib.Path(__file__).resolve().parent
subsystem=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert subsystem.load_level('/Game/PipelineSmoke/SmokeMap')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
cube=next(a for a in actors if a.get_actor_label()=='PipelineCube')
mesh=cube.static_mesh_component.static_mesh
assert isinstance(mesh,unreal.StaticMesh)
assert mesh.get_num_lods() >= 1
assert mesh.get_num_sections(0) >= 1
(root/'unreal_reopen_result.json').write_text(json.dumps({'reopened':True,'actor':cube.get_actor_label(),'mesh':mesh.get_path_name(),'lods':mesh.get_num_lods(),'sections':mesh.get_num_sections(0)}))
unreal.log('PIPELINE_REOPEN_OK')
