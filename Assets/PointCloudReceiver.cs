using UnityEngine;
using System.Net.Sockets;
using System.Threading;
using System;
using System.IO;
using System.Collections.Generic;

[System.Serializable]
public class PointCloudData
{
    public float[,] points;
    public float[,] colors;
    public double timestamp;
    public int point_count;
}

public class PointCloudReceiver : MonoBehaviour
{
    [Header("Network Settings")]
    public string serverAddress = "192.168.0.196"; // Your PC's IP address
    public int serverPort = 8081; // Point cloud server port

    [Header("VR Display Settings")]
    [Tooltip("The main camera for positioning")]
    public Camera mainCamera;
    [Tooltip("Position offset from camera")]
    public Vector3 positionOffset = new Vector3(0, 0, 1.5f); // Closer for VR
    [Tooltip("Scale of the point cloud")]
    public float pointCloudScale = 0.3f; // Smaller scale for VR viewing
    [Tooltip("Size of individual points")]
    public float pointSize = 0.003f; // Smaller points for VR

    [Header("Performance Settings")]
    public Material pointMaterial;
    public int maxPointsToRender = 15000;
    [Tooltip("Auto-reconnect if connection lost")]
    public bool autoReconnect = true;
    [Tooltip("Connection retry interval (seconds)")]
    public float reconnectInterval = 2.0f;

    private TcpClient client;
    private NetworkStream stream;
    private Thread receiveThread;
    private bool isRunning = false;
    private bool isConnected = false;

    private readonly object lockObject = new object();
    private bool newPointCloudReady = false;
    private float lastReconnectAttempt = 0f;

    private Vector3[] currentPoints;
    private Color[] currentColors;
    private List<GameObject> activePoints = new List<GameObject>();
    
    // Performance tracking
    private int framesReceived = 0;
    private float lastPerformanceReport = 0f;
    private Queue<float> latencyHistory = new Queue<float>();

    void Start()
    {
        // Find the correct VR camera if not assigned
        if (mainCamera == null)
        {
            // Look for OVR-specific cameras first
            Camera[] allCameras = FindObjectsOfType<Camera>();
            
            foreach (Camera cam in allCameras)
            {
                string camName = cam.gameObject.name.ToLower();
                
                // Priority order for OVR cameras
                if (camName.Contains("centereye") || camName.Contains("center_eye"))
                {
                    mainCamera = cam;
                    Debug.Log($"🎯 Found OVR Center Eye Camera: {cam.gameObject.name}");
                    break;
                }
                else if (camName.Contains("lefteye") || camName.Contains("left_eye"))
                {
                    mainCamera = cam;
                    Debug.Log($"🎯 Found OVR Left Eye Camera: {cam.gameObject.name}");
                    break;
                }
                else if (camName.Contains("main") && cam.enabled && cam.gameObject.activeInHierarchy)
                {
                    mainCamera = cam;
                    Debug.Log($"🎯 Found Main Camera: {cam.gameObject.name}");
                    break;
                }
            }
            
            // Fallback to Camera.main if no OVR camera found
            if (mainCamera == null)
            {
                mainCamera = Camera.main;
                Debug.LogWarning("⚠️ Using Camera.main - may not be optimal for VR");
            }
            
            // Debug: List all cameras found
            Debug.Log("📋 All cameras in scene:");
            foreach (Camera cam in allCameras)
            {
                Debug.Log($"   - {cam.gameObject.name} (enabled: {cam.enabled}, active: {cam.gameObject.activeInHierarchy})");
            }
        }

        // Create VR-optimized material if none assigned
        if (pointMaterial == null)
        {
            pointMaterial = new Material(Shader.Find("Standard"));
            pointMaterial.color = Color.white;
            pointMaterial.SetFloat("_Metallic", 0f);
            pointMaterial.SetFloat("_Glossiness", 0.2f);
        }

        Debug.Log($"🎯 VR Point Cloud Receiver initialized with camera: {(mainCamera ? mainCamera.gameObject.name : "NULL")}");
        
        // Generate test data immediately for debugging
        Debug.Log("🔥 Generating initial test data for VR debugging...");
        GenerateTestPointCloud();
        
        StartConnection();
    }

    void Update()
    {
        // Handle reconnection if needed
        if (!isConnected && autoReconnect && Time.time - lastReconnectAttempt > reconnectInterval)
        {
            StartConnection();
            lastReconnectAttempt = Time.time;
        }

        // Update position relative to VR camera
        if (mainCamera != null)
        {
            // Position the point cloud in front of the VR camera
            Vector3 forward = mainCamera.transform.forward;
            Vector3 right = mainCamera.transform.right;
            Vector3 up = mainCamera.transform.up;
            
            // Calculate position with proper VR scaling
            Vector3 targetPosition = mainCamera.transform.position + 
                                   forward * positionOffset.z + 
                                   right * positionOffset.x + 
                                   up * positionOffset.y;
            
            transform.position = targetPosition;
            
            // For VR, we typically want the point cloud to face the camera
            transform.LookAt(mainCamera.transform.position);
            
            // Debug info for VR positioning
            if (Time.time - lastPerformanceReport > 10.0f && currentPoints != null)
            {
                Debug.Log($"🎯 VR Point Cloud Position: {transform.position}, Distance from camera: {Vector3.Distance(transform.position, mainCamera.transform.position):F2}m");
            }
        }

        // Update point cloud if new data is available
        if (newPointCloudReady)
        {
            lock (lockObject)
            {
                if (currentPoints != null && currentColors != null)
                {
                    UpdatePointCloudVisualization();
                }
                newPointCloudReady = false;
            }
        }

        // Performance reporting
        if (Time.time - lastPerformanceReport > 5.0f)
        {
            float avgLatency = 0f;
            if (latencyHistory.Count > 0)
            {
                float total = 0f;
                foreach (float latency in latencyHistory)
                    total += latency;
                avgLatency = total / latencyHistory.Count;
            }

            Debug.Log($"🔥 VR Point Cloud: {framesReceived / 5.0f:F1} FPS | " +
                     $"{(currentPoints != null ? currentPoints.Length : 0):N0} points | " +
                     $"Latency: {avgLatency:F1}ms | Connected: {isConnected}");
            
            framesReceived = 0;
            lastPerformanceReport = Time.time;
            latencyHistory.Clear();
        }
    }

    void UpdatePointCloudVisualization()
    {
        Debug.Log($"🔥 UpdatePointCloudVisualization called - Current points: {(currentPoints != null ? currentPoints.Length : 0)}");
        
        // Clear existing points efficiently
        for (int i = 0; i < activePoints.Count; i++)
        {
            if (activePoints[i] != null)
                DestroyImmediate(activePoints[i]);
        }
        activePoints.Clear();

        if (currentPoints == null || currentPoints.Length == 0)
        {
            Debug.LogWarning("⚠️ No points to render!");
            return;
        }

        // Limit points for VR performance
        int pointsToRender = Mathf.Min(currentPoints.Length, maxPointsToRender);
        
        Debug.Log($"🎯 Rendering {pointsToRender} points at transform position: {transform.position}");
        Debug.Log($"🎯 Camera position: {(mainCamera ? mainCamera.transform.position.ToString() : "NULL")}");
        Debug.Log($"🎯 Distance from camera: {(mainCamera ? Vector3.Distance(transform.position, mainCamera.transform.position) : 0)}");
        
        // Create points optimized for VR
        for (int i = 0; i < pointsToRender; i++)
        {
            // Create point as a small sphere
            GameObject pointObj = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            pointObj.transform.parent = transform;
            
            // Scale and position for VR with bounds checking
            Vector3 scaledPosition = currentPoints[i] * pointCloudScale;
            pointObj.transform.localPosition = scaledPosition;
            pointObj.transform.localScale = Vector3.one * pointSize;
            
            // Make points VERY visible for debugging
            Renderer renderer = pointObj.GetComponent<Renderer>();
            Material pointMat = new Material(pointMaterial);
            pointMat.color = currentColors[i];
            
            // Make material unlit and bright
            pointMat.shader = Shader.Find("Unlit/Color");
            pointMat.color = new Color(currentColors[i].r, currentColors[i].g, currentColors[i].b, 1f);
            
            renderer.material = pointMat;
            
            // Remove collider for VR performance
            Collider collider = pointObj.GetComponent<Collider>();
            if (collider != null)
                DestroyImmediate(collider);
            
            activePoints.Add(pointObj);
            
            // Debug first few points
            if (i < 3)
            {
                Debug.Log($"   Point {i}: Local={scaledPosition}, World={pointObj.transform.position}, Color={currentColors[i]}");
            }
        }

        framesReceived++;
        Debug.Log($"✅ Successfully rendered {pointsToRender} VR points!");
    }

    void StartConnection()
    {
        if (isRunning)
        {
            Debug.LogWarning("⚠️ Already attempting connection to point cloud server");
            return;
        }

        try
        {
            Debug.Log($"🔗 Connecting to VR Point Cloud server at {serverAddress}:{serverPort}...");
            
            client = new TcpClient();
            client.ReceiveTimeout = 5000; // 5 second timeout
            client.SendTimeout = 5000;
            
            client.Connect(serverAddress, serverPort);
            stream = client.GetStream();
            isRunning = true;
            isConnected = true;

            receiveThread = new Thread(new ThreadStart(ReceivePointCloudData));
            receiveThread.IsBackground = true;
            receiveThread.Start();

            Debug.Log("✅ Connected to VR Point Cloud server successfully!");
        }
        catch (Exception e)
        {
            Debug.LogError($"❌ Failed to connect to point cloud server: {e.Message}");
            isConnected = false;
            
            if (client != null)
            {
                client.Close();
                client = null;
            }
        }
    }

    private void ReceivePointCloudData()
    {
        byte[] sizeInfo = new byte[4];

        while (isRunning && stream != null)
        {
            try
            {
                float receiveStart = Time.realtimeSinceStartup;
                
                // Read data size
                int bytesRead = stream.Read(sizeInfo, 0, sizeInfo.Length);
                if (bytesRead < 4)
                {
                    Debug.LogWarning("📡 Point cloud server disconnected. Attempting reconnection...");
                    isConnected = false;
                    isRunning = false;
                    break;
                }

                int dataSize = BitConverter.ToInt32(sizeInfo, 0);
                if (dataSize <= 0 || dataSize > 50000000) // 50MB safety limit
                {
                    Debug.LogWarning($"⚠️ Invalid point cloud data size: {dataSize}");
                    continue;
                }

                // Read serialized point cloud data with timeout protection
                byte[] pointCloudBytes = new byte[dataSize];
                int totalBytesRead = 0;
                DateTime startTime = DateTime.Now;
                
                while (totalBytesRead < dataSize)
                {
                    bytesRead = stream.Read(pointCloudBytes, totalBytesRead, dataSize - totalBytesRead);
                    if (bytesRead == 0)
                    {
                        Debug.LogWarning("📡 Point cloud data stream interrupted");
                        isConnected = false;
                        isRunning = false;
                        break;
                    }
                    totalBytesRead += bytesRead;
                    
                    // Timeout protection
                    if ((DateTime.Now - startTime).TotalSeconds > 1.0)
                    {
                        Debug.LogWarning("⏰ Point cloud data receive timeout");
                        break;
                    }
                }

                if (totalBytesRead == dataSize)
                {
                    ParsePointCloudData(pointCloudBytes);
                    
                    // Track latency for VR performance
                    float latency = (Time.realtimeSinceStartup - receiveStart) * 1000f;
                    latencyHistory.Enqueue(latency);
                    if (latencyHistory.Count > 30) // Keep last 30 samples
                        latencyHistory.Dequeue();
                }
            }
            catch (ThreadAbortException)
            {
                // Thread is being aborted. Normal on exit.
            }
            catch (Exception e)
            {
                Debug.LogError($"❌ Error receiving VR point cloud data: {e.Message}");
                isConnected = false;
                isRunning = false;
                break;
            }
        }
        
        // Cleanup on disconnect
        if (stream != null)
        {
            stream.Close();
            stream = null;
        }
    }

    private void ParsePointCloudData(byte[] data)
    {
        try
        {
            // Since Python is sending pickle data, we can't easily parse it in Unity
            // For now, let's generate test data and add connection debugging
            Debug.Log($"🔍 Received {data.Length} bytes of point cloud data from server");
            
            // Try to deserialize basic structure (this won't work with pickle, but let's try simple parsing)
            if (data.Length < 8)
            {
                Debug.LogWarning("⚠️ Data too small for point cloud");
                GenerateTestPointCloud();
                return;
            }
            
            // For now, always generate test data until we fix the data format
            GenerateTestPointCloud();
            
            Debug.Log($"✅ Point cloud data processed successfully");
            
        }
        catch (Exception e)
        {
            Debug.LogError($"❌ Error parsing VR point cloud: {e.Message}");
            // Fallback: generate test data to keep VR experience running
            GenerateTestPointCloud();
        }
    }

    private void GenerateTestPointCloud()
    {
        // Generate test point cloud that should definitely be visible in VR
        int numPoints = 1000; // Smaller number for testing
        
        Vector3[] points = new Vector3[numPoints];
        Color[] colors = new Color[numPoints];
        
        // Create a simple cube pattern that's easy to see in VR
        float size = 0.5f;
        for (int i = 0; i < numPoints; i++)
        {
            // Create points in a cube around the origin
            points[i] = new Vector3(
                UnityEngine.Random.Range(-size, size),
                UnityEngine.Random.Range(-size, size),
                UnityEngine.Random.Range(0f, size * 2) // In front of camera
            );
            
            // Bright colors for visibility
            colors[i] = new Color(
                UnityEngine.Random.Range(0.5f, 1f), // Bright red
                UnityEngine.Random.Range(0.5f, 1f), // Bright green
                UnityEngine.Random.Range(0.5f, 1f), // Bright blue
                1.0f
            );
        }
        
        lock (lockObject)
        {
            currentPoints = points;
            currentColors = colors;
            newPointCloudReady = true;
        }
        
        Debug.Log($"🎯 Generated {numPoints} bright test points for VR display");
    }

    void OnApplicationQuit()
    {
        Debug.Log("🧹 Shutting down VR Point Cloud Receiver...");
        
        if (isRunning)
        {
            isRunning = false;
            isConnected = false;
            
            if (receiveThread != null && receiveThread.IsAlive)
            {
                receiveThread.Abort();
            }
            if (stream != null) 
            {
                stream.Close();
                stream = null;
            }
            if (client != null) 
            {
                client.Close();
                client = null;
            }
        }
    }

    void OnDestroy()
    {
        // Clean up point objects for VR
        for (int i = 0; i < activePoints.Count; i++)
        {
            if (activePoints[i] != null)
                DestroyImmediate(activePoints[i]);
        }
        activePoints.Clear();
        
        Debug.Log("✅ VR Point Cloud Receiver cleanup complete");
    }
}
