using UnityEngine;
using System.Net.Sockets;
using System.Threading;
using System;
using System.IO;

public class DesktopVideoStreamReceiver : MonoBehaviour
{
    [Header("Network Settings")]
    public string serverAddress = "127.0.0.1"; // localhost for desktop testing
    public int serverPort = 8080;

    [Header("Display Settings")]
    [Tooltip("The camera to position relative to (leave empty to use as standalone window)")]
    public Camera targetCamera;
    [Tooltip("Position offset from camera (only used if targetCamera is set)")]
    public Vector3 positionOffset = new Vector3(0, 0, 3f);
    [Tooltip("Scale of the video quad")]
    public float videoScale = 2.0f;
    [Tooltip("Use this for standalone desktop testing")]
    public bool standaloneMode = true;

    private TcpClient client;
    private NetworkStream stream;
    private Thread receiveThread;
    private bool isRunning = false;

    private byte[] receivedBytes;
    private readonly object lockObject = new object();
    private bool newFrameReady = false;

    private Texture2D receivedTexture;
    private Renderer quadRenderer;

    void Start()
    {
        // Create a simple quad to display the video
        if (GetComponent<MeshRenderer>() == null)
        {
            CreateVideoQuad();
        }

        quadRenderer = GetComponent<Renderer>();
        receivedTexture = new Texture2D(2, 2);
        quadRenderer.material.mainTexture = receivedTexture;

        // Set initial position and scale
        if (standaloneMode)
        {
            // Position for desktop viewing
            transform.position = new Vector3(0, 0, 5);
            transform.localScale = Vector3.one * videoScale;
            
            // Create a camera if none exists
            if (Camera.main == null)
            {
                GameObject cameraObj = new GameObject("Main Camera");
                cameraObj.AddComponent<Camera>();
                cameraObj.tag = "MainCamera";
                cameraObj.transform.position = new Vector3(0, 0, 0);
            }
        }

        StartConnection();
    }

    void CreateVideoQuad()
    {
        // Add mesh components
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

        // Create material
        Material videoMaterial = new Material(Shader.Find("Unlit/Texture"));
        meshRenderer.material = videoMaterial;
    }

    void Update()
    {
        // Update position relative to target camera if in VR mode
        if (!standaloneMode && targetCamera != null)
        {
            transform.position = targetCamera.transform.position + 
                                 targetCamera.transform.forward * positionOffset.z + 
                                 targetCamera.transform.right * positionOffset.x + 
                                 targetCamera.transform.up * positionOffset.y;
            
            transform.LookAt(targetCamera.transform);
        }

        // Update video texture if new frame is available
        if (newFrameReady)
        {
            lock (lockObject)
            {
                if (receivedBytes != null && receivedBytes.Length > 0)
                {
                    receivedTexture.LoadImage(receivedBytes);
                    
                    // Adjust quad scale to match video aspect ratio
                    float aspectRatio = (float)receivedTexture.width / receivedTexture.height;
                    if (standaloneMode)
                    {
                        transform.localScale = new Vector3(videoScale * aspectRatio, videoScale, 1);
                    }
                }
                newFrameReady = false;
            }
        }

        // Handle input for standalone mode
        if (standaloneMode)
        {
            HandleDesktopInput();
        }
    }

    void HandleDesktopInput()
    {
        // Mouse controls for desktop testing
        if (Input.GetMouseButton(0))
        {
            float rotationSpeed = 2.0f;
            float mouseX = Input.GetAxis("Mouse X") * rotationSpeed;
            float mouseY = Input.GetAxis("Mouse Y") * rotationSpeed;

            Camera.main.transform.Rotate(-mouseY, mouseX, 0);
        }

        // Keyboard controls
        float moveSpeed = 5.0f * Time.deltaTime;
        if (Input.GetKey(KeyCode.W)) Camera.main.transform.Translate(0, 0, moveSpeed);
        if (Input.GetKey(KeyCode.S)) Camera.main.transform.Translate(0, 0, -moveSpeed);
        if (Input.GetKey(KeyCode.A)) Camera.main.transform.Translate(-moveSpeed, 0, 0);
        if (Input.GetKey(KeyCode.D)) Camera.main.transform.Translate(moveSpeed, 0, 0);
        if (Input.GetKey(KeyCode.Q)) Camera.main.transform.Translate(0, -moveSpeed, 0);
        if (Input.GetKey(KeyCode.E)) Camera.main.transform.Translate(0, moveSpeed, 0);

        // Reset position
        if (Input.GetKeyDown(KeyCode.R))
        {
            Camera.main.transform.position = Vector3.zero;
            Camera.main.transform.rotation = Quaternion.identity;
        }

        // Zoom
        float scroll = Input.GetAxis("Mouse ScrollWheel");
        videoScale += scroll * 0.5f;
        videoScale = Mathf.Clamp(videoScale, 0.5f, 10f);
        
        float aspectRatio = receivedTexture != null ? (float)receivedTexture.width / receivedTexture.height : 1f;
        transform.localScale = new Vector3(videoScale * aspectRatio, videoScale, 1);
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

            receiveThread = new Thread(new ThreadStart(ReceiveData));
            receiveThread.IsBackground = true;
            receiveThread.Start();

            Debug.Log($"Connected to video server at {serverAddress}:{serverPort}");
            
            if (standaloneMode)
            {
                Debug.Log("Desktop Controls:");
                Debug.Log("- Mouse + Left Click: Look around");
                Debug.Log("- WASD: Move camera");
                Debug.Log("- Q/E: Move up/down");
                Debug.Log("- Mouse Wheel: Zoom video");
                Debug.Log("- R: Reset camera position");
            }
        }
        catch (Exception e)
        {
            Debug.LogError($"Connection error: {e.Message}");
            Debug.LogError("Make sure the Python video server is running!");
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
                    Debug.LogWarning("Server disconnected.");
                    isRunning = false;
                    break;
                }

                int frameSize = BitConverter.ToInt32(sizeInfo, 0);
                if (frameSize <= 0) continue;

                byte[] frameData = new byte[frameSize];
                int totalBytesRead = 0;
                while (totalBytesRead < frameSize)
                {
                    bytesRead = stream.Read(frameData, totalBytesRead, frameSize - totalBytesRead);
                    if (bytesRead == 0)
                    {
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
                Debug.LogError($"Error receiving data: {e.Message}");
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
