using UnityEngine;

/// <summary>
/// Creates a proper VR camera setup for Oculus Link
/// </summary>
public class VRCameraSetup : MonoBehaviour
{
    [Header("VR Camera Setup")]
    [Tooltip("Automatically setup VR camera on Start")]
    public bool autoSetupOnStart = true;
    
    void Start()
    {
        if (autoSetupOnStart)
        {
            SetupVRCamera();
        }
    }
    
    [ContextMenu("Setup VR Camera")]
    public void SetupVRCamera()
    {
        Debug.Log("=== SETTING UP VR CAMERA ===");
        
        // Remove existing Main Camera if it exists
        Camera existingCamera = Camera.main;
        if (existingCamera != null && existingCamera.gameObject.name == "Main Camera")
        {
            Debug.Log("Removing existing Main Camera for VR setup");
            DestroyImmediate(existingCamera.gameObject);
        }
        
        // Create VR Camera setup
        GameObject vrCamera = new GameObject("VR Camera");
        Camera camera = vrCamera.AddComponent<Camera>();
        camera.tag = "MainCamera";
        
        // Configure camera for VR
        camera.nearClipPlane = 0.01f;
        camera.farClipPlane = 1000f;
        camera.fieldOfView = 90f;
        
        // Add audio listener
        vrCamera.AddComponent<AudioListener>();
        
        Debug.Log("✓ VR Camera setup complete");
        Debug.Log("Camera position: " + vrCamera.transform.position);
        Debug.Log("Make sure Unity XR is configured for PC Standalone + Oculus!");
    }
    
    [ContextMenu("Check VR Status")]
    public void CheckVRStatus()
    {
        Debug.Log("=== VR STATUS CHECK ===");
        
        // Check if XR is available
#if UNITY_XR_AVAILABLE
        Debug.Log("✓ Unity XR is available");
        
        if (UnityEngine.XR.XRSettings.enabled)
        {
            Debug.Log("✓ XR is enabled");
            Debug.Log($"XR Device: {UnityEngine.XR.XRSettings.loadedDeviceName}");
            Debug.Log($"XR Display: {UnityEngine.XR.XRSettings.eyeTextureWidth}x{UnityEngine.XR.XRSettings.eyeTextureHeight}");
        }
        else
        {
            Debug.LogWarning("⚠ XR is not enabled!");
            Debug.LogWarning("Go to Edit > Project Settings > XR Plug-in Management");
            Debug.LogWarning("Check 'Oculus' under PC Standalone tab");
        }
#else
        Debug.LogError("✗ Unity XR is not available - check XR packages");
#endif
        
        // Check camera setup
        Camera mainCam = Camera.main;
        if (mainCam != null)
        {
            Debug.Log($"✓ Main Camera found: {mainCam.name}");
            Debug.Log($"Camera position: {mainCam.transform.position}");
        }
        else
        {
            Debug.LogWarning("⚠ No Main Camera found");
        }
    }
}
