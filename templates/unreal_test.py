import unreal, pathlib, json, traceback
root=pathlib.Path(__file__).resolve().parent
try:
    task=unreal.AssetImportTask()
    task.filename=str(root/'cube.fbx')
    task.destination_path='/Game/PipelineSmoke'
    task.automated=True
    task.replace_existing=True
    task.save=True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    meshes=[unreal.load_asset(p) for p in task.imported_object_paths]
    mesh=next(m for m in meshes if isinstance(m,unreal.StaticMesh))
    subsystem=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if unreal.EditorAssetLibrary.does_asset_exist('/Game/PipelineSmoke/SmokeMap'):
        assert subsystem.load_level('/Game/PipelineSmoke/SmokeMap')
        actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        for existing in actors.get_all_level_actors():
            if existing.get_actor_label()=='PipelineCube':
                assert actors.destroy_actor(existing)
    else:
        assert subsystem.new_level('/Game/PipelineSmoke/SmokeMap')
    actor=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(0,0,100))
    actor.static_mesh_component.set_static_mesh(mesh)
    actor.set_actor_label('PipelineCube')
    assert actor.static_mesh_component.static_mesh == mesh
    assert subsystem.save_current_level()
    (root/'unreal_result.json').write_text(json.dumps({'mesh':mesh.get_path_name(),'actor':actor.get_actor_label(),'map':'/Game/PipelineSmoke/SmokeMap','engine':unreal.SystemLibrary.get_engine_version()}))
    unreal.log('PIPELINE_UNREAL_OK')
except Exception:
    (root/'unreal_error.txt').write_text(traceback.format_exc())
    raise
