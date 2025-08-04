using UnityEngine;
using System.Collections;

/// <summary>
/// Force VR Initialization for Oculus Link
/// This ensures Unity properly connects to the Quest 3 headset
/// </summary>
public class ForceVRInit : MonoBehaviour
{
    [Header("VR Initialization")]
    [Tooltip("Force VR initialization on Start")]
    public bool initializeVROnStart = true;
    
    [Header("Debug Info")]
    public bool showDebugInfo = true;

    void Start()
    {
        if (initializeVROnStart)
        {
            StartCoroutine(InitializeVR());
        }
    }

    IEnumerator InitializeVR()
    {
        if (showDebugInfo)
        {
            Debug.Log("=== FORCE VR INITIALIZATION ===");
            Debug.Log("Attempting to initialize VR for Quest 3...");
        }

#if UNITY_XR_AVAILABLE
        // Check if XR is already enabled
        if (UnityEngine.XR.XRSettings.enabled)
        {
            if (showDebugInfo)
            {
                Debug.Log($"✓ XR already enabled: {UnityEngine.XR.XRSettings.loadedDeviceName}");
                Debug.Log($"Eye texture resolution: {UnityEngine.XR.XRSettings.eyeTextureWidth}x{UnityEngine.XR.XRSettings.eyeTextureHeight}");
            }
        }
        else
        {
            if (showDebugInfo)
                Debug.Log("XR not enabled, attempting to initialize...");

            // Try to initialize XR
            UnityEngine.XR.XRSettings.enabled = true;
            yield return new WaitForSeconds(1f);

            if (UnityEngine.XR.XRSettings.enabled)
            {
                if (showDebugInfo)
                {
                    Debug.Log("✓ XR initialized successfully!");
                    Debug.Log($"Device: {UnityEngine.XR.XRSettings.loadedDeviceName}");
                }
            }
            else
            {
                Debug.LogError("✗ Failed to initialize XR!");
                Debug.LogError("Make sure:");
                Debug.LogError("1. Quest 3 is connected via USB");
                Debug.LogError("2. Oculus Link is enabled in headset");
                Debug.LogError("3. XR Management has Oculus enabled for PC Standalone");
            }
        }
#else
        Debug.LogError("Unity XR not available - check XR packages installation");
#endif

        // Additional checks
        CheckVRStatus();
        yield return null;
    }

    [ContextMenu("Check VR Status")]
    public void CheckVRStatus()
    {
        Debug.Log("=== VR STATUS CHECK ===");

#if UNITY_XR_AVAILABLE
        Debug.Log($"XR Enabled: {UnityEngine.XR.XRSettings.enabled}");
        Debug.Log($"Device Name: {UnityEngine.XR.XRSettings.loadedDeviceName}");
        Debug.Log($"Device Active: {UnityEngine.XR.XRDevice.isPresent}");
        Debug.Log($"Eye Texture: {UnityEngine.XR.XRSettings.eyeTextureWidth}x{UnityEngine.XR.XRSettings.eyeTextureHeight}");
        Debug.Log($"Render Scale: {UnityEngine.XR.XRSettings.eyeTextureResolutionScale}");

        if (UnityEngine.XR.XRDevice.isPresent)
        {
            Debug.Log("✓ VR Device detected and ready");
        }
        else
        {
            Debug.LogWarning("⚠ No VR device detected");
            Debug.LogWarning("Check Quest 3 connection and Oculus Link status");
        }
#endif

        // Check camera setup
        Camera mainCam = Camera.main;
        if (mainCam != null)
        {
            Debug.Log($"Main Camera: {mainCam.name}");
            Debug.Log($"Camera Position: {mainCam.transform.position}");
            Debug.Log($"Camera Stereo Target Eye: {mainCam.stereoTargetEye}");
        }
        else
        {
            Debug.LogWarning("⚠ No main camera found");
        }
    }

    [ContextMenu("Force Reinitialize VR")]
    public void ForceReinitializeVR()
    {
        StartCoroutine(ReinitializeVR());
    }

    IEnumerator ReinitializeVR()
    {
        Debug.Log("=== FORCE VR REINITIALIZATION ===");

#if UNITY_XR_AVAILABLE
        // Disable XR first
        UnityEngine.XR.XRSettings.enabled = false;
        yield return new WaitForSeconds(1f);

        // Re-enable XR
        UnityEngine.XR.XRSettings.enabled = true;
        yield return new WaitForSeconds(2f);

        CheckVRStatus();
#endif
        yield return null;
    }

    void Update()
    {
        // Optional: Show VR status in real-time
        if (showDebugInfo && Input.GetKeyDown(KeyCode.V))
        {
            CheckVRStatus();
        }
    }
}
