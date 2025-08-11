using System;
using System.Net.Sockets;
using System.Threading;
using UnityEngine;


using System.Net;
using System.Net.Sockets;

public class StereoUDPReceiver : MonoBehaviour
{
    public string serverAddress = "192.168.0.196";
    public int serverPort = 8080;
    public int pingPort = 8081;
    public int imageWidth = 2560; // Set to expected panorama width
    public int imageHeight = 720; // Set to expected panorama height

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
        Debug.Log($"StereoTCPReceiver starting - sending UDP ping to {serverAddress}:{pingPort}");
        // Send UDP ping to server to trigger handshake
        try
        {
            UdpClient pingClient = new UdpClient();
            IPEndPoint serverEndPoint = new IPEndPoint(IPAddress.Parse(serverAddress), pingPort);
            byte[] pingMsg = System.Text.Encoding.ASCII.GetBytes("ping");
            pingClient.Send(pingMsg, pingMsg.Length, serverEndPoint);
            pingClient.Close();
            Debug.Log($"Sent initial UDP ping to {serverAddress}:{pingPort}");
        }
        catch (Exception ex)
        {
            Debug.LogWarning("Failed to send initial UDP ping: " + ex.Message);
        }

    receivedTexture = new Texture2D(2, 2);
    GetComponent<Renderer>().material.mainTexture = receivedTexture;

    // Adjust quad width to match panoramic aspect ratio
    float aspect = (float)imageWidth / (float)imageHeight;
    Vector3 scale = transform.localScale;
    scale.x = scale.y * aspect * (2f/3f); // Decrease width by 1/3
    transform.localScale = scale;

    StartConnection();
    }

    private void StartConnection()
    {
        if (isRunning)
        {
            Debug.LogWarning("Already connected.");
            return;
        }

        try
        {
            Debug.Log($"🔄 Attempting to connect to {serverAddress}:{serverPort}...");
            client = new TcpClient(serverAddress, serverPort);
            stream = client.GetStream();
            isRunning = true;

            receiveThread = new Thread(new ThreadStart(ReceiveData));
            receiveThread.IsBackground = true;
            receiveThread.Start();

            Debug.Log("✅ Connected to video streaming server successfully!");
        }
        catch (Exception e)
        {
            Debug.LogError($"❌ Failed to connect to video server: {e.Message}");
            Debug.LogError($"   Make sure server is running at {serverAddress}:{serverPort}");
        }
    }

    private void ReceiveData()
    {
        // Header is 4 bytes for frame size
        byte[] sizeInfo = new byte[4];

        while (isRunning)
        {
            try
            {
                int bytesRead = 0;
                int totalHeaderBytesRead = 0;
                while(totalHeaderBytesRead < sizeInfo.Length)
                {
                    bytesRead = stream.Read(sizeInfo, totalHeaderBytesRead, sizeInfo.Length - totalHeaderBytesRead);
                    if (bytesRead == 0) {
                        Debug.LogWarning("Connection closed while reading header.");
                        isRunning = false;
                        break;
                    }
                    totalHeaderBytesRead += bytesRead;
                }

                if (!isRunning) break;

                if (totalHeaderBytesRead == 4)
                {
                    int frameSize = BitConverter.ToInt32(sizeInfo, 0);
                    byte[] frameData = new byte[frameSize];
                    int totalBytesRead = 0;
                    while (totalBytesRead < frameSize)
                    {
                        bytesRead = stream.Read(frameData, totalBytesRead, frameSize - totalBytesRead);
                        if (bytesRead == 0)
                        {
                            Debug.LogWarning("Connection closed while reading frame data.");
                            isRunning = false;
                            break;
                        }
                        totalBytesRead += bytesRead;
                    }

                    if (!isRunning) break;

                    if (totalBytesRead == frameSize)
                    {
                        lock (lockObject)
                        {
                            receivedBytes = frameData;
                            newFrameReady = true;
                        }
                    }
                }
            }
            catch (Exception e)
            {
                if (isRunning)
                {
                    Debug.LogError($"Error in ReceiveData: {e.Message}");
                }
                break;
            }
        }
    }

    void Update()
    {
        if (newFrameReady)
        {
            lock (lockObject)
            {
                if (receivedBytes != null)
                {
                    bool loaded = receivedTexture.LoadImage(receivedBytes);
                    Debug.Log($"Frame received, LoadImage result: {loaded}, bytes: {receivedBytes.Length}");
                }
                newFrameReady = false;
            }
        }
    }

    void OnDestroy()
    {
        if (isRunning)
        {
            isRunning = false;
            if (receiveThread != null) receiveThread.Join();
            if (stream != null) stream.Close();
            if (client != null) client.Close();
        }
    }
}
