using UnityEngine;
using UnityEditor;

#if UNITY_EDITOR
/// <summary>
/// Setup script to configure Unity for Oculus Link development
/// This enables instant VR testing without Android builds
/// </summary>
public class OculusLinkSetup : EditorWindow
{
    [MenuItem("VR Development/Setup Oculus Link")]
    public static void ShowWindow()
    {
        EditorWindow.GetWindow(typeof(OculusLinkSetup));
    }

    void OnGUI()
    {
        GUILayout.Label("Oculus Link Setup for Instant VR Testing", EditorStyles.boldLabel);
        GUILayout.Space(10);

        GUILayout.Label("This will configure your Unity project to work with Oculus Link,");
        GUILayout.Label("allowing you to test VR changes instantly in the Unity Editor!");
        GUILayout.Space(10);

        GUILayout.Label("Current Platform: " + EditorUserBuildSettings.activeBuildTarget.ToString());
        GUILayout.Space(5);

        if (GUILayout.Button("1. Switch to PC Standalone"))
        {
            SwitchToPCStandalone();
        }
        GUILayout.Space(5);

        if (GUILayout.Button("2. Configure XR Settings for Oculus Link"))
        {
            ConfigureXRSettings();
        }
        GUILayout.Space(5);

        if (GUILayout.Button("3. Create Test Scene with Oculus Link Components"))
        {
            CreateTestScene();
        }
        GUILayout.Space(10);

        GUILayout.Label("Instructions:", EditorStyles.boldLabel);
        GUILayout.Label("1. Connect Quest 3 to PC via USB-C cable");
        GUILayout.Label("2. Enable Oculus Link in Quest 3 headset");
        GUILayout.Label("3. Run your Python servers (realsense_stream_server.py, etc.)");
        GUILayout.Label("4. Hit Play in Unity Editor - instant VR testing!");
        GUILayout.Space(5);
        
        GUILayout.Label("Benefits:", EditorStyles.boldLabel);
        GUILayout.Label("✓ No more Android builds (5-15 minutes saved per test!)");
        GUILayout.Label("✓ Python server changes reflect immediately");
        GUILayout.Label("✓ Unity script changes work with hot reload");
        GUILayout.Label("✓ Full VR testing with real Quest 3 hardware");
    }

    void SwitchToPCStandalone()
    {
        if (EditorUserBuildSettings.activeBuildTarget != BuildTarget.StandaloneWindows64)
        {
            Debug.Log("Switching build target to PC Standalone...");
            EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Standalone, BuildTarget.StandaloneWindows64);
            Debug.Log("✓ Build target switched to PC Standalone");
        }
        else
        {
            Debug.Log("✓ Already using PC Standalone build target");
        }
    }

    void ConfigureXRSettings()
    {
        Debug.Log("Configuring XR settings for Oculus Link...");
        
        // Note: In Unity 2022.3, XR settings are managed through XR Management
        // The user should manually configure these through Project Settings > XR Plug-in Management
        
        Debug.Log("Please manually configure XR settings:");
        Debug.Log("1. Go to Edit > Project Settings > XR Plug-in Management");
        Debug.Log("2. Check 'Oculus' provider for PC Standalone");
        Debug.Log("3. Ensure 'Initialize XR on Startup' is checked");
        
        // Open the Project Settings window
        SettingsService.OpenProjectSettings("Project/XR Plug-in Management");
    }

    void CreateTestScene()
    {
        Debug.Log("Creating Oculus Link test scene...");
        
        // Create a new scene
        var scene = UnityEditor.SceneManagement.EditorSceneManager.NewScene(
            UnityEditor.SceneManagement.NewSceneSetup.DefaultGameObjects, 
            UnityEditor.SceneManagement.NewSceneMode.Single);

        // Remove default camera (VR will provide its own)
        GameObject defaultCamera = GameObject.Find("Main Camera");
        if (defaultCamera != null)
        {
            DestroyImmediate(defaultCamera);
        }

        // Create VR setup
        CreateVRSetup();
        
        // Create video receiver
        CreateVideoReceiver();
        
        // Create gyroscope sender
        CreateGyroscopeReader();
        
        // Save the scene
        string scenePath = "Assets/Scenes/OculusLinkTest.unity";
        UnityEditor.SceneManagement.EditorSceneManager.SaveScene(scene, scenePath);
        
        Debug.Log($"✓ Test scene created: {scenePath}");
        Debug.Log("Ready for Oculus Link testing!");
    }

    void CreateVRSetup()
    {
        // Create XR Origin (replaces XR Rig in newer Unity versions)
        GameObject xrOrigin = new GameObject("XR Origin");
        
        // Add XR Origin component (if available)
        var xrOriginComponent = xrOrigin.AddComponent(System.Type.GetType("Unity.XR.CoreUtils.XROrigin, Unity.XR.CoreUtils"));
        if (xrOriginComponent == null)
        {
            Debug.LogWarning("XR Origin component not found - make sure XR packages are installed");
        }

        // Create Camera Offset
        GameObject cameraOffset = new GameObject("Camera Offset");
        cameraOffset.transform.parent = xrOrigin.transform;

        // Create Main Camera for VR
        GameObject mainCamera = new GameObject("Main Camera");
        mainCamera.transform.parent = cameraOffset.transform;
        var camera = mainCamera.AddComponent<Camera>();
        camera.tag = "MainCamera";
        
        // Add TrackedPoseDriver for VR head tracking
        var trackedPoseDriver = mainCamera.AddComponent(System.Type.GetType("UnityEngine.SpatialTracking.TrackedPoseDriver, UnityEngine.SpatialTracking"));
        if (trackedPoseDriver == null)
        {
            Debug.LogWarning("TrackedPoseDriver not found - VR head tracking may not work");
        }

        Debug.Log("✓ VR setup created");
    }

    void CreateVideoReceiver()
    {
        GameObject videoReceiver = new GameObject("Video Receiver");
        videoReceiver.AddComponent<OculusLinkVideoReceiver>();
        
        Debug.Log("✓ Video receiver created");
    }

    void CreateGyroscopeReader()
    {
        GameObject gyroReader = new GameObject("Gyroscope Reader");
        var gyroComponent = gyroReader.AddComponent<OculusLinkGyroscopeReader>();
        
        // Try to find and assign the main camera
        GameObject mainCamera = GameObject.Find("Main Camera");
        if (mainCamera != null)
        {
            gyroComponent.headAnchor = mainCamera.transform;
        }
        
        Debug.Log("✓ Gyroscope reader created");
    }
}
#endif
