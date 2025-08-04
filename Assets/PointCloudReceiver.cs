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
    public int serverPort = 8081; // Different port from video stream

    [Header("Display Settings")]
    [Tooltip("The main camera for positioning")]
    public Camera mainCamera;
    [Tooltip("Position offset from camera")]
    public Vector3 positionOffset = new Vector3(0, 0, 3f);
    [Tooltip("Scale of the point cloud")]
    public float pointCloudScale = 1.0f;
    [Tooltip("Size of individual points")]
    public float pointSize = 0.01f;

    [Header("Point Cloud Settings")]
    public Material pointMaterial;
    public int maxPointsToRender = 10000;

    private TcpClient client;
    private NetworkStream stream;
    private Thread receiveThread;
    private bool isRunning = false;

    private byte[] receivedBytes;
    private readonly object lockObject = new object();
    private bool newPointCloudReady = false;

    private Vector3[] currentPoints;
    private Color[] currentColors;
    private GameObject[] pointObjects;
    private List<GameObject> activePoints = new List<GameObject>();

    void Start()
    {
        // Find the main camera if not assigned
        if (mainCamera == null)
        {
            mainCamera = Camera.main;
        }

        // Create default material if none assigned
        if (pointMaterial == null)
        {
            pointMaterial = new Material(Shader.Find("Standard"));
            pointMaterial.color = Color.white;
        }

        StartConnection();
    }

    void Update()
    {
        // Update position relative to camera
        if (mainCamera != null)
        {
            transform.position = mainCamera.transform.position + 
                                 mainCamera.transform.forward * positionOffset.z + 
                                 mainCamera.transform.right * positionOffset.x + 
                                 mainCamera.transform.up * positionOffset.y;
            
            transform.rotation = mainCamera.transform.rotation;
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
    }

    void UpdatePointCloudVisualization()
    {
        // Clear existing points
        foreach (GameObject point in activePoints)
        {
            if (point != null)
                DestroyImmediate(point);
        }
        activePoints.Clear();

        // Limit points for performance
        int pointsToRender = Mathf.Min(currentPoints.Length, maxPointsToRender);
        
        for (int i = 0; i < pointsToRender; i++)
        {
            // Create point as a small sphere
            GameObject pointObj = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            pointObj.transform.parent = transform;
            
            // Scale and position
            pointObj.transform.localPosition = currentPoints[i] * pointCloudScale;
            pointObj.transform.localScale = Vector3.one * pointSize;
            
            // Apply color
            Renderer renderer = pointObj.GetComponent<Renderer>();
            renderer.material = new Material(pointMaterial);
            renderer.material.color = currentColors[i];
            
            // Remove collider for performance
            Collider collider = pointObj.GetComponent<Collider>();
            if (collider != null)
                DestroyImmediate(collider);
            
            activePoints.Add(pointObj);
        }

        Debug.Log($"Rendered {pointsToRender} points");
    }

    void StartConnection()
    {
        if (isRunning)
        {
            Debug.LogWarning("Already connected.");
            return;
        }

        try
        {
            client = new TcpClient(serverAddress, serverPort);
            stream = client.GetStream();
            isRunning = true;

            receiveThread = new Thread(new ThreadStart(ReceivePointCloudData));
            receiveThread.IsBackground = true;
            receiveThread.Start();

            Debug.Log("Connected to point cloud server.");
        }
        catch (Exception e)
        {
            Debug.LogError("Socket error: " + e.Message);
        }
    }

    private void ReceivePointCloudData()
    {
        byte[] sizeInfo = new byte[4];

        while (isRunning && stream != null)
        {
            try
            {
                // Read data size
                int bytesRead = stream.Read(sizeInfo, 0, sizeInfo.Length);
                if (bytesRead < 4)
                {
                    Debug.LogWarning("Client disconnected.");
                    isRunning = false;
                    break;
                }

                int dataSize = BitConverter.ToInt32(sizeInfo, 0);
                if (dataSize <= 0) continue;

                // Read serialized point cloud data
                byte[] pointCloudBytes = new byte[dataSize];
                int totalBytesRead = 0;
                while (totalBytesRead < dataSize)
                {
                    bytesRead = stream.Read(pointCloudBytes, totalBytesRead, dataSize - totalBytesRead);
                    if (bytesRead == 0)
                    {
                        isRunning = false;
                        break;
                    }
                    totalBytesRead += bytesRead;
                }

                if (totalBytesRead == dataSize)
                {
                    // Parse the point cloud data (simplified JSON approach)
                    ParsePointCloudData(pointCloudBytes);
                }
            }
            catch (ThreadAbortException)
            {
                // Thread is being aborted. Normal on exit.
            }
            catch (Exception e)
            {
                Debug.LogError("Error receiving point cloud data: " + e.Message);
                isRunning = false;
            }
        }
    }

    private void ParsePointCloudData(byte[] data)
    {
        try
        {
            // For now, we'll use a simple binary format
            // This is a simplified version - in production you'd want to use a proper serialization
            
            // Convert binary data to string and parse as simple format
            string dataString = System.Text.Encoding.UTF8.GetString(data);
            
            // This is a placeholder - you'd implement proper deserialization here
            // For now, generate some test data
            GenerateTestPointCloud();
            
        }
        catch (Exception e)
        {
            Debug.LogError("Error parsing point cloud data: " + e.Message);
        }
    }

    private void GenerateTestPointCloud()
    {
        // Generate test point cloud for demonstration
        int numPoints = UnityEngine.Random.Range(1000, 5000);
        
        Vector3[] points = new Vector3[numPoints];
        Color[] colors = new Color[numPoints];
        
        for (int i = 0; i < numPoints; i++)
        {
            points[i] = new Vector3(
                UnityEngine.Random.Range(-1f, 1f),
                UnityEngine.Random.Range(-1f, 1f),
                UnityEngine.Random.Range(0f, 2f)
            );
            
            colors[i] = new Color(
                UnityEngine.Random.Range(0f, 1f),
                UnityEngine.Random.Range(0f, 1f),
                UnityEngine.Random.Range(0f, 1f)
            );
        }
        
        lock (lockObject)
        {
            currentPoints = points;
            currentColors = colors;
            newPointCloudReady = true;
        }
    }

    void OnApplicationQuit()
    {
        if (isRunning)
        {
            isRunning = false;
            if (receiveThread != null && receiveThread.IsAlive)
            {
                receiveThread.Abort();
            }
            if (stream != null) stream.Close();
            if (client != null) client.Close();
        }
    }

    void OnDestroy()
    {
        // Clean up point objects
        foreach (GameObject point in activePoints)
        {
            if (point != null)
                DestroyImmediate(point);
        }
        activePoints.Clear();
    }
}
