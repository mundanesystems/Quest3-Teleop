using UnityEngine;
using System.Net.Sockets;
using System.Threading;
using System;

/// <summary>
/// Simple video receiver - minimal version that should compile without issues
/// </summary>
public class SimpleVideoReceiver : MonoBehaviour
{
    public string serverAddress = "127.0.0.1";
    public int serverPort = 8080;
    
    private TcpClient client;
    private NetworkStream stream;
    private Thread receiveThread;
    private bool isRunning = false;
    
    private byte[] receivedBytes;
    private object lockObject = new object();
    private bool newFrameReady = false;
    private Texture2D receivedTexture;

    void Start()
    {
        Debug.Log("=== SIMPLE VIDEO RECEIVER STARTED ===");
        
        // Create texture and assign to renderer
        receivedTexture = new Texture2D(2, 2);
        
        // Add components if needed
        if (GetComponent<MeshRenderer>() == null)
        {
            gameObject.AddComponent<MeshFilter>();
            gameObject.AddComponent<MeshRenderer>();
            
            // Create simple quad
            GetComponent<MeshFilter>().mesh = CreateQuad();
            GetComponent<MeshRenderer>().material = new Material(Shader.Find("Unlit/Texture"));
        }
        
        GetComponent<Renderer>().material.mainTexture = receivedTexture;
        
        // Position in front of camera
        transform.position = new Vector3(0, 0, 5);
        transform.localScale = Vector3.one * 2;
        
        StartConnection();
    }

    Mesh CreateQuad()
    {
        Mesh mesh = new Mesh();
        mesh.vertices = new Vector3[]
        {
            new Vector3(-1, -1, 0), new Vector3(1, -1, 0),
            new Vector3(1, 1, 0), new Vector3(-1, 1, 0)
        };
        mesh.uv = new Vector2[]
        {
            new Vector2(0, 0), new Vector2(1, 0),
            new Vector2(1, 1), new Vector2(0, 1)
        };
        mesh.triangles = new int[] { 0, 1, 2, 2, 3, 0 };
        return mesh;
    }

    void Update()
    {
        if (newFrameReady)
        {
            lock (lockObject)
            {
                if (receivedBytes != null && receivedBytes.Length > 0)
                {
                    receivedTexture.LoadImage(receivedBytes);
                }
                newFrameReady = false;
            }
        }
    }

    void StartConnection()
    {
        try
        {
            client = new TcpClient(serverAddress, serverPort);
            stream = client.GetStream();
            isRunning = true;

            receiveThread = new Thread(ReceiveData);
            receiveThread.IsBackground = true;
            receiveThread.Start();

            Debug.Log($"✓ Connected to video server at {serverAddress}:{serverPort}");
        }
        catch (Exception e)
        {
            Debug.LogError($"Connection error: {e.Message}");
        }
    }

    void ReceiveData()
    {
        byte[] sizeInfo = new byte[4];

        while (isRunning && stream != null)
        {
            try
            {
                int bytesRead = stream.Read(sizeInfo, 0, 4);
                if (bytesRead < 4) break;

                int frameSize = System.BitConverter.ToInt32(sizeInfo, 0);
                if (frameSize <= 0 || frameSize > 5000000) continue;

                byte[] frameData = new byte[frameSize];
                int totalRead = 0;
                while (totalRead < frameSize)
                {
                    bytesRead = stream.Read(frameData, totalRead, frameSize - totalRead);
                    if (bytesRead == 0) break;
                    totalRead += bytesRead;
                }

                if (totalRead == frameSize)
                {
                    lock (lockObject)
                    {
                        receivedBytes = frameData;
                        newFrameReady = true;
                    }
                }
            }
            catch (Exception)
            {
                break;
            }
        }
    }

    void OnDestroy()
    {
        isRunning = false;
        if (stream != null) stream.Close();
        if (client != null) client.Close();
    }
}
