import unreal, pathlib, time, json, traceback
root=pathlib.Path(__file__).resolve().parent
result={'stage':'initializing'}
start=time.monotonic()
phase=0
handle=None
def record():
    (root/'editor_render_result.json').write_text(json.dumps(result,indent=2))
def tick(dt):
    global phase, handle
    try:
        elapsed=time.monotonic()-start
        if elapsed>150:
            raise TimeoutError('Editor render/play smoke exceeded 150 seconds')
        if phase==0:
            level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
            assert level.load_level('/Game/PipelineSmoke/SmokeMap')
            camera=unreal.Vector(500,-500,400)
            unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(camera,unreal.MathLibrary.find_look_at_rotation(camera,unreal.Vector(0,0,100)))
            actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
            light=actors.spawn_actor_from_class(unreal.DirectionalLight,unreal.Vector(0,0,400),unreal.Rotator(-45,-30,0))
            light.set_actor_label('RenderSmokeLight')
            light.light_component.set_intensity(75000)
            fill=actors.spawn_actor_from_class(unreal.PointLight,unreal.Vector(200,-200,350))
            fill.light_component.set_intensity(100000)
            result.update(stage='waiting_for_viewport',setup_seconds=elapsed)
            phase=1
            record()
        elif phase==1 and elapsed>25:
            unreal.AutomationLibrary.take_high_res_screenshot(960,540,str(root/'unreal_viewport.png'))
            result['screenshot_requested']=True
            result['stage']='waiting_for_screenshot'
            phase=3
            record()
        elif phase==3 and elapsed>32:
            unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_play_simulate()
            phase=2
            result['stage']='waiting_for_simulation'
            record()
        elif phase==2 and elapsed>40:
            world=unreal.EditorLevelLibrary.get_game_world()
            assert world is not None, 'No play/simulation world'
            cubes=[a for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.StaticMeshActor) if a.static_mesh_component.static_mesh is not None]
            assert cubes, 'No static mesh actor in simulation world'
            result.update(simulation_world=world.get_name(),simulation_mesh_actors=len(cubes),stage='complete',ok=True)
            record()
            unreal.unregister_slate_post_tick_callback(handle)
            unreal.SystemLibrary.quit_editor()
    except Exception:
        result.update(ok=False,error=traceback.format_exc())
        record()
        if handle: unreal.unregister_slate_post_tick_callback(handle)
        unreal.SystemLibrary.quit_editor()
handle=unreal.register_slate_post_tick_callback(tick)
record()
