using UnityEngine;
using System.Net.Sockets;
using System.Threading;
using System;
using System.Collections.Generic;

public class EfficientPointCloudReceiver : MonoBehaviour
{
    [Header("Network Settings")]
    public string serverAddress = "192.168.0.196";
    public int serverPort = 8081;

    [Header("Display Settings")]
    public Camera mainCamera;
    public Vector3 positionOffset = new Vector3(0, 0, 3f);
    public float pointCloudScale = 1.0f;
    public float pointSize = 0.02f;

    [Header("Point Cloud Rendering")]
    public Material pointMaterial;
    public Mesh pointMesh; // Use a simple quad or sphere mesh
    public int maxPointsToRender = 15000;

    private TcpClient client;
    private NetworkStream stream;
    private Thread receiveThread;
    private bool isRunning = false;

    private readonly object lockObject = new object();
    private bool newPointCloudReady = false;

    // Efficient rendering data
    private Matrix4x4[] pointMatrices;
    private Vector4[] pointColors;
    private MaterialPropertyBlock propertyBlock;

    void Start()
    {
        if (mainCamera == null)
            mainCamera = Camera.main;

        // Create default point mesh (small sphere)
        if (pointMesh == null)
        {
            pointMesh = CreatePointMesh();
        }

        // Create default material
        if (pointMaterial == null)
        {
            pointMaterial = CreatePointMaterial();
        }

        propertyBlock = new MaterialPropertyBlock();
        StartConnection();
    }

    Mesh CreatePointMesh()
    {
        // Create a simple quad mesh for points
        Mesh mesh = new Mesh();
        
        Vector3[] vertices = new Vector3[]
        {
            new Vector3(-0.5f, -0.5f, 0),
            new Vector3( 0.5f, -0.5f, 0),
            new Vector3( 0.5f,  0.5f, 0),
            new Vector3(-0.5f,  0.5f, 0)
        };

        Vector2[] uvs = new Vector2[]
        {
            new Vector2(0, 0),
            new Vector2(1, 0),
            new Vector2(1, 1),
            new Vector2(0, 1)
        };

        int[] triangles = new int[] { 0, 1, 2, 2, 3, 0 };

        mesh.vertices = vertices;
        mesh.uv = uvs;
        mesh.triangles = triangles;
        mesh.RecalculateNormals();

        return mesh;
    }

    Material CreatePointMaterial()
    {
        // Create a simple unlit material for better performance
        Material mat = new Material(Shader.Find("Unlit/Color"));
        mat.color = Color.white;
        return mat;
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

        // Render point cloud if new data is available
        if (newPointCloudReady)
        {
            lock (lockObject)
            {
                if (pointMatrices != null && pointMatrices.Length > 0)
                {
                    RenderPointCloud();
                }
                newPointCloudReady = false;
            }
        }
    }

    void RenderPointCloud()
    {
        if (pointMatrices == null || pointMatrices.Length == 0)
            return;

        // Render points in batches (Unity has a limit of 1023 instances per call)
        int batchSize = 1000;
        int pointCount = pointMatrices.Length;

        for (int i = 0; i < pointCount; i += batchSize)
        {
            int currentBatchSize = Mathf.Min(batchSize, pointCount - i);
            
            // Create batch arrays
            Matrix4x4[] batchMatrices = new Matrix4x4[currentBatchSize];
            System.Array.Copy(pointMatrices, i, batchMatrices, 0, currentBatchSize);

            // Render batch
            Graphics.DrawMeshInstanced(
                pointMesh, 
                0, 
                pointMaterial, 
                batchMatrices, 
                currentBatchSize,
                propertyBlock
            );
        }
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
                    Debug.LogWarning("Server disconnected.");
                    isRunning = false;
                    break;
                }

                int dataSize = BitConverter.ToInt32(sizeInfo, 0);
                if (dataSize <= 0) continue;

                // Read point cloud data
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
                    // For now, generate test data
                    // In production, you'd deserialize the actual point cloud data here
                    GenerateTestPointCloud();
                }
            }
            catch (ThreadAbortException)
            {
                break;
            }
            catch (Exception e)
            {
                Debug.LogError("Error receiving point cloud data: " + e.Message);
                isRunning = false;
            }
        }
    }

    private void GenerateTestPointCloud()
    {
        // Generate test point cloud data
        int numPoints = Mathf.Min(UnityEngine.Random.Range(5000, 10000), maxPointsToRender);
        
        Matrix4x4[] matrices = new Matrix4x4[numPoints];
        
        for (int i = 0; i < numPoints; i++)
        {
            Vector3 position = new Vector3(
                UnityEngine.Random.Range(-2f, 2f),
                UnityEngine.Random.Range(-1f, 1f),
                UnityEngine.Random.Range(0.5f, 3f)
            );

            Vector3 scale = Vector3.one * pointSize;
            
            matrices[i] = Matrix4x4.TRS(
                transform.TransformPoint(position * pointCloudScale), 
                transform.rotation, 
                scale
            );
        }
        
        lock (lockObject)
        {
            pointMatrices = matrices;
            newPointCloudReady = true;
        }
        
        Debug.Log($"Generated {numPoints} point cloud points");
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
}
