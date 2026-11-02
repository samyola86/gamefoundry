using UnrealBuildTool;
public class PipelineCppProbeTarget : TargetRules {
    public PipelineCppProbeTarget(TargetInfo Target) : base(Target) {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        ExtraModuleNames.Add("PipelineCppProbe");
    }
}
