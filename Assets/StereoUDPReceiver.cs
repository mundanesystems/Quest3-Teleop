using UnityEngine;
using System;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using System.Collections.Generic;
using System.Linq;

public class PassthroughUDPReceiver : MonoBehaviour
{
    [Header("Network Settings")]
    public string serverAddress = "192.168.0.196";
    public int serverPort = 8080;

    [Header("Display Settings")]
    public float screenDistance = 1.0f;

    private Thread clientThread;
    private bool isRunning = true;
    private UdpClient udpClient;

    private Texture2D videoTexture;
    private readonly object dataLock = new object();
    private bool newFrameReady = false;

    // --- JITTER BUFFER ---
    // A queue to hold incoming frames, smoothing out network jitter.
    private Queue<byte[]> frameQueue = new Queue<byte[]>();
    
    private Dictionary<uint, Dictionary<byte, byte[]>> frameBuffer = new Dictionary<uint, Dictionary<byte, byte[]>>();
    private Dictionary<uint, byte> totalChunksForFrame = new Dictionary<uint, byte>();
    private uint lastCompletedFrameId = 0;

    void Start()
    {
        videoTexture = new Texture2D(2, 2);
        GetComponent<Renderer>().material.mainTexture = videoTexture;

        float zedHorizontalFov = 90.0f; 
        float hFovRad = zedHorizontalFov * Mathf.Deg2Rad;
        float quadWidth = 2.0f * screenDistance * Mathf.Tan(hFovRad * 0.5f);
        float vFovRad = Camera.main.fieldOfView * Mathf.Deg2Rad;
        float quadHeight = 2.0f * screenDistance * Mathf.Tan(vFovRad * 0.5f);
        transform.localScale = new Vector3(quadWidth, quadHeight, 1);

        clientThread = new Thread(NetworkLoop);
        clientThread.IsBackground = true;
        clientThread.Start();
    }

    private void NetworkLoop()
    {
        try
        {
            udpClient = new UdpClient();
            IPEndPoint serverEndPoint = new IPEndPoint(IPAddress.Parse(serverAddress), serverPort);

            byte[] pingMsg = System.Text.Encoding.ASCII.GetBytes("ping");
            udpClient.Send(pingMsg, pingMsg.Length, serverEndPoint);

            while (isRunning)
            {
                IPEndPoint remoteEndPoint = null;
                byte[] receivedData = udpClient.Receive(ref remoteEndPoint);

                if (receivedData.Length < 6) continue;

                uint frameId = BitConverter.ToUInt32(receivedData, 0);
                byte chunkId = receivedData[4];
                byte totalChunks = receivedData[5];
                
                if (frameId < lastCompletedFrameId) continue;

                if (!frameBuffer.ContainsKey(frameId))
                {
                    frameBuffer[frameId] = new Dictionary<byte, byte[]>();
                    totalChunksForFrame[frameId] = totalChunks;
                }

                byte[] chunkData = new byte[receivedData.Length - 6];
                Array.Copy(receivedData, 6, chunkData, 0, chunkData.Length);
                frameBuffer[frameId][chunkId] = chunkData;

                if (frameBuffer[frameId].Count == totalChunksForFrame[frameId])
                {
                    var chunks = frameBuffer[frameId].OrderBy(kvp => kvp.Key).Select(kvp => kvp.Value);
                    byte[] fullFrameData = chunks.SelectMany(a => a).ToArray();
                    
                    lock (dataLock)
                    {
                        // Add the completed frame to the queue instead of a single variable.
                        // We cap the queue at 2 to prevent latency from building up.
                        if (frameQueue.Count < 2) 
                        {
                            frameQueue.Enqueue(fullFrameData);
                        }
                    }
                    
                    lastCompletedFrameId = frameId;
                    var oldFrameIds = frameBuffer.Keys.Where(id => id <= frameId).ToList();
                    foreach (var id in oldFrameIds)
                    {
                        frameBuffer.Remove(id);
                        totalChunksForFrame.Remove(id);
                    }
                }
            }
        }
        catch (Exception e)
        {
            Debug.LogError($"[Passthrough] Network error: {e.Message}");
        }
    }

    void Update()
    {
        lock (dataLock)
        {
            // If there's a frame in the queue, pull it out to be displayed.
            if (frameQueue.Count > 0)
            {
                byte[] frameToDisplay = frameQueue.Dequeue();
                videoTexture.LoadImage(frameToDisplay);
            }
        }
    }

    void OnDestroy()
    {
        isRunning = false;
        if (udpClient != null) udpClient.Close();
        if (clientThread != null && clientThread.IsAlive)
        {
            clientThread.Abort();
        }
    }
}