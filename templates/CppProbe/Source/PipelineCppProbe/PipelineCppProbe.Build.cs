using UnrealBuildTool;
public class PipelineCppProbe : ModuleRules {
    public PipelineCppProbe(ReadOnlyTargetRules Target) : base(Target) {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new string[] {"Core", "CoreUObject", "Engine"});
    }
}
