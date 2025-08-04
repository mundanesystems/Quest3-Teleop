using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
using UnityEditor.SceneManagement;
#endif

/// <summary>
/// Clean Scene Setup - Removes missing scripts and creates fresh Oculus Link setup
/// </summary>
public class CleanSceneSetup : MonoBehaviour
{
    [Header("Scene Cleanup")]
    [Tooltip("Remove all GameObjects with missing scripts")]
    public bool removeMissingScripts = true;
    
    [Header("Fresh Oculus Link Setup")]
    [Tooltip("Create new Oculus Link components")]
    public bool createOculusLinkSetup = true;

    void Start()
    {
        Debug.Log("=== CLEAN SCENE SETUP ===");
        Debug.Log("Use the context menu options to clean up the scene");
    }

#if UNITY_EDITOR
    [ContextMenu("Clean Scene - Remove Missing Scripts")]
    public void CleanMissingScripts()
    {
        Debug.Log("=== CLEANING MISSING SCRIPTS ===");
        
        GameObject[] allObjects = FindObjectsOfType<GameObject>();
        int removedCount = 0;
        
        foreach (GameObject obj in allObjects)
        {
            // Get all components
            Component[] components = obj.GetComponents<Component>();
            
            for (int i = components.Length - 1; i >= 0; i--)
            {
                if (components[i] == null)
                {
                    Debug.Log($"Removing missing script from: {obj.name}");
                    
                    // Remove the missing component
                    SerializedObject serializedObject = new SerializedObject(obj);
                    SerializedProperty prop = serializedObject.FindProperty("m_Component");
                    
                    prop.DeleteArrayElementAtIndex(i);
                    serializedObject.ApplyModifiedProperties();
                    removedCount++;
                }
            }
            
            // If object has no components left and is not essential, consider removing
            Component[] remainingComponents = obj.GetComponents<Component>();
            if (remainingComponents.Length == 1 && remainingComponents[0] is Transform)
            {
                // Only has Transform - check if it's a container or has children
                if (obj.transform.childCount == 0 && 
                    !obj.name.Contains("Camera") && 
                    !obj.name.Contains("Light") &&
                    !obj.name.Contains("Directional"))
                {
                    Debug.Log($"Removing empty GameObject: {obj.name}");
                    DestroyImmediate(obj);
                }
            }
        }
        
        Debug.Log($"✓ Removed {removedCount} missing script references");
        EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
    }

    [ContextMenu("Create Fresh Oculus Link Setup")]
    public void CreateFreshSetup()
    {
        Debug.Log("=== CREATING FRESH OCULUS LINK SETUP ===");
        
        // Remove old setup if exists
        GameObject oldVideo = GameObject.Find("Video Receiver");
        GameObject oldGyro = GameObject.Find("Gyroscope Reader");
        GameObject oldSetup = GameObject.Find("Setup Helper");
        
        if (oldVideo) DestroyImmediate(oldVideo);
        if (oldGyro) DestroyImmediate(oldGyro);
        if (oldSetup) DestroyImmediate(oldSetup);
        
        // Create setup helper
        GameObject setupHelper = new GameObject("Setup Helper");
        setupHelper.AddComponent<ManualOculusLinkSetup>();
        
        // Create VR initializer
        GameObject vrInit = new GameObject("VR Initializer");
        vrInit.AddComponent<ForceVRInit>();
        
        // Create video receiver
        GameObject videoReceiver = new GameObject("Video Receiver");
        var videoComp = videoReceiver.AddComponent<OculusLinkVideoReceiver>();
        videoComp.serverAddress = "127.0.0.1";
        videoComp.serverPort = 8080;
        videoComp.displayDistance = 3.0f;
        videoComp.displayScale = 2.0f;
        videoComp.showDebugInfo = true;
        videoComp.autoReconnect = true;
        
        // Create gyroscope reader
        GameObject gyroReader = new GameObject("Gyroscope Reader");
        var gyroComp = gyroReader.AddComponent<OculusLinkGyroscopeReader>();
        gyroComp.pcIPAddress = "127.0.0.1";
        gyroComp.port = 9050;
        gyroComp.sendRate = 20f;
        gyroComp.showDebugInfo = true;
        
        // Try to assign head anchor
        Camera mainCamera = Camera.main;
        if (mainCamera != null)
        {
            gyroComp.headAnchor = mainCamera.transform;
            Debug.Log($"✓ Assigned head anchor: {mainCamera.name}");
        }
        
        Debug.Log("✓ Fresh Oculus Link setup created");
        Debug.Log("Components created:");
        Debug.Log("- Setup Helper (ManualOculusLinkSetup)");
        Debug.Log("- Video Receiver (OculusLinkVideoReceiver)");
        Debug.Log("- Gyroscope Reader (OculusLinkGyroscopeReader)");
        
        EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
    }

    [ContextMenu("Full Scene Reset")]
    public void FullSceneReset()
    {
        Debug.Log("=== FULL SCENE RESET ===");
        
        // First clean missing scripts
        CleanMissingScripts();
        
        // Wait a frame
        EditorApplication.delayCall += () => {
            // Then create fresh setup
            CreateFreshSetup();
            
            Debug.Log("✓ Scene fully reset and ready for Oculus Link testing!");
            Debug.Log("Next steps:");
            Debug.Log("1. Make sure Quest 3 is connected via USB with Link enabled");
            Debug.Log("2. Check Unity Build Settings - should be PC Standalone");
            Debug.Log("3. Check XR Management - Oculus should be enabled for PC Standalone");
            Debug.Log("4. Start your Python servers");
            Debug.Log("5. Hit Play!");
        };
    }
#endif

    [ContextMenu("Check Scene Status")]
    public void CheckSceneStatus()
    {
        Debug.Log("=== SCENE STATUS CHECK ===");
        
        GameObject[] allObjects = FindObjectsOfType<GameObject>();
        int missingScriptCount = 0;
        
        foreach (GameObject obj in allObjects)
        {
            Component[] components = obj.GetComponents<Component>();
            foreach (Component comp in components)
            {
                if (comp == null)
                {
                    missingScriptCount++;
                    Debug.LogWarning($"Missing script on: {obj.name}");
                }
            }
        }
        
        if (missingScriptCount > 0)
        {
            Debug.LogError($"Found {missingScriptCount} missing script references!");
            Debug.LogError("Use 'Clean Scene - Remove Missing Scripts' to fix this");
        }
        else
        {
            Debug.Log("✓ No missing scripts found");
        }
        
        // Check for Oculus Link components
        bool hasVideoReceiver = FindObjectOfType<OculusLinkVideoReceiver>() != null;
        bool hasGyroReader = FindObjectOfType<OculusLinkGyroscopeReader>() != null;
        
        Debug.Log($"OculusLinkVideoReceiver: {(hasVideoReceiver ? "✓ Found" : "✗ Missing")}");
        Debug.Log($"OculusLinkGyroscopeReader: {(hasGyroReader ? "✓ Found" : "✗ Missing")}");
        
        if (!hasVideoReceiver || !hasGyroReader)
        {
            Debug.LogWarning("Use 'Create Fresh Oculus Link Setup' to add missing components");
        }
    }
}
