using UnityEngine;
using System.Net.Sockets;
using System.Threading;
using System;
using System.IO;

/// <summary>
/// Oculus Link-optimized video receiver for instant VR testing
/// This allows you to test in Unity Editor Play mode with Quest 3 via Oculus Link
/// No more Android builds - just hit Play in Unity Editor!
/// </summary>
public class OculusLinkVideoReceiver : MonoBehaviour
{
    [Header("Network Settings")]
    public string serverAddress = "127.0.0.1"; // localhost - Python server on same PC
    public int serverPort = 8080;

    [Header("VR Display Settings")]
    [Tooltip("Distance from player/camera")]
    public float displayDistance = 3.0f;
    [Tooltip("Size of the video display")]
    public float displayScale = 2.0f;
    [Tooltip("Follow head movement smoothly")]
    public bool followHead = true;
    [Tooltip("Smooth following speed")]
    public float followSpeed = 2.0f;

    [Header("Debug Settings")]
    public bool showDebugInfo = true;
    public bool autoReconnect = true;
    public float reconnectDelay = 2.0f;

    private TcpClient client;
    private NetworkStream stream;
    private Thread receiveThread;
    private bool isRunning = false;
    private bool isConnected = false;

    private byte[] receivedBytes;
    private readonly object lockObject = new object();
    private bool newFrameReady = false;

    private Texture2D receivedTexture;
    private Renderer quadRenderer;
    private Transform playerHead;
    private Vector3 targetPosition;

    // Debug info
    private int framesReceived = 0;
    private float lastFrameTime;
    private float fps = 0;

    void Start()
    {
        // Create video display quad
        SetupVideoQuad();
        
        // Find the main camera (VR head)
        playerHead = Camera.main?.transform;
        if (playerHead == null)
        {
            // Fallback for VR - look for center eye anchor
            GameObject centerEye = GameObject.Find("CenterEyeAnchor");
            if (centerEye != null)
                playerHead = centerEye.transform;
        }

        // Start connection
        StartConnection();
        
        if (showDebugInfo)
        {
            Debug.Log("=== OCULUS LINK VIDEO RECEIVER STARTED ===");
            Debug.Log("1. Make sure your Quest 3 is connected via Oculus Link");
            Debug.Log("2. Make sure Python realsense_stream_server.py is running");
            Debug.Log("3. Hit Play in Unity Editor - no Android build needed!");
            Debug.Log("4. Changes to Python server will reconnect automatically");
        }
    }

    void SetupVideoQuad()
    {
        // Add mesh components if not present
        if (GetComponent<MeshRenderer>() == null)
        {
            MeshFilter meshFilter = gameObject.AddComponent<MeshFilter>();
            MeshRenderer meshRenderer = gameObject.AddComponent<MeshRenderer>();

            // Create quad mesh
            Mesh quadMesh = new Mesh();
            Vector3[] vertices = new Vector3[]
            {
                new Vector3(-1, -1, 0),
                new Vector3( 1, -1, 0),
                new Vector3( 1,  1, 0),
                new Vector3(-1,  1, 0)
            };

            Vector2[] uvs = new Vector2[]
            {
                new Vector2(0, 0),
                new Vector2(1, 0),
                new Vector2(1, 1),
                new Vector2(0, 1)
            };

            int[] triangles = new int[] { 0, 1, 2, 2, 3, 0 };

            quadMesh.vertices = vertices;
            quadMesh.uv = uvs;
            quadMesh.triangles = triangles;
            quadMesh.RecalculateNormals();

            meshFilter.mesh = quadMesh;

            // Create unlit material for video
            Material videoMaterial = new Material(Shader.Find("Unlit/Texture"));
            meshRenderer.material = videoMaterial;
        }

        quadRenderer = GetComponent<Renderer>();
        receivedTexture = new Texture2D(2, 2);
        quadRenderer.material.mainTexture = receivedTexture;
    }

    void Update()
    {
        // Update position to follow head in VR
        UpdateVideoPosition();

        // Process new video frames
        if (newFrameReady)
        {
            UpdateVideoTexture();
        }

        // Auto-reconnect if disconnected
        if (autoReconnect && !isConnected && !isRunning)
        {
            if (Time.time - lastFrameTime > reconnectDelay)
            {
                if (showDebugInfo)
                    Debug.Log("Auto-reconnecting to video server...");
                StartConnection();
            }
        }

        // Update debug info
        if (showDebugInfo && Time.time - lastFrameTime > 1.0f)
        {
            fps = framesReceived / (Time.time - lastFrameTime);
            if (isConnected)
                Debug.Log($"Video FPS: {fps:F1} | Frames: {framesReceived}");
            framesReceived = 0;
            lastFrameTime = Time.time;
        }
    }

    void UpdateVideoPosition()
    {
        if (playerHead == null) return;

        if (followHead)
        {
            // Position video in front of player
            targetPosition = playerHead.position + playerHead.forward * displayDistance;
            transform.position = Vector3.Lerp(transform.position, targetPosition, followSpeed * Time.deltaTime);
            
            // Make video face the player
            Vector3 lookDirection = playerHead.position - transform.position;
            transform.rotation = Quaternion.LookRotation(-lookDirection, Vector3.up);
        }
        else
        {
            // Fixed position relative to head
            transform.position = playerHead.position + playerHead.forward * displayDistance;
            transform.LookAt(playerHead);
        }
    }

    void UpdateVideoTexture()
    {
        lock (lockObject)
        {
            if (receivedBytes != null && receivedBytes.Length > 0)
            {
                try
                {
                    receivedTexture.LoadImage(receivedBytes);
                    
                    // Adjust scale to maintain aspect ratio
                    float aspectRatio = (float)receivedTexture.width / receivedTexture.height;
                    transform.localScale = new Vector3(displayScale * aspectRatio, displayScale, 1);
                    
                    framesReceived++;
                }
                catch (Exception e)
                {
                    Debug.LogError($"Error loading video frame: {e.Message}");
                }
            }
            newFrameReady = false;
        }
    }

    void StartConnection()
    {
        if (isRunning)
        {
            if (showDebugInfo)
                Debug.LogWarning("Already connecting/connected.");
            return;
        }

        try
        {
            client = new TcpClient();
            client.ReceiveTimeout = 5000; // 5 second timeout
            client.SendTimeout = 5000;
            
            // Connect asynchronously to avoid blocking
            var result = client.BeginConnect(serverAddress, serverPort, null, null);
            bool success = result.AsyncWaitHandle.WaitOne(TimeSpan.FromSeconds(3));
            
            if (success)
            {
                client.EndConnect(result);
                stream = client.GetStream();
                isRunning = true;
                isConnected = true;

                receiveThread = new Thread(new ThreadStart(ReceiveData));
                receiveThread.IsBackground = true;
                receiveThread.Start();

                if (showDebugInfo)
                {
                    Debug.Log($"✓ Connected to video server at {serverAddress}:{serverPort}");
                    Debug.Log("✓ Video streaming to Oculus Link - no Android build needed!");
                }
            }
            else
            {
                isConnected = false;
                if (showDebugInfo)
                    Debug.LogWarning($"Connection timeout to {serverAddress}:{serverPort}");
                client.Close();
            }
        }
        catch (Exception e)
        {
            isConnected = false;
            if (showDebugInfo)
            {
                Debug.LogError($"Connection error: {e.Message}");
                Debug.LogError("Make sure Python realsense_stream_server.py is running!");
            }
        }
    }

    private void ReceiveData()
    {
        byte[] sizeInfo = new byte[4];

        while (isRunning && stream != null)
        {
            try
            {
                int bytesRead = stream.Read(sizeInfo, 0, sizeInfo.Length);
                if (bytesRead < 4)
                {
                    if (showDebugInfo)
                        Debug.LogWarning("Video server disconnected - will auto-reconnect");
                    isConnected = false;
                    isRunning = false;
                    break;
                }

                int frameSize = BitConverter.ToInt32(sizeInfo, 0);
                if (frameSize <= 0 || frameSize > 10000000) // Max 10MB frame
                {
                    if (showDebugInfo)
                        Debug.LogWarning($"Invalid frame size: {frameSize}");
                    continue;
                }

                byte[] frameData = new byte[frameSize];
                int totalBytesRead = 0;
                while (totalBytesRead < frameSize && isRunning)
                {
                    bytesRead = stream.Read(frameData, totalBytesRead, frameSize - totalBytesRead);
                    if (bytesRead == 0)
                    {
                        isConnected = false;
                        isRunning = false;
                        break;
                    }
                    totalBytesRead += bytesRead;
                }

                if (totalBytesRead == frameSize)
                {
                    lock (lockObject)
                    {
                        receivedBytes = frameData;
                        newFrameReady = true;
                    }
                }
            }
            catch (ThreadAbortException)
            {
                break;
            }
            catch (Exception e)
            {
                if (showDebugInfo)
                    Debug.LogError($"Error receiving video data: {e.Message}");
                isConnected = false;
                isRunning = false;
            }
        }
    }

    void OnApplicationQuit()
    {
        Cleanup();
    }

    void OnDestroy()
    {
        Cleanup();
    }

    void Cleanup()
    {
        if (showDebugInfo)
            Debug.Log("Cleaning up video connection...");
            
        isRunning = false;
        isConnected = false;
        
        if (receiveThread != null && receiveThread.IsAlive)
        {
            receiveThread.Abort();
        }
        if (stream != null) stream.Close();
        if (client != null) client.Close();
    }

    // Public methods for debugging
    public void ForceReconnect()
    {
        Cleanup();
        System.Threading.Thread.Sleep(500);
        StartConnection();
    }

    public string GetStatus()
    {
        return $"Connected: {isConnected} | Running: {isRunning} | FPS: {fps:F1}";
    }
}
