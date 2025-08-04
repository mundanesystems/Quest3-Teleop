using UnityEngine;

#if UNITY_EDITOR
using UnityEditor;
#endif

public class QuickVideoStreamSetup : MonoBehaviour
{
    [Header("Quick Setup")]
    [Tooltip("Click to automatically setup video streaming for desktop testing")]
    public bool setupDesktopMode = true;
    
    [Header("Server Settings")]
    public string serverIP = "127.0.0.1";
    public int serverPort = 8080;

#if UNITY_EDITOR
    [ContextMenu("Setup Desktop Video Stream")]
    public void SetupDesktopVideoStream()
    {
        // Create video stream receiver object
        GameObject videoReceiver = new GameObject("Desktop Video Stream");
        DesktopVideoStreamReceiver receiver = videoReceiver.AddComponent<DesktopVideoStreamReceiver>();
        
        // Configure for desktop mode
        receiver.serverAddress = serverIP;
        receiver.serverPort = serverPort;
        receiver.standaloneMode = true;
        receiver.videoScale = 3.0f;
        
        // Position in scene
        videoReceiver.transform.position = new Vector3(0, 0, 5);
        
        // Setup camera if needed
        if (Camera.main == null)
        {
            GameObject cameraObj = new GameObject("Main Camera");
            Camera cam = cameraObj.AddComponent<Camera>();
            cam.tag = "MainCamera";
            cameraObj.transform.position = Vector3.zero;
            cameraObj.transform.rotation = Quaternion.identity;
        }
        
        Debug.Log("✅ Desktop video stream setup complete!");
        Debug.Log($"🔗 Connecting to: {serverIP}:{serverPort}");
        Debug.Log("🚀 Start the Python server and press Play!");
        
        // Select the created object
        Selection.activeGameObject = videoReceiver;
    }

    [ContextMenu("Setup VR Video Stream")]
    public void SetupVRVideoStream()
    {
        // Create video stream receiver object
        GameObject videoReceiver = new GameObject("VR Video Stream");
        DesktopVideoStreamReceiver receiver = videoReceiver.AddComponent<DesktopVideoStreamReceiver>();
        
        // Configure for VR mode
        receiver.serverAddress = "192.168.0.196"; // Your PC IP
        receiver.serverPort = serverPort;
        receiver.standaloneMode = false;
        receiver.positionOffset = new Vector3(0, 0, 2f);
        receiver.videoScale = 1.5f;
        
        Debug.Log("✅ VR video stream setup complete!");
        Debug.Log("📱 Deploy to Quest 3 to test");
        
        // Select the created object
        Selection.activeGameObject = videoReceiver;
    }
#endif

    void Start()
    {
        // Auto-setup if this component is added to a scene
        if (setupDesktopMode)
        {
#if UNITY_EDITOR
            SetupDesktopVideoStream();
#endif
            // Remove this component after setup
            Destroy(this);
        }
    }
}
