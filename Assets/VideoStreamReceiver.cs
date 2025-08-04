using UnityEngine;
using System.Net.Sockets;
using System.Threading;
using System;
using System.IO;
using System.Net;

public class VideoStreamReceiver : MonoBehaviour
{
    public string serverAddress = "192.168.0.196"; // Change to your PC's IP address
    public int serverPort = 8080;
    public int pingPort = 8081; // UDP port for latency measurement

    private TcpClient client;
    private NetworkStream stream;
    private Thread receiveThread;
    private UdpClient pingClient;
    private Thread pingThread;
    private bool isRunning = false;

    private byte[] receivedBytes;
    private object lockObject = new object();
    private bool newFrameReady = false;

    private Texture2D receivedTexture;

    void Start()
    {
        Debug.Log($"🎬 VideoStreamReceiver starting - connecting to {serverAddress}:{serverPort}");
        receivedTexture = new Texture2D(2, 2);
        GetComponent<Renderer>().material.mainTexture = receivedTexture;
        StartConnection();
    }

    void Update()
    {
        if (newFrameReady)
        {
            lock (lockObject)
            {
                if (receivedBytes != null)
                {
                    receivedTexture.LoadImage(receivedBytes);
                }
                newFrameReady = false;
            }
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
            Debug.Log($"🔄 Attempting to connect to {serverAddress}:{serverPort}...");
            client = new TcpClient(serverAddress, serverPort);
            stream = client.GetStream();
            isRunning = true;

            receiveThread = new Thread(new ThreadStart(ReceiveData));
            receiveThread.IsBackground = true;
            receiveThread.Start();
            
            // Start the ping client thread
            pingThread = new Thread(new ThreadStart(PingService));
            pingThread.IsBackground = true;
            pingThread.Start();

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
        // Simplified: Header is just 4 bytes for frame size
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
            catch (IOException ioex)
            {
                Debug.LogWarning($"Socket error in ReceiveData: {ioex.Message}");
                break;
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

    private void PingService()
    {
        try
        {
            pingClient = new UdpClient();
            IPEndPoint serverEndPoint = new IPEndPoint(IPAddress.Parse(serverAddress), pingPort);

            // Send an initial message to let the server know our address
            byte[] initialMessage = new byte[] { 1 };
            pingClient.Send(initialMessage, initialMessage.Length, serverEndPoint);

            while (isRunning)
            {
                // Wait to receive a ping (timestamp)
                IPEndPoint remoteEP = new IPEndPoint(IPAddress.Any, 0);
                byte[] receivedData = pingClient.Receive(ref remoteEP);

                // Immediately send it back
                pingClient.Send(receivedData, receivedData.Length, serverEndPoint);
            }
        }
        catch (Exception e)
        {
            if(isRunning)
            {
                Debug.LogError($"Ping service error: {e.Message}");
            }
        }
        finally
        {
            if(pingClient != null)
            {
                pingClient.Close();
            }
        }
    }

    void OnDestroy()
    {
        if (isRunning)
        {
            isRunning = false;
            
            if (receiveThread != null) receiveThread.Join();
            if (pingThread != null) pingThread.Abort(); // Abort is okay for the ping thread

            if (stream != null) stream.Close();
            if (client != null) client.Close();
            if (pingClient != null) pingClient.Close();
        }
    }
}
