using UnityEngine;
using System.Net.Sockets;
using System.Threading;
using System;
using System.IO;

public class VideoStreamReceiver : MonoBehaviour
{
    public string serverAddress = "192.168.0.196"; // Change to your PC's IP address
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
        byte[] sizeInfo = new byte[4];

        while (isRunning)
        {
            try
            {
                int bytesRead = stream.Read(sizeInfo, 0, sizeInfo.Length);
                if (bytesRead == 0)
                {
                    // Connection closed
                    break;
                }

                if (bytesRead == 4)
                {
                    int frameSize = BitConverter.ToInt32(sizeInfo, 0);
                    byte[] frameData = new byte[frameSize];
                    int totalBytesRead = 0;
                    while (totalBytesRead < frameSize)
                    {
                        bytesRead = stream.Read(frameData, totalBytesRead, frameSize - totalBytesRead);
                        if (bytesRead == 0)
                        {
                            // Connection closed
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
            }
            catch (Exception e)
            {
                Debug.LogError("Error receiving data: " + e.Message);
                isRunning = false;
            }
        }
    }

    void OnApplicationQuit()
    {
        if (isRunning)
        {
            isRunning = false;
            receiveThread.Join();
            stream.Close();
            client.Close();
        }
    }
}
